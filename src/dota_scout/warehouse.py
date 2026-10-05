"""Idempotent raw storage. Completed matches survive failures in later requests."""

import logging
import os
from pathlib import Path

from dota_scout.api import OpenDotaClient, discover, validate_match
from dota_scout.tournaments import selected_leagues, tournament_family

ROOT = Path(__file__).resolve().parents[2]
LOG = logging.getLogger(__name__)


def connect():
    import psycopg
    return psycopg.connect(os.environ["WAREHOUSE_DSN"])


def init_schema(conn):
    conn.execute((ROOT / "sql/schema.sql").read_text(encoding="utf-8"))
    conn.commit()


def sync(*, pages=3, limit=50, before=None, client=None):
    from psycopg.types.json import Jsonb

    if limit < 1:
        raise ValueError("limit must be positive")
    client = client or OpenDotaClient()
    summaries = discover(client, pages, before)
    league_ids, leagues = selected_leagues(client)
    if league_ids is not None:
        summaries = [row for row in summaries if row.get("leagueid") in league_ids]
    heroes = client.get("/heroes")
    with connect() as conn:
        init_schema(conn)
        for league in leagues:
            conn.execute("INSERT INTO raw.leagues (league_id,name,family) VALUES (%s,%s,%s) "
                         "ON CONFLICT (league_id) DO UPDATE SET name=EXCLUDED.name, "
                         "family=EXCLUDED.family, updated_at=now()",
                         (league["leagueid"], league["name"], tournament_family(league["name"])))
        for hero in heroes:
            conn.execute("INSERT INTO raw.heroes VALUES (%s, %s) "
                         "ON CONFLICT (hero_id) DO UPDATE SET name = EXCLUDED.name",
                         (hero["id"], hero["localized_name"]))
        for row in summaries:
            conn.execute("INSERT INTO raw.pro_matches (match_id, start_time, payload) "
                         "VALUES (%s, %s, %s) ON CONFLICT (match_id) DO UPDATE "
                         "SET payload=EXCLUDED.payload, start_time=EXCLUDED.start_time",
                         (row["match_id"], row["start_time"], Jsonb(row)))
        conn.commit()
        pending = conn.execute("""
            SELECT p.match_id FROM raw.pro_matches p
            LEFT JOIN raw.match_payloads m USING (match_id)
            WHERE (%s::bigint[] IS NULL OR (p.payload->>'leagueid')::bigint = ANY(%s))
            AND (m.match_id IS NULL OR (
                jsonb_array_length(COALESCE(NULLIF(m.payload->'picks_bans', 'null'::jsonb),
                                           '[]'::jsonb)) = 0
                AND p.start_time > extract(epoch FROM now() - interval '7 days')
                AND m.fetched_at < now() - interval '6 hours'))
            ORDER BY p.match_id ASC LIMIT %s
        """, (None if league_ids is None else list(league_ids),
              None if league_ids is None else list(league_ids), limit)).fetchall()
        failures = []
        loaded = 0
        for (match_id,) in pending:
            try:
                payload = validate_match(client.get(f"/matches/{match_id}"), match_id)
            except (RuntimeError, ValueError) as exc:
                LOG.warning("Match %s deferred: %s", match_id, exc)
                failures.append(match_id)
                continue
            conn.execute("INSERT INTO raw.match_payloads (match_id, payload) VALUES (%s, %s) "
                         "ON CONFLICT (match_id) DO UPDATE "
                         "SET payload=EXCLUDED.payload, fetched_at=now()",
                         (match_id, Jsonb(payload)))
            conn.commit()
            loaded += 1
        LOG.info("Discovered %s, loaded %s, deferred %s", len(summaries), loaded, len(failures))
        if failures:
            raise RuntimeError(f"{len(failures)} matches deferred; rerun to retry pending matches")
        return loaded


def load_demo():
    """Load clearly labelled synthetic fixtures for a reproducible offline demonstration."""
    import json
    from psycopg.types.json import Jsonb

    fixture = json.loads((ROOT / "tests/fixtures/demo.json").read_text(encoding="utf-8"))
    with connect() as conn:
        init_schema(conn)
        for hero in fixture["heroes"]:
            conn.execute("INSERT INTO raw.heroes VALUES (%s,%s) ON CONFLICT DO NOTHING",
                         (hero["id"], hero["localized_name"]))
        for payload in fixture["matches"]:
            validate_match(payload, payload["match_id"])
            conn.execute("INSERT INTO raw.pro_matches (match_id,start_time,payload) "
                         "VALUES (%s,%s,%s) ON CONFLICT DO NOTHING",
                         (payload["match_id"], payload["start_time"], Jsonb(payload)))
            conn.execute("INSERT INTO raw.match_payloads (match_id,payload) "
                         "VALUES (%s,%s) ON CONFLICT (match_id) DO UPDATE "
                         "SET payload=EXCLUDED.payload, fetched_at=now()",
                         (payload["match_id"], Jsonb(payload)))
        for profile in fixture.get("team_profiles", []):
            conn.execute("INSERT INTO raw.team_profiles (team_id,payload) VALUES (%s,%s) "
                         "ON CONFLICT (team_id) DO UPDATE SET payload=EXCLUDED.payload",
                         (profile["team_id"], Jsonb(profile)))
        for profile in fixture.get("player_profiles", []):
            conn.execute("INSERT INTO raw.player_profiles (account_id,payload) VALUES (%s,%s) "
                         "ON CONFLICT (account_id) DO UPDATE SET payload=EXCLUDED.payload",
                         (profile["profile"]["account_id"], Jsonb(profile)))


def sync_profiles(limit=20, client=None):
    """Refresh a bounded batch of separately stored team and player profiles weekly."""
    from psycopg.types.json import Jsonb
    if limit < 1:
        raise ValueError("limit must be positive")
    client = client or OpenDotaClient()
    loaded = 0
    failures = 0
    with connect() as conn:
        init_schema(conn)
        teams = conn.execute("""
            WITH ids AS (
                SELECT DISTINCT nullif((payload->>'radiant_team_id')::bigint,0) AS id
                FROM raw.pro_matches
                UNION
                SELECT DISTINCT nullif((payload->>'dire_team_id')::bigint,0)
                FROM raw.pro_matches
            )
            SELECT i.id FROM ids i LEFT JOIN raw.team_profiles p ON p.team_id=i.id
            WHERE i.id IS NOT NULL AND (p.team_id IS NULL OR p.fetched_at < now()-interval '7 days')
            ORDER BY p.fetched_at NULLS FIRST, i.id LIMIT %s
        """, (limit,)).fetchall()
        players = conn.execute("""
            WITH ids AS (
                SELECT DISTINCT (player->>'account_id')::bigint AS id
                FROM raw.match_payloads
                CROSS JOIN LATERAL jsonb_array_elements(
                    coalesce(nullif(payload->'players','null'::jsonb),'[]'::jsonb)) player
            )
            SELECT i.id FROM ids i LEFT JOIN raw.player_profiles p ON p.account_id=i.id
            WHERE i.id > 0 AND i.id <> 4294967295
              AND (p.account_id IS NULL OR p.fetched_at < now()-interval '7 days')
            ORDER BY p.fetched_at NULLS FIRST, i.id LIMIT %s
        """, (limit,)).fetchall()
        for kind, ids, table, key in [("teams",teams,"team_profiles","team_id"),
                                       ("players",players,"player_profiles","account_id")]:
            for (entity_id,) in ids:
                try:
                    payload = client.get(f"/{kind}/{entity_id}")
                    if not isinstance(payload, dict):
                        raise ValueError("Invalid profile response")
                    returned_id = (payload.get("team_id") if kind == "teams"
                                   else (payload.get("profile") or {}).get("account_id"))
                    if returned_id is None or int(returned_id) != entity_id:
                        raise ValueError("Missing or mismatched profile ID")
                except (RuntimeError, ValueError, TypeError) as exc:
                    LOG.warning("Profile %s/%s deferred: %s", kind, entity_id, exc)
                    failures += 1
                    continue
                # Identifiers are fixed internal constants, never user input.
                conn.execute(f"INSERT INTO raw.{table} ({key},payload) VALUES (%s,%s) "
                             f"ON CONFLICT ({key}) DO UPDATE SET payload=EXCLUDED.payload, "
                             "fetched_at=now()", (entity_id, Jsonb(payload)))
                conn.commit()
                loaded += 1
    LOG.info("Profiles loaded %s; deferred %s", loaded, failures)
    return {"loaded": loaded, "deferred": failures}

"""Idempotent raw storage. Completed matches survive failures in later requests."""

import logging
import os
from pathlib import Path

from dota_scout.api import OpenDotaClient, discover, validate_match

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
    league_ids = {int(value.strip()) for value in os.getenv("LEAGUE_IDS", "").split(",")
                  if value.strip()}
    if league_ids:
        summaries = [row for row in summaries if row.get("leagueid") in league_ids]
    heroes = client.get("/heroes")
    with connect() as conn:
        init_schema(conn)
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
        """, (list(league_ids) or None, list(league_ids) or None, limit)).fetchall()
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

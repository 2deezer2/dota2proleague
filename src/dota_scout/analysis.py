"""Read a reproducible analysis bundle from PostgreSQL or a local JSON export."""
import json
from datetime import datetime, timezone
from pathlib import Path

from dota_scout.forecast import Match


def merge_match(summary, detail):
    merged = summary | detail
    for key in ("radiant_team_id","dire_team_id","radiant_name","dire_name","leagueid","league_name"):
        if not merged.get(key):
            merged[key] = summary.get(key)
    return merged


def raw_bundle(conn):
    matches = conn.execute("SELECT m.payload,p.payload FROM raw.match_payloads m "
                           "JOIN raw.pro_matches p USING(match_id) ORDER BY p.start_time,m.match_id")
    merged = [merge_match(summary,detail) for detail,summary in matches.fetchall()]
    return {
        "synthetic": False,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "matches": merged,
        "heroes": [{"id":row[0],"localized_name":row[1]} for row in
                   conn.execute("SELECT hero_id,name FROM raw.heroes").fetchall()],
        "team_profiles": [row[0] for row in conn.execute(
            "SELECT payload FROM raw.team_profiles").fetchall()],
        "player_profiles": [row[0] for row in conn.execute(
            "SELECT payload FROM raw.player_profiles").fetchall()],
    }


def load_bundle(path=None):
    if path:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    from dota_scout.warehouse import connect, init_schema
    with connect() as conn:
        init_schema(conn)
        return raw_bundle(conn)


def to_match(payload):
    lineups = {0:[],1:[]}
    for player in payload.get("players") or []:
        slot, account = player.get("player_slot"), player.get("account_id")
        if type(slot) is int and type(account) is int and 0 < account < 4294967295:
            lineups[0 if slot < 128 else 1].append(account)
    return Match(
        int(payload["match_id"]),float(payload["start_time"]),int(payload["duration"]),
        int(payload.get("radiant_team_id") or 0),int(payload.get("dire_team_id") or 0),
        tuple(sorted(lineups[0])),tuple(sorted(lineups[1])),payload["radiant_win"],
    )


def export_bundle(output):
    bundle = load_bundle()
    path = Path(output)
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(bundle,ensure_ascii=False,indent=2,default=str)+"\n",encoding="utf-8")
    return len(bundle["matches"])


def analysis_frames(bundle):
    import pandas as pd
    from dota_scout.forecast import valid_lineup
    from dota_scout.tournaments import tournament_family
    team_rows, player_rows, draft_rows = [], [], []
    heroes = {hero["id"]:hero["localized_name"] for hero in bundle.get("heroes",[])}
    seen = set()
    for payload in sorted(bundle["matches"], key=lambda row:(row["start_time"],row["match_id"])):
        if payload["match_id"] in seen:
            continue
        seen.add(payload["match_id"])
        match = to_match(payload)
        for side,team_id,opponent,lineup,won in [
            (0,match.radiant_team,match.dire_team,match.radiant_players,match.radiant_win),
            (1,match.dire_team,match.radiant_team,match.dire_players,not match.radiant_win),
        ]:
            if team_id <= 0:
                continue
            prefix = "radiant" if side == 0 else "dire"
            metadata = {"match_id":match.match_id,"started_at":pd.to_datetime(match.started_at,unit="s",utc=True),
                        "team_id":team_id,"team_name":(payload.get(prefix+"_team") or {}).get("name")
                        or payload.get(prefix+"_name") or f"Team {team_id}",
                        "opponent_id":opponent,"won":bool(won),"league_id":payload.get("leagueid"),
                        "league_name":payload.get("league_name") or "Unknown",
                        "family":tournament_family(payload.get("league_name")),
                        "duration_minutes":match.duration/60,"has_draft":bool(payload.get("picks_bans")),
                        "is_synthetic": bool(bundle.get("synthetic")) or payload.get("leagueid")==999999,
                        "player_ids":lineup,"roster_known":valid_lineup(lineup)}
            team_rows.append(metadata)
            for player in payload.get("players") or []:
                slot = player.get("player_slot")
                if type(slot) is int and (0 if slot<128 else 1)==side:
                    player_rows.append(metadata | {"account_id":player.get("account_id"),
                        "player_name":player.get("name") or player.get("personaname"),
                        "hero_id":player.get("hero_id"),"kills":player.get("kills"),
                        "deaths":player.get("deaths"),"assists":player.get("assists"),
                        "gold_per_min":player.get("gold_per_min"),"xp_per_min":player.get("xp_per_min")})
            for action in payload.get("picks_bans") or []:
                if action["team"]==side:
                    draft_rows.append(metadata | {"hero_id":action["hero_id"],
                        "hero_name":heroes.get(action["hero_id"],str(action["hero_id"])),
                        "is_pick":action["is_pick"],"draft_order":action["order"]})
    teams, players, drafts = pd.DataFrame(team_rows), pd.DataFrame(player_rows), pd.DataFrame(draft_rows)
    if not teams.empty:
        last, spell, first = {}, {}, {}
        spells, starts = [], []
        for row in teams.itertuples():
            if not row.roster_known:
                spells.append(None)
                starts.append(None)
                continue
            if last.get(row.team_id)!=row.player_ids:
                spell[row.team_id]=spell.get(row.team_id,0)+1
                first[row.team_id]=row.started_at
                last[row.team_id]=row.player_ids
            spells.append(spell[row.team_id])
            starts.append(first[row.team_id])
        teams["roster_spell"] = spells
        teams["roster_first_seen"] = starts
        lookup = teams[["match_id","team_id","roster_spell","roster_first_seen"]]
        if not players.empty:
            players = players.merge(lookup,on=["match_id","team_id"],validate="many_to_one")
        if not drafts.empty:
            drafts = drafts.merge(lookup,on=["match_id","team_id"],validate="many_to_one")
    return teams, players, drafts

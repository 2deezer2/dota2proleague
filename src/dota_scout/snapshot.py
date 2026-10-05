"""Small, explicitly bounded live sample for notebooks without a running database."""
import json
from datetime import datetime, timezone
from pathlib import Path

from dota_scout.api import OpenDotaClient, discover, validate_match
from dota_scout.analysis import merge_match
from dota_scout.tournaments import selected_leagues


def snapshot(output, *, pages=10, limit=60, profile_limit=10, max_seconds=300, client=None):
    if limit < 1 or profile_limit < 0:
        raise ValueError("limit > 0 and profile_limit >= 0 are required")
    client = client or OpenDotaClient(attempts=3,budget_seconds=max_seconds)
    allowed, leagues = selected_leagues(client)
    summaries = discover(client,pages=pages)
    chosen = [row for row in summaries if allowed is None or row.get("leagueid") in allowed]
    heroes = client.get("/heroes")
    payloads, failures = [], []
    profiles = {"team_profiles":[],"player_profiles":[]}
    path = Path(output)
    path.parent.mkdir(parents=True,exist_ok=True)

    def save(complete=False):
        bundle = {"synthetic":False,"exported_at":datetime.now(timezone.utc).isoformat(),
                  "source":"OpenDota bounded snapshot; not complete history",
                  "snapshot_complete":complete,"discovered_matches":len(summaries),
                  "eligible_matches":len(chosen),"matches":payloads,"heroes":heroes,
                  "leagues":leagues,"failures":failures, **profiles}
        path.write_text(json.dumps(bundle,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")

    save()
    print(f"Discovered {len(summaries)}; selected {len(chosen)}; detail limit {limit}",flush=True)
    for summary in chosen[:limit]:
        try:
            detail = validate_match(client.get(f"/matches/{summary['match_id']}"),summary["match_id"])
            payloads.append(merge_match(summary,detail))
        except (RuntimeError,ValueError) as exc:
            failures.append({"match_id":summary["match_id"],"error":str(exc)})
            if "time budget" in str(exc) or len(failures)>=5:
                save()
                break
        save()
        if len(payloads)%10==0:
            print(f"Saved {len(payloads)} matches; deferred {len(failures)}",flush=True)
    team_ids = sorted({int(row.get(field) or 0) for row in payloads
                       for field in ("radiant_team_id","dire_team_id")} - {0})
    player_ids = sorted({player["account_id"] for row in payloads for player in row.get("players",[])
                         if type(player.get("account_id")) is int
                         and 0 < player["account_id"] < 4294967295})
    for kind, ids, key in [("teams",team_ids,"team_profiles"),("players",player_ids,"player_profiles")]:
        for entity in ids[:profile_limit]:
            try:
                profile = client.get(f"/{kind}/{entity}")
                if isinstance(profile,dict):
                    profiles[key].append(profile)
            except RuntimeError as exc:
                failures.append({"profile":f"{kind}/{entity}","error":str(exc)})
            save()
    save(complete=not failures)
    return {"discovered":len(summaries),"eligible":len(chosen),"loaded":len(payloads),
            "deferred":len(failures),"output":str(path)}

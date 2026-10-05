"""Selected event families, independently of unverified tier metadata."""
import json
import os
import re
from pathlib import Path

CONFIG = Path(__file__).resolve().parents[2] / "config/tournament_families.json"


def tournament_family(name):
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    if re.search(config["exclude_pattern"], name or "", re.IGNORECASE):
        return None
    for family in config["families"]:
        if re.search(family["pattern"], name or "", re.IGNORECASE):
            return family["name"]
    return None


def selected_leagues(client):
    """An explicit allowlist overrides family matching; empty set never means allow all."""
    explicit = {int(item.strip()) for item in os.getenv("LEAGUE_IDS", "").split(",")
                if item.strip()}
    if explicit:
        return explicit, []
    if os.getenv("TOURNAMENT_SCOPE", "selected") == "all":
        return None, []
    leagues = client.get("/leagues")
    return {league["leagueid"] for league in leagues if tournament_family(league.get("name"))}, leagues

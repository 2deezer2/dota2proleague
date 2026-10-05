"""Generate local secrets without overwriting an existing .env."""
import secrets
from pathlib import Path

target = Path(__file__).resolve().parents[1] / ".env"
if target.exists():
    print(".env already exists; kept unchanged")
else:
    with target.open("x", encoding="utf-8") as output:
        output.write(f"POSTGRES_PASSWORD={secrets.token_hex(24)}\n")
        output.write("OPENDOTA_API_KEY=\n")
        output.write("MATCH_PAGES=3\nMATCH_LIMIT=50\n")
        output.write("LEAGUE_IDS=\n")
        output.write("TOURNAMENT_SCOPE=selected\nPROFILE_LIMIT=20\n")
    print("Created .env with a random local database password")

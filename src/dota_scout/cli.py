import argparse
import logging


def main():
    parser = argparse.ArgumentParser(description="Ingest professional Dota 2 matches")
    sub = parser.add_subparsers(dest="command", required=True)
    collect = sub.add_parser("sync")
    collect.add_argument("--pages", type=int, default=3)
    collect.add_argument("--limit", type=int, default=50)
    collect.add_argument("--before", type=int, help="Fetch match IDs below this cursor")
    sub.add_parser("init")
    sub.add_parser("demo")
    sub.add_parser("leagues", help="List tournament IDs to configure LEAGUE_IDS")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    if args.command == "leagues":
        from dota_scout.api import OpenDotaClient
        for league in OpenDotaClient().get("/leagues"):
            print(f"{league['leagueid']}\t{league['name']}")
        return
    from dota_scout.warehouse import connect, init_schema, load_demo, sync
    if args.command == "sync":
        sync(pages=args.pages, limit=args.limit, before=args.before)
    elif args.command == "demo":
        load_demo()
    else:
        with connect() as conn:
            init_schema(conn)


if __name__ == "__main__":
    main()

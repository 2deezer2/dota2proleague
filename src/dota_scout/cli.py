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
    profiles = sub.add_parser("profiles", help="Refresh separate team and player profiles")
    profiles.add_argument("--limit", type=int, default=20)
    export = sub.add_parser("export", help="Export raw matches and profiles for Jupyter")
    export.add_argument("--output", default="data/analysis.json")
    sample = sub.add_parser("snapshot", help="Bounded live notebook sample without PostgreSQL")
    sample.add_argument("--pages",type=int,default=10)
    sample.add_argument("--limit",type=int,default=60)
    sample.add_argument("--profile-limit",type=int,default=10)
    sample.add_argument("--output",default="data/analysis.json")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    if args.command == "leagues":
        from dota_scout.api import OpenDotaClient
        for league in OpenDotaClient().get("/leagues"):
            print(f"{league['leagueid']}\t{league['name']}")
        return
    if args.command == "export":
        from dota_scout.analysis import export_bundle
        print(f"Exported {export_bundle(args.output)} matches to {args.output}")
        return
    if args.command == "snapshot":
        from dota_scout.snapshot import snapshot
        print(snapshot(args.output,pages=args.pages,limit=args.limit,profile_limit=args.profile_limit))
        return
    from dota_scout.warehouse import connect, init_schema, load_demo, sync, sync_profiles
    if args.command == "sync":
        sync(pages=args.pages, limit=args.limit, before=args.before)
    elif args.command == "demo":
        load_demo()
    elif args.command == "profiles":
        sync_profiles(limit=args.limit)
    else:
        with connect() as conn:
            init_schema(conn)


if __name__ == "__main__":
    main()

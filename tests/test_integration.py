"""Run against a dedicated empty PostgreSQL database, never a production database."""
import os
import unittest
from unittest.mock import patch


@unittest.skipUnless(os.getenv("RUN_DB_TESTS") == "1", "Set RUN_DB_TESTS=1 for PostgreSQL tests")
class WarehouseTests(unittest.TestCase):
    def test_demo_load_is_idempotent_and_marts_are_correct(self):
        import subprocess
        from dota_scout.warehouse import connect, load_demo
        load_demo()
        load_demo()
        with connect() as conn:
            self.assertEqual(conn.execute("SELECT count(*) FROM raw.match_payloads "
                                          "WHERE match_id IN (900000000001,900000000002)")
                             .fetchone()[0], 2)
        dbt = os.getenv("DBT_BIN", "dbt")
        subprocess.run([dbt, "build", "--project-dir", "dbt", "--profiles-dir", "dbt"],
                       check=True)
        with connect() as conn:
            stats = conn.execute("SELECT games,wins,win_rate FROM analytics.team_summary "
                                 "WHERE team_id=990001 AND league_id=999999").fetchone()
            self.assertEqual(stats[:2], (2, 1))
            self.assertEqual(float(stats[2]), 50.0)
            hero = conn.execute("SELECT picks,bans,pick_wins FROM analytics.hero_summary "
                                "WHERE team_id=990001 AND league_id=999999 AND hero_id=2")
            self.assertEqual(hero.fetchone(), (2, 0, 1))
            self.assertEqual(conn.execute("SELECT count(*) FROM analytics.fct_team_matches "
                                          "WHERE league_id=999999").fetchone()[0], 4)

    def test_sync_rerun_keeps_one_payload_and_does_not_refetch_complete_match(self):
        from dota_scout.warehouse import sync, connect
        class Client:
            def __init__(self):
                self.detail_calls = 0
            def get(self, endpoint, **_params):
                if endpoint == "/proMatches":
                    return [{"match_id": 900000000003, "start_time": 1790812800,
                             "leagueid": 999998}]
                if endpoint == "/heroes":
                    return []
                self.detail_calls += 1
                return {"match_id": 900000000003, "start_time": 1790812800,
                        "duration": 2000, "radiant_win": True, "leagueid":999998,
                        "picks_bans":[{"order":0,"hero_id":2,"team":0,"is_pick":True}]}
        client = Client()
        with patch.dict(os.environ, {"LEAGUE_IDS": "999998"}):
            sync(pages=1, client=client)
            sync(pages=1, client=client)
        self.assertEqual(client.detail_calls, 1)
        with connect() as conn:
            self.assertEqual(conn.execute("SELECT count(*) FROM raw.match_payloads "
                                          "WHERE match_id=900000000003").fetchone()[0], 1)

    def test_roster_change_resets_roster_summary_and_keeps_players_separate(self):
        import json
        import subprocess
        from pathlib import Path
        from psycopg.types.json import Jsonb
        from dota_scout.warehouse import connect, load_demo
        load_demo()
        fixture=json.loads((Path(__file__).parent/'fixtures/demo.json').read_text())
        changed=fixture['matches'][0]
        changed['match_id']=900000000004
        changed['start_time']=fixture['matches'][1]['start_time']+86400
        changed['players'][0]['account_id']=910099
        with connect() as conn:
            conn.execute("INSERT INTO raw.pro_matches(match_id,start_time,payload) VALUES (%s,%s,%s) "
                         "ON CONFLICT DO NOTHING",(changed['match_id'],changed['start_time'],Jsonb(changed)))
            conn.execute("INSERT INTO raw.match_payloads(match_id,payload) VALUES (%s,%s) "
                         "ON CONFLICT DO NOTHING",(changed['match_id'],Jsonb(changed)))
        subprocess.run([os.getenv('DBT_BIN','dbt'),'build','--project-dir','dbt','--profiles-dir','dbt'],
                       check=True)
        with connect() as conn:
            self.assertEqual(conn.execute("SELECT roster_spell,games FROM analytics.current_rosters "
                                          "WHERE team_id=990001").fetchone(),(2,1))
            self.assertEqual(conn.execute("SELECT count(*) FROM analytics.fct_player_matches "
                                          "WHERE account_id=910001").fetchone()[0],2)
            self.assertEqual(conn.execute("SELECT count(*) FROM analytics.dim_players "
                                          "WHERE account_id=910099").fetchone()[0],1)

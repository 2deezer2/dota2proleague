import unittest

from dota_scout.forecast import Match, chronological_features, history_before, temporal_holdout
from dota_scout.tournaments import tournament_family, selected_leagues

A, B = (1,2,3,4,5), (6,7,8,9,10)


def match(i, start, a=A, win=True, duration=100):
    return Match(i,start,duration,100,200,a,B,win)


class ForecastTests(unittest.TestCase):
    def test_features_ignore_current_and_future_outcomes(self):
        original = [match(1,0),match(2,200),match(3,400)]
        changed = [match(1,0),match(2,200,win=False),match(3,400,win=False)]
        left, right = chronological_features(original), chronological_features(changed)
        for key in left[1]:
            if key != "radiant_win":
                self.assertEqual(left[1][key],right[1][key])
        self.assertEqual(left[0]["radiant_roster_games"],0)
        self.assertEqual(left[1]["radiant_roster_games"],1)

    def test_overlapping_game_outcome_is_unavailable(self):
        rows = chronological_features([match(1,0,duration=1000),match(2,500)])
        self.assertEqual(rows[1]["radiant_roster_games"],0)
        self.assertEqual(rows[1]["roster_elo_diff"],0)

    def test_new_roster_resets_team_history_but_keeps_player_experience(self):
        rows = chronological_features([match(1,0),match(2,200,a=(1,2,3,4,11))])
        self.assertEqual(rows[1]["radiant_roster_games"],0)
        self.assertEqual(rows[1]["dire_roster_games"],1)
        self.assertNotEqual(rows[1]["player_elo_diff"],0)

    def test_returning_five_starts_a_new_spell(self):
        rows = chronological_features([match(1,0),match(2,200,a=(1,2,3,4,11)),match(3,400)])
        self.assertEqual(rows[2]["radiant_roster_games"],0)

    def test_forecast_uses_explicit_cutoff_and_known_five(self):
        history = history_before([match(1,0),match(2,200)],150)
        self.assertEqual(history.features(100,200,A,B)["radiant_roster_games"],1)
        with self.assertRaises(ValueError):
            history.features(100,200,A[:4],B)
        with self.assertRaises(ValueError):
            history.features(100,200,A,A)

    def test_holdout_purges_unfinished_training_results(self):
        rows = [{"match_id":i,"started_at":i*200,"finished_at":i*200+100,
                 "radiant_win":i%2} for i in range(12)]
        rows[8]["finished_at"] = 999999
        train,test,cut = temporal_holdout(rows)
        self.assertTrue(all(row["finished_at"]<cut for row in train))
        self.assertTrue(all(row["started_at"]>=cut for row in test))
        self.assertNotIn(8,{row["match_id"] for row in train})

    def test_duplicate_match_is_rejected(self):
        with self.assertRaises(ValueError):
            chronological_features([match(1,0),match(1,0)])


class TournamentTests(unittest.TestCase):
    def test_selected_main_events(self):
        examples = {"BLAST SLAM VIII":"BLAST Slam", "ESL One Birmingham 2026":"ESL One",
                    "DreamLeague Season 28":"DreamLeague Season", "Esports World Cup 2026":
                    "Esports World Cup", "PGL Wallachia Season 7":"PGL Wallachia",
                    "The International 2026":"The International"}
        for name,family in examples.items():
            self.assertEqual(tournament_family(name),family)

    def test_qualifiers_division_two_and_other_esl_events_excluded(self):
        for name in ["BLAST Slam IX China Open Qualifier", "DreamLeague Division 2 Series 5",
                     "PGL Wallachia Closed Qualifiers", "ESL Challenger", "FISSURE Universe 8"]:
            self.assertIsNone(tournament_family(name))

    def test_empty_matching_set_is_not_all_events(self):
        from unittest.mock import patch
        class Client:
            def get(self,*_args):
                return [{"leagueid":1,"name":"Some Tier 3 event"}]
        with patch.dict("os.environ",{"LEAGUE_IDS":"","TOURNAMENT_SCOPE":"selected"}):
            allowed,_ = selected_leagues(Client())
        self.assertEqual(allowed,set())

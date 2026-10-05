import io
import json
import unittest
from urllib.error import HTTPError
from unittest.mock import patch

from dota_scout.api import OpenDotaClient, discover, retry_delay, validate_match


class APIClientTests(unittest.TestCase):
    def test_retries_rate_limit_and_paces_every_attempt(self):
        calls, sleeps = [], []

        def opener(request, timeout):
            calls.append((request.full_url, timeout))
            if len(calls) == 1:
                raise HTTPError(request.full_url, 429, "rate limited", {"Retry-After": "2"}, None)
            return io.BytesIO(b'[{"match_id": 1}]')

        result = OpenDotaClient(opener=opener, sleep=sleeps.append).get("/proMatches")
        self.assertEqual(result, [{"match_id": 1}])
        self.assertEqual(sleeps, [1.1, 2.0, 1.1])
        self.assertEqual(calls[0][1], 30)

    def test_non_retryable_error_does_not_leak_api_key(self):
        def opener(request, timeout):
            raise HTTPError(request.full_url, 401, "unauthorized", {}, None)
        with patch.dict("os.environ", {"OPENDOTA_API_KEY": "secret-for-test"}):
            with self.assertRaisesRegex(RuntimeError, "HTTP 401") as caught:
                OpenDotaClient(opener=opener, sleep=lambda _: None).get("/heroes")
        self.assertNotIn("secret-for-test", str(caught.exception))

    def test_retries_are_bounded(self):
        calls = []
        def opener(request, timeout):
            calls.append(request)
            raise TimeoutError()
        with self.assertRaisesRegex(RuntimeError, "retries exhausted"):
            OpenDotaClient(attempts=3, opener=opener, sleep=lambda _: None).get("/heroes")
        self.assertEqual(len(calls), 3)

    def test_pagination_and_deduplication(self):
        class Client:
            def __init__(self):
                self.cursors = []
            def get(self, endpoint, **params):
                self.cursors.append(params["less_than_match_id"])
                ids = [10, 9] if len(self.cursors) == 1 else [9, 8]
                return [{"match_id": item, "start_time": 1} for item in ids]
        client = Client()
        self.assertEqual({row["match_id"] for row in discover(client, pages=2)}, {8, 9, 10})
        self.assertEqual(client.cursors, [None, 9])

    def test_stuck_cursor_is_rejected(self):
        class Client:
            def get(self, *_args, **_kwargs):
                return [{"match_id": 10, "start_time": 1}]
        with self.assertRaisesRegex(ValueError, "cursor did not advance"):
            discover(Client(), pages=2)

    def test_missing_draft_is_allowed_but_wrong_outcome_is_not(self):
        payload = {"match_id": 1, "start_time": 1, "duration": 1800, "radiant_win": False}
        self.assertEqual(validate_match(payload, 1), payload)
        with self.assertRaises(ValueError):
            validate_match(payload | {"radiant_win": "false"}, 1)
        with self.assertRaises(ValueError):
            validate_match(payload, 2)

    def test_duplicate_draft_order_rejected(self):
        action = {"is_pick": True, "team": 0, "hero_id": 1, "order": 0}
        payload = {"match_id": 1, "start_time": 1, "duration": 1800,
                   "radiant_win": True, "picks_bans": [action, action]}
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            validate_match(payload, 1)

    def test_retry_after_is_capped(self):
        self.assertEqual(retry_delay("999999", 0), 120)

    def test_demo_fixtures_are_valid(self):
        from pathlib import Path
        fixture = json.loads((Path(__file__).parent / "fixtures/demo.json").read_text())
        for match in fixture["matches"]:
            validate_match(match, match["match_id"])


if __name__ == "__main__":
    unittest.main()

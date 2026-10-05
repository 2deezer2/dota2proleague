"""OpenDota client: bounded retries, timeouts and pacing, without third-party HTTP libraries."""

import json
import os
import random
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class OpenDotaClient:
    def __init__(self, *, interval=1.1, attempts=5, opener=urlopen, sleep=time.sleep):
        if interval < 0 or attempts < 1:
            raise ValueError("interval >= 0 and attempts >= 1 are required")
        self.interval = interval
        self.attempts = attempts
        self.opener = opener
        self.sleep = sleep

    def get(self, endpoint, **params):
        if not endpoint.startswith("/") or ".." in endpoint:
            raise ValueError("Expected an API endpoint")
        params = {key: value for key, value in params.items() if value is not None}
        if os.getenv("OPENDOTA_API_KEY"):
            params["api_key"] = os.environ["OPENDOTA_API_KEY"]
        url = "https://api.opendota.com/api" + endpoint
        if params:
            url += "?" + urlencode(params)
        request = Request(url, headers={"User-Agent": "dota2proleague/0.1"})
        for attempt in range(self.attempts):
            self.sleep(self.interval)
            try:
                with self.opener(request, timeout=30) as response:
                    return json.load(response)
            except HTTPError as exc:
                if exc.code != 429 and not 500 <= exc.code < 600:
                    # Never include a URL containing an API key in logs.
                    raise RuntimeError(f"OpenDota {endpoint}: HTTP {exc.code}") from None
                retry_after = exc.headers.get("Retry-After") if exc.headers else None
                delay = retry_delay(retry_after, attempt)
            except (URLError, TimeoutError, ConnectionError):
                delay = retry_delay(None, attempt)
            if attempt + 1 < self.attempts:
                self.sleep(delay)
        raise RuntimeError(f"OpenDota {endpoint}: retries exhausted") from None


def retry_delay(value, attempt):
    if value:
        try:
            return min(120, max(0, float(value)))
        except ValueError:
            try:
                date = parsedate_to_datetime(value)
                return min(120, max(0, (date - datetime.now(timezone.utc)).total_seconds()))
            except (TypeError, ValueError):
                pass
    return min(60, 2 ** attempt + random.random())


def discover(client, pages=3, before=None):
    """Walk the API's decreasing match-id cursor; deduplicate overlapping pages."""
    if pages < 1:
        raise ValueError("pages must be positive")
    found = {}
    cursor = before
    for _ in range(pages):
        rows = client.get("/proMatches", less_than_match_id=cursor)
        if not isinstance(rows, list):
            raise ValueError("Unexpected proMatches response")
        if not rows:
            break
        for row in rows:
            validate_summary(row)
            found[row["match_id"]] = row
        next_cursor = min(row["match_id"] for row in rows)
        if cursor is not None and next_cursor >= cursor:
            raise ValueError("OpenDota pagination cursor did not advance")
        cursor = next_cursor
    return list(found.values())


def validate_summary(row):
    if not isinstance(row, dict) or type(row.get("match_id")) is not int:
        raise ValueError("Invalid match_id")
    if row["match_id"] <= 0 or type(row.get("start_time")) is not int:
        raise ValueError("Invalid match timestamp or ID")


def validate_match(payload, expected_id):
    validate_summary(payload)
    if payload["match_id"] != expected_id:
        raise ValueError("Response match_id does not match requested ID")
    if type(payload.get("radiant_win")) is not bool:
        raise ValueError("Missing match outcome")
    if type(payload.get("duration")) is not int or payload["duration"] <= 0:
        raise ValueError("Invalid match duration")
    draft = payload.get("picks_bans") or []
    if not isinstance(draft, list):
        raise ValueError("Invalid draft")
    orders = set()
    for action in draft:
        if (not isinstance(action, dict) or type(action.get("is_pick")) is not bool
                or type(action.get("team")) is not int or action["team"] not in (0, 1)
                or type(action.get("hero_id")) is not int or action["hero_id"] <= 0
                or type(action.get("order")) is not int or action["order"] < 0):
            raise ValueError("Invalid draft action")
        if action["order"] in orders:
            raise ValueError("Duplicate draft order")
        orders.add(action["order"])
    return payload

"""Chronological, roster-aware pre-draft features using only finished games.

Lineups are supplied to the prediction scenario. Observed historical lineups are not
proof that an upcoming lineup was publicly known; never call these official transfer dates.
"""
import heapq
import math
from collections import deque
from dataclasses import dataclass, field

FEATURES = ["roster_elo_diff", "player_elo_diff", "roster_form_diff", "player_form_diff",
            "roster_games_diff", "player_games_diff"]


@dataclass(frozen=True)
class Match:
    match_id: int
    started_at: float
    duration: int
    radiant_team: int
    dire_team: int
    radiant_players: tuple[int, ...]
    dire_players: tuple[int, ...]
    radiant_win: bool

    @property
    def finished_at(self):
        return self.started_at + self.duration


@dataclass
class Rating:
    elo: float = 1500.0
    games: int = 0
    recent: deque = field(default_factory=lambda: deque(maxlen=20))

    @property
    def form(self):
        return (sum(self.recent) + 2) / (len(self.recent) + 4)


def valid_lineup(players):
    return len(players) == 5 and len(set(players)) == 5 and all(
        type(player) is int and 0 < player < 4294967295 for player in players)


def probability(rating_a, rating_b):
    return 1 / (1 + 10 ** ((rating_b - rating_a) / 400))


class RosterHistory:
    """Changing five resets team form and Elo; player history survives a transfer."""
    def __init__(self):
        self.teams = {}
        self.players = {}
        self.cutoff = None

    def roster_rating(self, team_id, players):
        signature = tuple(sorted(players))
        stored = self.teams.get(team_id)
        return stored[1] if stored and stored[0] == signature else Rating()

    def player_ratings(self, players):
        return [self.players.get(player, Rating()) for player in players]

    def features(self, team_a, team_b, players_a, players_b):
        if not valid_lineup(players_a) or not valid_lineup(players_b):
            raise ValueError("Two known five-player lineups are required")
        if team_a <= 0 or team_b <= 0 or team_a == team_b:
            raise ValueError("Two distinct positive team IDs are required")
        if set(players_a) & set(players_b):
            raise ValueError("A player cannot be on both teams")
        a, b = self.roster_rating(team_a, players_a), self.roster_rating(team_b, players_b)
        pa, pb = self.player_ratings(players_a), self.player_ratings(players_b)
        def average(rows, attr):
            return sum(getattr(row, attr) for row in rows) / len(rows)
        return {
            "roster_elo_diff": a.elo - b.elo,
            "player_elo_diff": average(pa,"elo") - average(pb,"elo"),
            "roster_form_diff": a.form - b.form,
            "player_form_diff": average(pa,"form") - average(pb,"form"),
            "roster_games_diff": math.log1p(a.games) - math.log1p(b.games),
            "player_games_diff": math.log1p(average(pa,"games"))
                                 - math.log1p(average(pb,"games")),
            "radiant_roster_games": a.games,
            "dire_roster_games": b.games,
        }

    def observe(self, match):
        if (not valid_lineup(match.radiant_players) or not valid_lineup(match.dire_players)
                or match.radiant_team <= 0 or match.dire_team <= 0
                or match.radiant_team == match.dire_team):
            return
        a = self.roster_rating(match.radiant_team,match.radiant_players)
        b = self.roster_rating(match.dire_team,match.dire_players)
        pa, pb = self.player_ratings(match.radiant_players), self.player_ratings(match.dire_players)
        roster_delta = 24 * (int(match.radiant_win)-probability(a.elo,b.elo))
        player_delta = 16 * (int(match.radiant_win)-probability(
            sum(p.elo for p in pa)/5, sum(p.elo for p in pb)/5))
        for team, lineup, rating, result, delta in [
            (match.radiant_team,match.radiant_players,a,match.radiant_win,roster_delta),
            (match.dire_team,match.dire_players,b,not match.radiant_win,-roster_delta),
        ]:
            rating.elo += delta
            rating.games += 1
            rating.recent.append(int(result))
            self.teams[team] = (tuple(sorted(lineup)),rating)
        for lineup, ratings, result, delta in [
            (match.radiant_players,pa,match.radiant_win,player_delta),
            (match.dire_players,pb,not match.radiant_win,-player_delta),
        ]:
            for player, rating in zip(lineup, ratings):
                rating.elo += delta
                rating.games += 1
                rating.recent.append(int(result))
                self.players[player] = rating


def chronological_features(matches):
    """Every row is one map; outcomes are consumed only after the map ended."""
    history = RosterHistory()
    pending, rows, seen = [], [], set()
    for match in sorted(matches, key=lambda row:(row.started_at,row.match_id)):
        if match.match_id in seen:
            raise ValueError("Duplicate match_id")
        seen.add(match.match_id)
        if match.duration <= 0:
            raise ValueError("Match duration must be positive")
        while pending and pending[0][0] < match.started_at:
            _, _, finished = heapq.heappop(pending)
            history.observe(finished)
        if (valid_lineup(match.radiant_players) and valid_lineup(match.dire_players)
                and match.radiant_team > 0 and match.dire_team > 0
                and match.radiant_team != match.dire_team):
            row = history.features(match.radiant_team,match.dire_team,
                                   match.radiant_players,match.dire_players)
            row.update(match_id=match.match_id, started_at=match.started_at,
                       finished_at=match.finished_at, radiant_win=int(match.radiant_win))
            rows.append(row)
        heapq.heappush(pending,(match.finished_at,match.match_id,match))
    return rows


def history_before(matches, as_of):
    """A forecast requires an explicit timestamp and explicitly supplied future lineups."""
    history = RosterHistory()
    for match in sorted(matches, key=lambda row:(row.finished_at,row.match_id)):
        if match.finished_at < as_of:
            history.observe(match)
    history.cutoff = as_of
    return history


def temporal_holdout(rows, test_fraction=0.25):
    """Hold out the latest start times; purge training outcomes not yet finished."""
    if not 0 < test_fraction < 1 or len(rows) < 8:
        raise ValueError("Need at least 8 matches and test_fraction between 0 and 1")
    ordered = sorted(rows,key=lambda row:(row["started_at"],row["match_id"]))
    cut = ordered[max(1,int(len(ordered)*(1-test_fraction)))]["started_at"]
    train = [row for row in ordered if row["finished_at"] < cut]
    test = [row for row in ordered if row["started_at"] >= cut]
    if len(train) < 4 or len(test) < 2 or len({row["radiant_win"] for row in train}) < 2:
        raise ValueError("Insufficient independent matches/classes for chronological evaluation")
    return train, test, cut

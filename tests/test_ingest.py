import pytest

from futdados.ingest.football_data import (FootballDataClient, MissingTokenError, RateLimiter,
                                           parse_matches, parse_standings)
from futdados.ingest.historical import assign_seasons

import pandas as pd

API_MATCHES = {"matches": [
    {"id": 1, "utcDate": "2026-04-01T22:00:00Z", "status": "FINISHED", "matchday": 1,
     "homeTeam": {"id": 1776, "name": "São Paulo FC", "shortName": "São Paulo", "tla": "SAO"},
     "awayTeam": {"id": 1769, "name": "SE Palmeiras", "shortName": "Palmeiras", "tla": "PAL"},
     "score": {"fullTime": {"home": 2, "away": 1}}},
    {"id": 2, "utcDate": "2026-04-08T22:00:00Z", "status": "TIMED", "matchday": 2,
     "homeTeam": {"id": 1769, "name": "SE Palmeiras", "shortName": "Palmeiras", "tla": "PAL"},
     "awayTeam": {"id": 1776, "name": "São Paulo FC", "shortName": "São Paulo", "tla": "SAO"},
     "score": {"fullTime": {"home": None, "away": None}}},
]}


def test_rate_limiter_never_exceeds_limit():
    t = [0.0]
    slept = []

    def sleep(s):
        slept.append(s)
        t[0] += s

    lim = RateLimiter(10, clock=lambda: t[0], sleep=sleep)
    stamps = []
    for _ in range(25):
        lim.wait()
        stamps.append(t[0])
        t[0] += 0.1
    for i in range(len(stamps) - 10):
        assert stamps[i + 10] - stamps[i] >= 60
    assert slept


def test_missing_token(monkeypatch, tmp_path):
    monkeypatch.delenv("FOOTBALL_DATA_TOKEN", raising=False)
    with pytest.raises(MissingTokenError):
        FootballDataClient("https://x", tmp_path)


def test_parse_matches_and_idempotent_upsert(repo):
    rows = parse_matches(API_MATCHES, 2026)
    assert rows[0]["home_id"] == "sao-paulo" and rows[0]["home_goals"] == 2
    assert rows[1]["home_goals"] is None and rows[1]["status"] == "TIMED"
    repo.upsert_matches(rows)
    repo.upsert_matches(rows)  # segunda vez não duplica
    assert len(repo.matches(2026)) == 2
    rows[1].update(status="FINISHED", home_goals=0, away_goals=0)
    repo.upsert_matches(rows)
    df = repo.matches(2026)
    assert len(df) == 2 and (df.status == "FINISHED").all()


def test_parse_standings():
    payload = {"standings": [{"type": "TOTAL", "table": [
        {"position": 1, "team": {"name": "São Paulo FC"}, "playedGames": 1, "won": 1, "draw": 0,
         "lost": 0, "points": 3, "goalsFor": 2, "goalsAgainst": 1}]}]}
    assert parse_standings(payload)[0]["team_id"] == "sao-paulo"


def test_assign_seasons_by_round_reset():
    ids = pd.Series([1, 2, 3, 4, 5, 6])
    rounds = pd.Series([1, 38, 38, 1, 2, 38])
    assert list(assign_seasons(ids, rounds, 2003)) == [2003, 2003, 2003, 2004, 2004, 2004]

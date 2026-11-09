import sqlite3

import pytest


def _rec(**kw):
    rec = dict(season=2026, round=1, home_id="sao-paulo", away_id="palmeiras",
               kickoff_utc="2026-04-01T22:00:00Z", model_version="t", lambda_home=1.4,
               lambda_away=1.0, p_home=0.45, p_draw=0.28, p_away=0.27, payload={"x": 1})
    rec.update(kw)
    return rec


def test_prediction_registry_is_append_only(repo):
    repo.insert_prediction(_rec(), created_at="2026-04-01T10:00:00Z")
    repo.insert_prediction(_rec(home_id="santos"), created_at="2026-04-01T10:00:01Z")
    assert repo.verify_prediction_chain()
    with pytest.raises(sqlite3.DatabaseError):
        repo.conn.execute("UPDATE predictions SET p_home = 0.9")
    with pytest.raises(sqlite3.DatabaseError):
        repo.conn.execute("DELETE FROM predictions")


def test_prediction_after_kickoff_is_rejected(repo):
    with pytest.raises(sqlite3.IntegrityError):
        repo.insert_prediction(_rec(), created_at="2026-04-01T22:30:00Z")

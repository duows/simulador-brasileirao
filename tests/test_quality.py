from pathlib import Path

import pandas as pd
import pytest

from futdados.config import load_config
from futdados.quality import closed_season_issues, compute_flags, coverage, quality_issues, season_rules

DB = Path(load_config()["paths"]["db"])
CURRENT = 2026


def _season(teams=("a", "b", "c", "d"), season=2030):
    from futdados.simulate.schedule import round_robin

    rows = []
    for r, games in enumerate(round_robin(list(teams)), start=1):
        for h, a in games:
            rows.append(dict(season=season, round=r, home_id=h, away_id=a, status="FINISHED",
                             home_goals=1, away_goals=0, source="teste",
                             kickoff_utc=pd.Timestamp("2030-04-01", tz="UTC") + pd.Timedelta(days=7 * r)))
    return pd.DataFrame(rows)


def test_season_rules_defaults_and_overrides():
    assert season_rules(2010)["jogos_esperados"] == 380
    assert season_rules(2016)["jogos_esperados"] == 379
    assert season_rules(2020)["portoes_fechados"]["inicio"] == "2020-08-01"
    assert season_rules(2026)["zonas"]["rebaixamento"] == [17, 20]


def test_quality_catches_duplicates_and_double_round():
    df = _season()
    assert quality_issues(df) == []
    bad = pd.concat([df, df.iloc[[0]]])
    assert any("duplicados" in i for i in quality_issues(bad))
    clash = df.copy()
    clash.loc[2, "round"] = 1  # o jogo da rodada 2 de um time vai para a rodada 1
    assert any("mesma rodada" in i for i in quality_issues(clash))
    neg = df.copy()
    neg.loc[0, "home_goals"] = -1
    assert "placar negativo" in quality_issues(neg)


def test_flags_postponed_and_rescheduled():
    df = _season()
    df.loc[0, "kickoff_utc"] = df.loc[0, "kickoff_utc"] + pd.Timedelta(days=20)  # disputado bem depois
    df.loc[3, ["status", "home_goals", "away_goals"]] = ["TIMED", None, None]   # rodada já andou sem ele
    f = compute_flags(df)
    assert f.loc[0, "rescheduled"] == 1 and f.loc[3, "postponed"] == 1
    assert f.loc[1, "postponed"] == 0 and f.behind_closed_doors.sum() == 0


@pytest.mark.skipif(not DB.exists(), reason="banco local não existe")
def test_real_database_closed_seasons_complete():
    from futdados.db import Repository

    m = Repository(DB).matches()
    if m.empty or m.season.min() > 2006:
        pytest.skip("histórico 2006+ não carregado")
    assert quality_issues(m) == []
    for s in range(2006, CURRENT):
        assert closed_season_issues(m, s) == [], f"temporada {s}"
    cov = coverage(m, 2006, CURRENT - 1)
    assert (cov.existentes == cov.esperados).all()

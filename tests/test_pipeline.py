"""Teste de ponta a ponta do pipeline da rodada com uma liga fictícia."""

import json
import sqlite3

import numpy as np
import pandas as pd
import pytest

from futdados.config import load_config
from futdados.db import Repository
from futdados.model.poisson import fit
from futdados.model.predict import features_for
from futdados.pipeline import post_round, predict_round

AVISO = "Projeção estatística baseada em dados históricos. Não é recomendação de aposta."
FORBIDDEN = ["palpite", "aposte", "favorito", "dica", "odds"]


def _league(season, start, rng, finished=True):
    teams = [f"t{i}" for i in range(6)]
    rows, day, k = [], start, 0
    pairs = [(h, a) for h in teams for a in teams if h != a]
    for k, (h, a) in enumerate(pairs):
        day = start + pd.Timedelta(days=k // 3 * 4)
        rows.append(dict(season=season, home_id=h, away_id=a, round=k // 3 + 1,
                         kickoff_utc=day.strftime("%Y-%m-%dT%H:%M:%SZ"),
                         home_goals=int(rng.poisson(1.5)) if finished else None,
                         away_goals=int(rng.poisson(1.0)) if finished else None,
                         status="FINISHED" if finished else "SCHEDULED",
                         home_coach=None, away_coach=None, source="teste", ext_id=None))
    return rows


@pytest.fixture
def env(tmp_path):
    cfg = load_config()
    cfg["paths"].update(db=str(tmp_path / "t.sqlite"), weights=str(tmp_path / "w.json"),
                        videos=str(tmp_path / "videos"), coach_changes=str(tmp_path / "none.csv"))
    cfg["model"].update(train_first_season=2020, bootstrap=0)
    cfg["simulation"]["n_sims"] = 300
    cfg["output"]["focus_team"] = "t0"
    rng = np.random.default_rng(3)
    repo = Repository(cfg["paths"]["db"])
    for s in (2020, 2021, 2022):
        repo.upsert_matches(_league(s, pd.Timestamp(f"{s}-04-01", tz="UTC"), rng))
    repo.upsert_matches(_league(2026, pd.Timestamp("2026-04-01", tz="UTC"), rng, finished=False))
    feat = features_for(repo, cfg, 365)
    fit(feat[feat.season < 2026], cfg["model"], 365, bootstrap=0).save(cfg["paths"]["weights"])
    return repo, cfg


def test_round_pipeline_end_to_end(env):
    repo, cfg = env
    now = pd.Timestamp("2026-03-30", tz="UTC")
    path, info = predict_round(repo, cfg, 2026, now=now)
    assert info["round"] == 1 and info["registered"] == 3
    doc = json.loads(path.read_text(encoding="utf-8"))
    assert doc["aviso"] == AVISO and doc["versao_modelo"] and doc["fontes"] and doc["gerado_em"]
    assert doc["atribuicao"] == "Football data provided by the Football-Data.org API"
    jogo = doc["jogos"][0]
    probs = jogo["probabilidade_estimada"]
    assert sum(probs.values()) == pytest.approx(1, abs=1e-3)
    efeito = sum(f["mandante"]["efeito_gols"] for f in jogo["fatores"])
    assert jogo["gols_base"] + efeito == pytest.approx(jogo["gols_esperados"]["mandante"], abs=0.01)
    text = path.read_text(encoding="utf-8").lower()
    assert not any(word in text for word in FORBIDDEN)

    # não dá para alterar o registro
    with pytest.raises(sqlite3.DatabaseError):
        repo.conn.execute("UPDATE predictions SET p_home = 1")

    # resultados chegam e o pós-rodada compara
    m = repo.matches(2026)
    r1 = m[m["round"] == 1].copy()
    r1["home_goals"], r1["away_goals"], r1["status"] = 2, 0, "FINISHED"
    r1["kickoff_utc"] = r1.kickoff_utc.dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    repo.upsert_matches(r1.to_dict("records"))
    path2, info2 = post_round(repo, cfg, 2026, 1)
    doc2 = json.loads(path2.read_text(encoding="utf-8"))
    assert doc2["aviso"] == AVISO and info2["n"] == 3
    assert 0 <= doc2["brier_rodada"] <= 2
    assert doc2["time_foco"]["variacao_chances"]["titulo"] is not None
    assert repo.verify_prediction_chain()


def test_started_games_are_not_registered(env):
    repo, cfg = env
    now = pd.Timestamp("2026-04-01T00:00:01Z")  # rodada 1 começou à 00:00
    _, info = predict_round(repo, cfg, 2026, round_=1, now=now)
    assert info["registered"] == 0 and len(info["skipped"]) == 3


def test_postponed_game_is_handled_separately(env):
    """Rodadas 1 e 2 disputadas, menos um jogo da rodada 1, remarcado para depois."""
    repo, cfg = env
    m = repo.matches(2026)
    m["kickoff_utc"] = m.kickoff_utc.dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    early = m[m["round"] <= 2].copy()
    early["home_goals"], early["away_goals"], early["status"] = 1, 1, "FINISHED"
    late = early.iloc[[0]].copy()  # jogo da rodada 1 adiado
    late["home_goals"], late["away_goals"], late["status"] = None, None, "TIMED"
    late["kickoff_utc"] = "2026-05-20T22:00:00Z"
    repo.upsert_matches(early.iloc[1:].to_dict("records") + late.to_dict("records"))

    now = pd.Timestamp("2026-04-07", tz="UTC")
    path, info = predict_round(repo, cfg, 2026, now=now)
    assert info["round"] == 3                    # não a rodada 1 do adiado
    assert info["games"] == 3 and info["postponed"] == 1 and info["registered"] == 4
    doc = json.loads(path.read_text(encoding="utf-8"))
    assert all(not j["adiado"] for j in doc["jogos"])
    assert len(doc["adiados"]) == 1 and doc["adiados"][0]["adiado"] is True
    assert doc["adiados"][0]["rodada"] == 1
    reg = repo.predictions(2026)
    adiado = reg[(reg.home_id == late.iloc[0].home_id) & (reg.away_id == late.iloc[0].away_id)]
    assert len(adiado) == 1 and json.loads(adiado.iloc[0].payload)["adiado"] is True

    # rodar de novo não duplica nada no registro imutável
    _, again = predict_round(repo, cfg, 2026, now=now)
    assert again["registered"] == 0 and len(repo.predictions(2026)) == 4
    # --round aceita a rodada do adiado: cita a previsão existente
    _, r1 = predict_round(repo, cfg, 2026, round_=1, now=now)
    assert r1["round"] == 1 and r1["games"] == 1 and r1["registered"] == 0
    # com repeat=True grava uma nova sem apagar a antiga
    _, rep = predict_round(repo, cfg, 2026, round_=1, now=now + pd.Timedelta(hours=1), repeat=True)
    assert rep["registered"] == 1 and len(repo.predictions(2026)) == 5
    assert repo.verify_prediction_chain()


def test_export_site_writes_derived_data_only(env, tmp_path):
    from futdados.site_export import export_site

    repo, cfg = env
    out = export_site(repo, cfg, 2026, n_sims=200, out_dir=tmp_path / "data")
    names = {p.stem for p in out.glob("*.json")}
    assert names == {"meta", "tabela", "rodada", "simulador", "modelo", "financas"}
    for p in out.glob("*.json"):
        doc = json.loads(p.read_text(encoding="utf-8"))
        assert doc["aviso"] == AVISO
        assert doc["atribuicao"] == "Football data provided by the Football-Data.org API"
        assert doc["gerado_em"]
        assert not any(w in p.read_text(encoding="utf-8").lower() for w in FORBIDDEN)
    sim = json.loads((out / "simulador.json").read_text(encoding="utf-8"))
    # jogos disputados entram só agregados (tabela atual e confronto direto), nunca como lista
    assert set(sim["atual"]) == {"pts", "j", "v", "gp", "gc"}
    assert len(sim["restantes"]) == 30 and "jogos" not in sim
    rodada = json.loads((out / "rodada.json").read_text(encoding="utf-8"))
    assert rodada["rodada"] == 1 and "adiados" in rodada

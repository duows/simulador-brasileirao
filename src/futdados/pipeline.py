"""Orquestração: projeção da tabela, previsões da rodada e pós-rodada.

Todas as saídas para vídeo passam por `video_json`, que acrescenta fontes, versão do
modelo, data de geração e o campo obrigatório "aviso".
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from .db import Repository, utc_now
from .model.poisson import Weights
from .model.predict import coach_extra, match_payload
from .model.features import build_features
from .simulate.montecarlo import simulate_season
from .teams import display_name

SOURCES = [
    {"nome": "football-data.org (API v4, competição BSA)", "url": "https://www.football-data.org",
     "uso": "jogos e classificação da temporada corrente"},
    {"nome": "Brasileirao_Dataset, de Adão Duque", "url": "https://github.com/adaoduque/Brasileirao_Dataset",
     "uso": "resultados históricos 2003-2025"},
]

LINGUAGEM = ("Os números são probabilidades estimadas pelo modelo e projeções. "
             "Descrevem o que é provável com base no desempenho recente e no histórico; "
             "não dizem o que vai acontecer.")


def load_weights(cfg) -> Weights:
    path = cfg["paths"]["weights"]
    if not Path(path).exists():
        raise FileNotFoundError("Pesos não encontrados. Rode `futdados fit` antes.")
    return Weights.load(path)


def video_json(cfg, w: Weights, tipo: str, dados: dict, slug: str) -> Path:
    doc = {
        "tipo": tipo,
        "gerado_em": utc_now(),
        "versao_modelo": w.model_version,
        "meia_vida_dias": w.half_life_days,
        "aviso": cfg["output"]["aviso"],
        "linguagem": LINGUAGEM,
        "fontes": SOURCES,
        **dados,
    }
    out = Path(cfg["paths"]["videos"]) / f"{slug}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def season_features(repo: Repository, cfg, w: Weights, season: int,
                    as_of_round: int | None = None) -> pd.DataFrame:
    """Fatores de todos os jogos da temporada. Com `as_of_round`, esconde os resultados
    das rodadas seguintes (para reconstituir o que o modelo veria naquela data)."""
    matches = repo.matches()
    if as_of_round is not None:
        hide = (matches.season == season) & (matches["round"] > as_of_round)
        matches.loc[hide, ["home_goals", "away_goals"]] = np.nan
        matches.loc[hide, "status"] = "SCHEDULED"
        # ignora tudo que veio depois da temporada (sem vazamento)
        matches = matches[matches.season <= season]
    feat = build_features(matches, cfg["model"], coach_extra(repo, cfg["paths"]["coach_changes"]),
                          half_life_days=w.half_life_days)
    return feat[feat.season == season].reset_index(drop=True)


def last_complete_round(feat: pd.DataFrame) -> int:
    done = feat.groupby("round").apply(lambda g: (g.status == "FINISHED").all(), include_groups=False)
    complete = done[done].index
    return int(complete.max()) if len(complete) else 0


# ------------------------------------------------------------------- projeção
def project(repo: Repository, cfg, season: int, target_round: int | None = None,
            as_of_round: int | None = None, n_sims: int | None = None,
            record: bool = True) -> tuple[pd.DataFrame, dict]:
    w = load_weights(cfg)
    feat = season_features(repo, cfg, w, season, as_of_round)
    max_round = int(feat["round"].max())
    target = max_round if target_round is None else int(target_round)
    based_on = last_complete_round(feat)
    table = simulate_season(feat, w, cfg, target, n_sims=n_sims)
    meta = {"season": season, "based_on_round": based_on, "target_round": target,
            "model_version": w.model_version, "n_sims": int(n_sims or cfg["simulation"]["n_sims"]),
            "max_round": max_round}
    if record:
        repo.insert_projection(meta, table)
    return table, meta


def projection_json(cfg, table: pd.DataFrame, meta: dict) -> Path:
    w = load_weights(cfg)
    linhas = []
    for i, r in enumerate(table.itertuples(), start=1):
        linhas.append({
            "posicao_projetada": i,
            "time": {"id": r.team_id, "nome": display_name(r.team_id)},
            "jogos": int(r.jogos), "pontos_atuais": int(r.pontos_atuais), "saldo_atual": int(r.saldo_atual),
            "pontos_esperados": round(float(r.exp_points), 1),
            "faixa_posicao": {"p10": int(round(r.pos_p10)), "mediana": int(round(r.pos_p50)),
                              "p90": int(round(r.pos_p90))},
            "pontos_esperados_fim": round(float(r.exp_points_final), 1),
            "chance_titulo": round(float(r.p_titulo), 4),
            "chance_g4": round(float(r.p_g4), 4),
            "chance_g6": round(float(r.p_g6), 4),
            "chance_rebaixamento": round(float(r.p_rebaixamento), 4),
        })
    titulo = (f"Tabela projetada depois da rodada {meta['target_round']}"
              + (" (fim do campeonato)" if meta["target_round"] == meta["max_round"] else ""))
    dados = {
        "titulo": titulo,
        "temporada": meta["season"],
        "resultados_reais_ate_rodada": meta["based_on_round"],
        "rodada_alvo": meta["target_round"],
        "simulacoes": meta["n_sims"],
        "metodo": ("Simulação Monte Carlo do restante do campeonato a partir da matriz de placares de "
                   "cada jogo. Ordem pelos pontos esperados; a faixa de posição vai do percentil 10 ao 90. "
                   "As chances de título, G4, G6 e rebaixamento referem-se ao fim do campeonato."),
        "criterios_desempate": cfg["simulation"]["tiebreakers"],
        "tabela": linhas,
    }
    slug = f"tabela-projetada-{meta['season']}-apos-r{meta['target_round']:02d}-base-r{meta['based_on_round']:02d}"
    return video_json(cfg, w, "tabela_projetada", dados, slug)

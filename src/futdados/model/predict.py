"""Previsão por jogo com a decomposição dos fatores (o que vai para o JSON do vídeo)."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from ..teams import display_name
from .features import FEATURES, build_features
from .poisson import Weights, decompose, expected_goals, score_matrix

FACTOR_LABEL = {
    "ataque": "Força de ataque (longo prazo)",
    "defesa_adversario": "Defesa do adversário (longo prazo)",
    "mando": "Mando de campo",
    "forma": "Forma recente (últimos 5 jogos)",
    "descanso": "Dias de descanso",
    "meio_de_semana": "Jogo no meio da semana",
    "tecnico_novo": "Troca recente de técnico",
}


def coach_extra(repo, path: str) -> pd.DataFrame:
    """Trocas de técnico vindas dos snapshots da API e do CSV manual."""
    frames = []
    snaps = repo.coach_snapshots()
    if not snaps.empty:
        snaps = snaps.sort_values("fetched_at")
        changed = snaps[snaps.duplicated("team_id", keep="first")]  # 1º snapshot não é troca
        frames.append(pd.DataFrame({"team_id": changed.team_id, "start": changed.fetched_at}))
    try:
        manual = pd.read_csv(path)
        if not manual.empty:
            frames.append(pd.DataFrame({"team_id": manual.team_id, "start": manual.start_date}))
    except FileNotFoundError:
        pass
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=["team_id", "start"])


def features_for(repo, cfg: dict, half_life: float) -> pd.DataFrame:
    return build_features(repo.matches(), cfg["model"], coach_extra(repo, cfg["paths"]["coach_changes"]),
                          half_life_days=half_life)


def _side(row: pd.Series, side: str) -> np.ndarray:
    return row[[f"{c}_{side}" for c in FEATURES]].to_numpy(float)


def match_payload(row: pd.Series, w: Weights, max_goals: int = 10) -> dict:
    """Probabilidades, gols esperados e fatores de um jogo (motor de produção, se houver)."""
    if "lh_prod" in row and pd.notna(row.get("lh_prod")):
        from .production import payload

        p = payload(row, 0.0, max_goals)
        return {
            "mandante": {"id": row["home_id"], "nome": display_name(row["home_id"])},
            "visitante": {"id": row["away_id"], "nome": display_name(row["away_id"])},
            "rodada": None if pd.isna(row["round"]) else int(row["round"]),
            "inicio_utc": pd.Timestamp(row["kickoff_utc"]).strftime("%Y-%m-%dT%H:%M:%SZ"),
            **p,
            "contexto": {
                "pontos_por_jogo_ultimos": {"mandante": round(float(row["raw_ppg_h"]), 2),
                                            "visitante": round(float(row["raw_ppg_a"]), 2)},
                "elo": None if pd.isna(row.get("elo_h")) else {"mandante": round(float(row["elo_h"])),
                                                               "visitante": round(float(row["elo_a"]))},
            },
        }
    lh, la = (float(v[0]) for v in expected_goals(row.to_frame().T, w))
    m = score_matrix(lh, la, w.rho, max_goals)
    p_home, p_draw, p_away = float(np.tril(m, -1).sum()), float(np.trace(m)), float(np.triu(m, 1).sum())
    base = float(row["mu"]) * math.exp(w.intercept)
    dec_h = decompose(_side(row, "h"), base, w)
    dec_a = decompose(_side(row, "a"), base, w)
    i, j = np.unravel_index(np.argmax(m), m.shape)
    fatores = []
    for f in FEATURES:
        fatores.append({
            "fator": f,
            "rotulo": FACTOR_LABEL[f],
            "peso": round(dec_h[f]["peso"], 4),
            "mandante": {"valor": round(dec_h[f]["valor"], 3),
                         "efeito_gols": round(dec_h[f]["gols"], 3),
                         "multiplicador": round(dec_h[f]["multiplicador"], 3)},
            "visitante": {"valor": round(dec_a[f]["valor"], 3),
                          "efeito_gols": round(dec_a[f]["gols"], 3),
                          "multiplicador": round(dec_a[f]["multiplicador"], 3)},
        })
    return {
        "mandante": {"id": row["home_id"], "nome": display_name(row["home_id"])},
        "visitante": {"id": row["away_id"], "nome": display_name(row["away_id"])},
        "rodada": None if pd.isna(row["round"]) else int(row["round"]),
        "inicio_utc": pd.Timestamp(row["kickoff_utc"]).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "gols_esperados": {"mandante": round(lh, 3), "visitante": round(la, 3)},
        "gols_base": round(base, 3),
        "probabilidade_estimada": {"mandante": round(p_home, 4), "empate": round(p_draw, 4),
                                   "visitante": round(p_away, 4)},
        "placar_mais_provavel": {"mandante": int(i), "visitante": int(j),
                                 "probabilidade": round(float(m[i, j]), 4)},
        "fatores": fatores,
        "contexto": {
            "pontos_por_jogo_ultimos": {"mandante": round(float(row["raw_ppg_h"]), 2),
                                        "visitante": round(float(row["raw_ppg_a"]), 2),
                                        "jogos_considerados": [int(row["raw_nform_h"]), int(row["raw_nform_a"])]},
            "dias_descanso": {"mandante": float(row["raw_rest_h"]), "visitante": float(row["raw_rest_a"])},
            "tecnico_novo": {"mandante": bool(row["raw_newcoach_h"]), "visitante": bool(row["raw_newcoach_a"])},
        },
    }

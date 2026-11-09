"""Melhor time do Cartola para um orçamento, pela pontuação esperada (programação linear inteira).

Variáveis: x_i (atleta escalado), c_i (capitão), f_k (esquema tático escolhido).
Maximiza  Σ E_i·x_i + (multiplicador_capitão − 1)·Σ E_i·c_i
sujeito a Σ preço_i·x_i ≤ orçamento, um esquema, nº de atletas por posição = o do esquema,
um capitão entre os escalados (técnico não pode ser capitão). Solução exata (scipy.milp/HiGHS).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.optimize import Bounds, LinearConstraint, milp

POSITIONS = ["gol", "lat", "zag", "mei", "ata", "tec"]


def best_team(players: pd.DataFrame, budget: float, schemes: dict[str, dict[str, int]],
              captain_mult: float = 1.5, only: str | None = None) -> dict:
    """players: colunas atleta_id, apelido, posicao, preco, esperado (> 0 para entrar)."""
    p = players[players.esperado > 0].reset_index(drop=True)
    names = [only] if only else list(schemes)
    n, k = len(p), len(names)
    # vetor: [x (n), c (n), f (k)]
    E = p.esperado.to_numpy(float)
    obj = -np.concatenate([E, (captain_mult - 1) * E, np.zeros(k)])
    A, lo, hi = [], [], []
    # orçamento
    A.append(np.concatenate([p.preco.to_numpy(float), np.zeros(n + k)])); lo.append(-np.inf); hi.append(budget)
    # um esquema
    A.append(np.concatenate([np.zeros(2 * n), np.ones(k)])); lo.append(1); hi.append(1)
    # atletas por posição = esquema escolhido
    for pos in POSITIONS:
        row = np.concatenate([(p.posicao == pos).astype(float).to_numpy(), np.zeros(n),
                              -np.array([schemes[s][pos] for s in names], float)])
        A.append(row); lo.append(0); hi.append(0)
    # um capitão, escalado, e não técnico
    A.append(np.concatenate([np.zeros(n), np.ones(n), np.zeros(k)])); lo.append(1); hi.append(1)
    cap_rows = np.hstack([-np.eye(n), np.eye(n), np.zeros((n, k))])
    A.extend(cap_rows); lo.extend([-np.inf] * n); hi.extend([0] * n)
    ub = np.ones(2 * n + k)
    ub[n:2 * n] = (p.posicao != "tec").astype(float).to_numpy()
    res = milp(obj, constraints=LinearConstraint(np.array(A), lo, hi), integrality=np.ones(2 * n + k),
               bounds=Bounds(np.zeros(2 * n + k), ub))
    if not res.success:
        return {"ok": False, "motivo": "Orçamento insuficiente para montar um time completo com os atletas disponíveis."}
    x = res.x[:n] > 0.5
    c = res.x[n:2 * n] > 0.5
    scheme = names[int(np.argmax(res.x[2 * n:]))]
    team = p[x].assign(capitao=c[x]).copy()
    team["pos_ordem"] = team.posicao.map({q: i for i, q in enumerate(POSITIONS)})
    team = team.sort_values(["pos_ordem", "esperado"], ascending=[True, False]).drop(columns="pos_ordem")
    total = float(team.esperado.sum() + (captain_mult - 1) * team[team.capitao].esperado.sum())
    return {"ok": True, "esquema": scheme, "custo": float(team.preco.sum()), "orcamento": budget,
            "pontos_esperados": total, "time": team}

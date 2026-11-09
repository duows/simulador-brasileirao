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
              captain_mult: float = 1.5, only: str | None = None, reserves: dict | None = None,
              vice: bool = False) -> dict:
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
    res = {"ok": True, "esquema": scheme, "custo": float(team.preco.sum()), "orcamento": budget,
           "pontos_esperados": total, "time": team, "reservas": pd.DataFrame()}
    # vice-capitão: herda o ×multiplicador se o capitão não jogar
    vice = vice_captain(team) if vice and "p_jogar" in team else None
    vice_value = 0.0
    if vice is not None:
        cap = team[team.capitao].iloc[0]
        vice_value = (captain_mult - 1) * (1 - float(cap.p_jogar)) * float(vice.esperado)
        res["vice"] = int(vice.atleta_id)
        res["valor_vice"] = vice_value
    if reserves and reserves.get("ativo"):
        rv = add_reserves(team, players, reserves)
        if len(rv) and "previsto_se_jogar" in rv:
            sim = bench_simulation(team, rv, reserves.get("desvio_por_posicao"), captain_mult=captain_mult)
            rv["valor_reserva"] = rv.posicao.map(lambda q: sim[q]["banco"])
            rv["valor_luxo"] = rv.posicao.map(lambda q: sim[q]["luxo"])
            rv["luxo"] = False
            if reserves.get("reserva_de_luxo", True):
                rv.loc[rv.valor_luxo.idxmax(), "luxo"] = True
        res["reservas"] = rv
        lux = float(rv[rv.luxo].valor_luxo.sum()) if len(rv) and "luxo" in rv else 0.0
        res["valor_reservas"] = (float(rv.valor_reserva.sum()) if len(rv) else 0.0) + lux
        res["pontos_esperados_com_reservas"] = total + vice_value + res["valor_reservas"]
    return res


RESERVE_POSITIONS = ["gol", "lat", "zag", "mei", "ata"]


def add_reserves(team: pd.DataFrame, players: pd.DataFrame, rules: dict) -> pd.DataFrame:
    """Um reserva por posição (técnico não tem), escolhido depois dos titulares.

    Regra (configurável, TODO confirmar no regulamento do Cartola): o reserva não gasta cartoletas,
    mas custa no máximo o mesmo que o titular mais barato da posição. Ele só entra se um titular da
    posição não jogar, então vale chance(algum titular faltar) × pontuação esperada do reserva.
    """
    pool = players[(players.esperado > 0) & ~players.atleta_id.isin(team.atleta_id)]
    rows = []
    for pos in RESERVE_POSITIONS:
        starters = team[team.posicao == pos]
        if starters.empty:  # esquema sem a posição (ex.: 3-5-2 sem laterais): não há a quem substituir
            continue
        cap = starters.preco.min() if rules.get("preco_maximo") == "titular_mais_barato" else np.inf
        cand = pool[(pool.posicao == pos) & (pool.preco <= cap + 1e-9)]
        if cand.empty:
            continue
        q = 1 - float(np.prod(starters.p_jogar.to_numpy(float))) if "p_jogar" in starters else 0.0
        best = cand.loc[cand.esperado.idxmax()].copy()
        best["chance_de_entrar"] = q
        best["valor_reserva"] = q * float(best.esperado)
        rows.append(best)
    return pd.DataFrame(rows)


DEFAULT_SD = {"gol": 4.0, "lat": 4.0, "zag": 3.6, "mei": 3.7, "ata": 4.4}


def vice_captain(team: pd.DataFrame) -> pd.Series | None:
    """Vice: o melhor titular de linha depois do capitão; herda a braçadeira se o capitão não jogar."""
    cand = team[(team.posicao != "tec") & ~team.capitao]
    return None if cand.empty else cand.loc[cand.esperado.idxmax()]


def bench_simulation(team: pd.DataFrame, reserves: pd.DataFrame, sd: dict | None = None, n: int = 4000,
                     seed: int = 0, captain_mult: float = 1.5) -> dict[str, dict[str, float]]:
    """Valor esperado do banco por posição, simulando quem joga e quanto pontua.

    Regras: o reserva entra no lugar de um titular da posição que não jogou, se o reserva jogou e
    pontuou mais que zero (banco); se o capitão está entre os ausentes, ele tem prioridade e o
    reserva herda o multiplicador (leitura da regra de prioridade, a confirmar).
    Se ele não foi usado no banco e for o Reserva de Luxo, substitui o
    titular da posição que pontuou menos, se pontuou mais que ele. Pontos ~ Normal(previsto, desvio
    da posição); jogar ~ Bernoulli(chance de jogar).
    """
    sd = {**DEFAULT_SD, **(sd or {})}
    rng = np.random.default_rng(seed)
    out = {}
    for r in reserves.itertuples():
        st = team[team.posicao == r.posicao]
        s_play = rng.random((n, len(st))) < st.p_jogar.to_numpy(float)
        s_pts = rng.normal(st.previsto_se_jogar.to_numpy(float), sd.get(r.posicao, 4.0), (n, len(st))) * s_play
        r_play = rng.random(n) < r.p_jogar
        r_pts = rng.normal(r.previsto_se_jogar, sd.get(r.posicao, 4.0), n) * r_play
        bench_used = (~s_play).any(axis=1) & r_play & (r_pts > 0)
        bench_gain = np.where(bench_used, r_pts, 0.0)
        if "capitao" in st and st.capitao.any():  # capitão ausente tem prioridade: o reserva herda o ×mult
            cap_missing = ~s_play[:, np.flatnonzero(st.capitao.to_numpy())[0]]
            bench_gain = bench_gain + np.where(bench_used & cap_missing, (captain_mult - 1) * r_pts, 0.0)
        low = np.where(s_play, s_pts, np.inf).min(axis=1)  # titular que jogou e pontuou menos
        lux = ~bench_used & r_play & np.isfinite(low) & (r_pts > low)
        lux_gain = np.where(lux, r_pts - np.where(np.isfinite(low), low, 0), 0.0)
        out[r.posicao] = {"banco": float(bench_gain.mean()), "luxo": float(lux_gain.mean())}
    return out

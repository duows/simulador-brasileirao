"""Simulação Monte Carlo do restante do campeonato.

Cada jogo que falta é sorteado da sua matriz de placares (a mesma que gera as
probabilidades). A tabela NÃO é montada com o resultado mais provável de cada jogo:
isso ignoraria os empates e distorceria os pontos. Usamos a distribuição inteira e
reportamos pontos esperados, percentis de posição e chances por zona.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..model.poisson import Weights, expected_goals, score_matrix

STAT_KEYS = {"points": "pts", "wins": "w", "goal_difference": "gd", "goals_for": "gf"}
UNAVAILABLE = {"red_cards", "yellow_cards"}  # não temos cartões: caem no sorteio


def rank(stats: dict[str, np.ndarray], h2h: np.ndarray, criteria: list[str],
         rng: np.random.Generator) -> np.ndarray:
    """Posição (1 = líder) de cada time em cada simulação. Arrays (N, T)."""
    n, t = stats["pts"].shape
    if "head_to_head" in criteria:
        before = criteria[: criteria.index("head_to_head")]
    else:
        before = criteria
    before = [STAT_KEYS[c] for c in before if c in STAT_KEYS]
    rand = rng.random((n, t))  # sorteio (e cartões indisponíveis)
    keys = [rand] + [-stats[k] for k in reversed(before)]
    order = np.lexsort(keys, axis=-1)  # (N, T): índice do time por colocação

    if "head_to_head" in criteria and t > 1:
        rows = np.arange(n)[:, None]
        sorted_keys = np.stack([stats[k][rows, order] for k in before], axis=-1)  # (N,T,K)
        tie = np.all(sorted_keys[:, 1:] == sorted_keys[:, :-1], axis=-1)  # (N, T-1)
        pad = np.zeros((n, 1), bool)
        tie_prev = np.hstack([pad, tie[:, :-1]])   # empate da posição p com p-1
        tie_next = np.hstack([tie[:, 1:], pad])    # empate de p+1 com p+2
        pair = tie & ~tie_prev & ~tie_next          # grupo de exatamente dois
        s_idx, p_idx = np.nonzero(pair)
        a, b = order[s_idx, p_idx], order[s_idx, p_idx + 1]
        swap = h2h[s_idx, b, a] > h2h[s_idx, a, b]
        order[s_idx[swap], p_idx[swap]] = b[swap]
        order[s_idx[swap], p_idx[swap] + 1] = a[swap]

    pos = np.empty_like(order)
    np.put_along_axis(pos, order, np.arange(1, t + 1)[None, :].repeat(n, 0), axis=-1)
    return pos


def _sample_scores(lh, la, rho, max_goals, n, rng):
    m = score_matrix(lh, la, rho, max_goals).ravel()
    idx = np.searchsorted(np.cumsum(m), rng.random(n) * m.sum())
    idx = np.minimum(idx, len(m) - 1)
    return idx // (max_goals + 1), idx % (max_goals + 1)


POSTPONED_STATUS = {"POSTPONED", "SUSPENDED"}


def round_plan(season_feat: pd.DataFrame) -> tuple[int | None, pd.Series]:
    """Próxima rodada "cheia" e máscara dos jogos adiados.

    Próxima rodada = a primeira rodada em que NENHUM jogo foi disputado. Adiado = jogo ainda
    por disputar de uma rodada anterior a ela (a rodada dele já andou sem ele), ou com status
    POSTPONED/SUSPENDED na API. Assim um jogo atrasado da rodada 21 não "vira" a próxima rodada.
    """
    pending = season_feat.status != "FINISHED"
    if not pending.any():
        return None, pending & False
    all_pending = pending.groupby(season_feat["round"]).all()
    full = all_pending[all_pending].index
    nxt = int(full.min()) if len(full) else None
    behind = season_feat["round"] < nxt if nxt is not None else pd.Series(True, index=season_feat.index)
    postponed = pending & (behind | season_feat.status.isin(POSTPONED_STATUS))
    return nxt, postponed


def split_remaining(season_feat: pd.DataFrame, w: Weights):
    """Separa jogos disputados e restantes e calcula os gols esperados dos restantes.

    Forma e técnico novo só valem para a próxima rodada e para os adiados (jogos próximos);
    nas rodadas seguintes ficam neutros.
    """
    played = season_feat[(season_feat.status == "FINISHED") & season_feat.home_goals.notna()]
    todo = season_feat.drop(played.index).copy()
    if todo.empty:
        return played, todo, np.array([]), np.array([])
    nxt, postponed = round_plan(season_feat)
    nxt = todo["round"].min() if nxt is None else nxt
    later = (todo["round"] > nxt) & ~postponed.loc[todo.index]
    for c in ("forma", "tecnico_novo"):
        todo.loc[later, [f"{c}_h", f"{c}_a"]] = 0.0
    lh, la = expected_goals(todo, w)
    if "lh_prod" in todo.columns and todo.lh_prod.notna().all():  # motor de produção (forças por time)
        lh, la = todo.lh_prod.to_numpy(float), todo.la_prod.to_numpy(float)
    return played, todo, lh, la


def simulate_season(season_feat: pd.DataFrame, w: Weights, cfg: dict, target_round: int,
                    n_sims: int | None = None, seed: int | None = None) -> pd.DataFrame:
    """Projeta a tabela depois da rodada `target_round` e as chances finais.

    `season_feat`: linhas de build_features de UMA temporada (jogos disputados e não).
    """
    scfg, mcfg = cfg["simulation"], cfg["model"]
    n = int(n_sims or scfg["n_sims"])
    rng = np.random.default_rng(scfg["seed"] if seed is None else seed)
    teams = sorted(set(season_feat.home_id) | set(season_feat.away_id))
    tix = {t: i for i, t in enumerate(teams)}
    T = len(teams)

    played, todo, lh, la = split_remaining(season_feat, w)

    def blank():
        return {k: np.zeros((n, T)) for k in ("pts", "w", "gf", "ga")}

    def add(st, h2h, hi, ai, hg, ag):
        hp = np.where(hg > ag, 3, np.where(hg == ag, 1, 0))
        ap = np.where(ag > hg, 3, np.where(hg == ag, 1, 0))
        st["pts"][:, hi] += hp
        st["pts"][:, ai] += ap
        st["w"][:, hi] += hg > ag
        st["w"][:, ai] += ag > hg
        st["gf"][:, hi] += hg
        st["ga"][:, hi] += ag
        st["gf"][:, ai] += ag
        st["ga"][:, ai] += hg
        h2h[:, hi, ai] += hp
        h2h[:, ai, hi] += ap

    final, at_x = blank(), blank()
    h2h_final = np.zeros((n, T, T), np.int16)
    h2h_x = np.zeros((n, T, T), np.int16)
    for r in played.itertuples():
        hg, ag = np.full(n, int(r.home_goals)), np.full(n, int(r.away_goals))
        add(final, h2h_final, tix[r.home_id], tix[r.away_id], hg, ag)
        add(at_x, h2h_x, tix[r.home_id], tix[r.away_id], hg, ag)
    for k, r in enumerate(todo.itertuples()):
        hg, ag = _sample_scores(lh[k], la[k], w.rho, mcfg["max_goals"], n, rng)
        add(final, h2h_final, tix[r.home_id], tix[r.away_id], hg, ag)
        if r.round <= target_round:
            add(at_x, h2h_x, tix[r.home_id], tix[r.away_id], hg, ag)

    crit = scfg["tiebreakers"]
    for st in (final, at_x):
        st["gd"] = st["gf"] - st["ga"]
    pos_final = rank(final, h2h_final, crit, rng)
    pos_x = rank(at_x, h2h_x, crit, rng)

    zones = scfg["zones"]
    cur = {k: np.zeros(T) for k in ("pts", "j", "w", "gf", "ga")}
    for r in played.itertuples():
        hi, ai = tix[r.home_id], tix[r.away_id]
        hg, ag = int(r.home_goals), int(r.away_goals)
        cur["j"][[hi, ai]] += 1
        cur["pts"][hi] += 3 if hg > ag else (1 if hg == ag else 0)
        cur["pts"][ai] += 3 if ag > hg else (1 if hg == ag else 0)
        cur["w"][hi] += hg > ag
        cur["w"][ai] += ag > hg
        cur["gf"][hi] += hg
        cur["ga"][hi] += ag
        cur["gf"][ai] += ag
        cur["ga"][ai] += hg

    def zone(pos, z):
        lo, hi = zones[z]
        return ((pos >= lo) & (pos <= hi)).mean(axis=0)

    table = pd.DataFrame({
        "team_id": teams,
        "jogos": cur["j"].astype(int),
        "pontos_atuais": cur["pts"].astype(int),
        "saldo_atual": (cur["gf"] - cur["ga"]).astype(int),
        "exp_points": at_x["pts"].mean(axis=0),
        "pos_p10": np.percentile(pos_x, 10, axis=0),
        "pos_p50": np.percentile(pos_x, 50, axis=0),
        "pos_p90": np.percentile(pos_x, 90, axis=0),
        "exp_points_final": final["pts"].mean(axis=0),
        "p_titulo": zone(pos_final, "titulo"),
        "p_g4": zone(pos_final, "g4"),
        "p_g6": zone(pos_final, "g6"),
        "p_rebaixamento": zone(pos_final, "rebaixamento"),
    })
    # distribuição da posição final: dist[k] = P(terminar em k+1º)
    counts = np.stack([(pos_final == k).mean(axis=0) for k in range(1, T + 1)], axis=1)
    table["dist"] = [counts[i].tolist() for i in range(T)]
    return table.sort_values(["exp_points", "pontos_atuais"], ascending=False).reset_index(drop=True)

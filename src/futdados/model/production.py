"""Motor de produção dos jogos: forças por time (gols esperados) + Elo, combinados em conjunto.

Escolhido pelo placar do backtest (docs/DECISIONS.md D23/D26): o Poisson de 7 fatores perdia do
Elo puro em todas as temporadas; forças por time empatam com o Elo e o conjunto dos dois é o
melhor. Este módulo:

- `fit_strengths`: ataque e defesa por time com prior gaussiano (MAP), mando comum e média da
  liga, com decaimento temporal, usando só jogos antes de `before`. Intervalo por Laplace.
- `elo_now`: rating Elo atual de cada time e a regressão ordinal (diferença de Elo → V/E/D).
- `attach`: acrescenta a um DataFrame de jogos pendentes os gols esperados (forças), as
  probabilidades de cada modelo e as do conjunto, prontos para rodada, simulação e Cartola.

Gols esperados = exp(média + mando + ataque do time + defesa do adversário): cada termo é um
fator explicável em linguagem simples.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from ..ratings.elo import EloParams, fit_ordinal, ordinal_probs, outcome, run_elo
from .poisson import outcome_probs, score_matrix

FACTOR_LABELS = {"media_liga": "Média de gols da liga", "mando": "Mando de campo",
                 "ataque": "Ataque do time", "defesa_adversario": "Defesa do adversário"}


def fit_strengths(matches: pd.DataFrame, before: pd.Timestamp, seasons_back: int = 3, half_life: float = 365,
                  prior_sd: float = 0.3) -> dict:
    hist = matches[(matches.status == "FINISHED") & matches.home_goals.notna()].copy()
    hist["kickoff_utc"] = pd.to_datetime(hist.kickoff_utc, utc=True)
    season_now = int(hist[hist.kickoff_utc < before].season.max())
    train = hist[(hist.kickoff_utc < before) & (hist.season >= season_now - seasons_back)]
    teams = sorted(set(train.home_id) | set(train.away_id) | set(matches[matches.season == matches.season.max()].home_id))
    ix = {t: i for i, t in enumerate(teams)}
    T = len(teams)
    hi, ai = train.home_id.map(ix).to_numpy(), train.away_id.map(ix).to_numpy()
    hg, ag = train.home_goals.to_numpy(float), train.away_goals.to_numpy(float)
    wt = 0.5 ** ((before - train.kickoff_utc).dt.total_seconds().to_numpy() / 86400 / half_life)

    def nll(th):
        atk, dfn, mu, home = th[:T], th[T:2 * T], th[2 * T], th[2 * T + 1]
        lh = np.exp(mu + home + atk[hi] + dfn[ai])
        la = np.exp(mu + atk[ai] + dfn[hi])
        ll = np.sum(wt * (hg * np.log(lh) - lh + ag * np.log(la) - la))
        grad = np.zeros_like(th)
        rh, ra = wt * (hg - lh), wt * (ag - la)
        np.add.at(grad, hi, rh)
        np.add.at(grad, ai, ra)
        np.add.at(grad, T + ai, rh)
        np.add.at(grad, T + hi, ra)
        grad[2 * T] = rh.sum() + ra.sum()
        grad[2 * T + 1] = rh.sum()
        pen = np.concatenate([th[:2 * T], [0, 0]]) / prior_sd**2
        return -ll + 0.5 * np.sum(th[:2 * T] ** 2) / prior_sd**2, -grad + pen

    res = minimize(nll, np.zeros(2 * T + 2), jac=True, method="L-BFGS-B")
    th = res.x
    # incerteza (Laplace): diagonal da inversa da hessiana aproximada pelo L-BFGS
    try:
        se = np.sqrt(np.clip(np.diag(res.hess_inv.todense()), 0, None))
    except Exception:  # noqa: BLE001
        se = np.full_like(th, np.nan)
    return {"teams": teams, "atk": dict(zip(teams, th[:T], strict=True)), "def": dict(zip(teams, th[T:2 * T], strict=True)),
            "atk_se": dict(zip(teams, se[:T], strict=True)), "def_se": dict(zip(teams, se[T:2 * T], strict=True)),
            "mu": float(th[2 * T]), "home": float(th[2 * T + 1]), "jogos": len(train),
            "ate": before.strftime("%Y-%m-%dT%H:%M:%SZ")}


def lambdas(s: dict, home_ids, away_ids) -> tuple[np.ndarray, np.ndarray]:
    a, d = s["atk"], s["def"]
    lh = np.exp([s["mu"] + s["home"] + a.get(h, 0) + d.get(w, 0) for h, w in zip(home_ids, away_ids, strict=True)])
    la = np.exp([s["mu"] + a.get(w, 0) + d.get(h, 0) for h, w in zip(home_ids, away_ids, strict=True)])
    return np.asarray(lh), np.asarray(la)


def elo_now(matches: pd.DataFrame, params: EloParams, first_season: int) -> tuple[dict[str, float], np.ndarray]:
    r = run_elo(matches, params)
    rating: dict[str, float] = {}
    for row in r.itertuples():
        rating[row.home_id], rating[row.away_id] = row.elo_h_depois, row.elo_a_depois
    fit_rows = r[r.season >= first_season]
    theta = fit_ordinal(fit_rows.elo_diff.to_numpy(), outcome(fit_rows.home_goals.to_numpy(), fit_rows.away_goals.to_numpy()))
    return rating, theta


def ensemble_weights(cfg: dict) -> dict[str, float]:
    """Pesos do conjunto (forças, Elo) do backtest mais recente; padrão 0,6/0,4."""
    path = Path(cfg["paths"]["weights"]).with_name("backtest.json")
    try:
        conj = json.loads(path.read_text(encoding="utf-8"))["conjunto"]
        w = conj[max(conj, key=int)]["pesos"]
        f, e = float(w.get("forcas_map", 0)), float(w.get("base_elo", 0))
        if f + e > 0:
            return {"forcas": f / (f + e), "elo": e / (f + e)}
    except Exception:  # noqa: BLE001
        pass
    return {"forcas": 0.6, "elo": 0.4}


def attach(feat: pd.DataFrame, matches: pd.DataFrame, cfg: dict, elo_params: dict | None) -> pd.DataFrame:
    """Acrescenta gols esperados e probabilidades de produção aos jogos ainda não disputados."""
    out = feat.copy()
    pending = out.status != "FINISHED"
    if not pending.any():
        return out
    done = matches[(matches.status == "FINISHED") & matches.home_goals.notna()]
    before = pd.to_datetime(done.kickoff_utc, utc=True).max() + pd.Timedelta(seconds=1)
    s = fit_strengths(matches, before, half_life=float(cfg.get("production", {}).get("half_life_days", 365)))
    rows = out[pending]
    lh, la = lambdas(s, rows.home_id, rows.away_id)
    p_f = outcome_probs(lh, la)
    out.loc[pending, "lh_prod"], out.loc[pending, "la_prod"] = lh, la
    out.loc[pending, ["p_forcas_h", "p_forcas_d", "p_forcas_a"]] = p_f
    out.loc[pending, "atk_h"] = [s["atk"].get(t, 0) for t in rows.home_id]
    out.loc[pending, "atk_a"] = [s["atk"].get(t, 0) for t in rows.away_id]
    out.loc[pending, "def_h"] = [s["def"].get(t, 0) for t in rows.home_id]
    out.loc[pending, "def_a"] = [s["def"].get(t, 0) for t in rows.away_id]
    out.loc[pending, "mu_prod"], out.loc[pending, "home_prod"] = s["mu"], s["home"]
    w = ensemble_weights(cfg)
    if elo_params:
        params = EloParams(**{k: elo_params[k] for k in ("k", "home", "regression", "promoted")})
        rating, theta = elo_now(matches, params, int(cfg["model"]["train_first_season"]))
        diff = np.array([rating.get(h, 1500) + params.home - rating.get(a, 1500) for h, a in zip(rows.home_id, rows.away_id, strict=True)])
        p_e = ordinal_probs(diff, theta)
        out.loc[pending, ["p_elo_h", "p_elo_d", "p_elo_a"]] = p_e
        out.loc[pending, "elo_h"] = [rating.get(h, 1500) for h in rows.home_id]
        out.loc[pending, "elo_a"] = [rating.get(a, 1500) for a in rows.away_id]
        p_c = w["forcas"] * p_f + w["elo"] * p_e
    else:
        p_c = p_f
    out.loc[pending, ["p_conj_h", "p_conj_d", "p_conj_a"]] = p_c
    out.attrs["production"] = {"pesos_conjunto": w, "forcas_ate": s["ate"], "jogos_forcas": s["jogos"]}
    return out


def payload(row: pd.Series, rho: float = 0.0, max_goals: int = 10) -> dict:
    """Bloco de um jogo com o motor de produção: probabilidades por modelo e fatores explicáveis."""
    lh, la = float(row.lh_prod), float(row.la_prod)
    m = score_matrix(lh, la, rho, max_goals)
    i, j = np.unravel_index(np.argmax(m), m.shape)
    base = float(np.exp(row.mu_prod))
    def contrib(terms: dict[str, float], lam: float) -> dict[str, float]:
        # LMDI: divide (lam - base) entre os termos proporcionalmente na escala log
        tot = sum(terms.values())
        L = lam if abs(lam - base) < 1e-12 else (lam - base) / np.log(lam / base)
        return {k: float(v * L) if abs(tot) > 1e-12 else 0.0 for k, v in terms.items()}
    ch = contrib({"mando": row.home_prod, "ataque": row.atk_h, "defesa_adversario": row.def_a}, lh)
    ca = contrib({"mando": 0.0, "ataque": row.atk_a, "defesa_adversario": row.def_h}, la)
    fatores = [{"fator": "media_liga", "rotulo": FACTOR_LABELS["media_liga"], "peso": None,
                "mandante": {"valor": base, "efeito_gols": 0.0, "multiplicador": 1.0},
                "visitante": {"valor": base, "efeito_gols": 0.0, "multiplicador": 1.0}}]
    for k in ("mando", "ataque", "defesa_adversario"):
        th = {"mando": row.home_prod, "ataque": row.atk_h, "defesa_adversario": row.def_a}[k]
        ta = {"mando": 0.0, "ataque": row.atk_a, "defesa_adversario": row.def_h}[k]
        fatores.append({
            "fator": k, "rotulo": FACTOR_LABELS[k], "peso": None,
            "mandante": {"valor": round(float(th), 3), "efeito_gols": round(ch[k], 3),
                         "multiplicador": round(float(np.exp(th)), 3)},
            "visitante": {"valor": round(float(ta), 3), "efeito_gols": round(ca[k], 3),
                          "multiplicador": round(float(np.exp(ta)), 3)},
        })
    pc = [float(row.p_conj_h), float(row.p_conj_d), float(row.p_conj_a)]
    modelos = {"forcas": {"mandante": round(float(row.p_forcas_h), 4), "empate": round(float(row.p_forcas_d), 4),
                          "visitante": round(float(row.p_forcas_a), 4)}}
    if "p_elo_h" in row and pd.notna(row.get("p_elo_h")):
        modelos["elo"] = {"mandante": round(float(row.p_elo_h), 4), "empate": round(float(row.p_elo_d), 4),
                          "visitante": round(float(row.p_elo_a), 4)}
    return {
        "gols_esperados": {"mandante": round(lh, 3), "visitante": round(la, 3)}, "gols_base": round(base, 3),
        "probabilidade_estimada": {"mandante": round(pc[0], 4), "empate": round(pc[1], 4), "visitante": round(pc[2], 4)},
        "probabilidade_por_modelo": modelos,
        "placar_mais_provavel": {"mandante": int(i), "visitante": int(j), "probabilidade": round(float(m[i, j]), 4)},
        "fatores": fatores, "motor": "conjunto (forças por time + Elo)",
    }

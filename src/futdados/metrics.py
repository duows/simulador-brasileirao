"""Catálogo de métricas (seção 2 do prompt mestre), calculado só com jogos disputados.

Três tabelas derivadas, regravadas por `futdados metrics`:
- team_round_stats: cada time depois de cada rodada (tabela acumulada, posição, distâncias para
  líder/G4/G6/Z4, médias móveis de pontos).
- team_season_stats: cada time em cada temporada (resultados, casa/fora, ataque e defesa,
  sequências, distribuição de placares, Pitagórico e sorte/azar).
- league_season_stats: cada temporada (pontos de corte, gols, empates, mando, competitividade).

O expoente do Pitagórico é estimado do próprio histórico (ver `fit_pythagorean`).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.optimize import minimize_scalar

from .quality import season_rules


def team_games(matches: pd.DataFrame) -> pd.DataFrame:
    """Uma linha por time por jogo disputado (formato longo), em ordem cronológica."""
    done = matches[(matches.status == "FINISHED") & matches.home_goals.notna()].copy()
    done["kickoff_utc"] = pd.to_datetime(done.kickoff_utc, utc=True)
    home = pd.DataFrame({"season": done.season, "round": done["round"], "kickoff_utc": done.kickoff_utc,
                         "team_id": done.home_id, "opp_id": done.away_id, "local": "casa",
                         "gf": done.home_goals.astype(int), "ga": done.away_goals.astype(int)})
    away = pd.DataFrame({"season": done.season, "round": done["round"], "kickoff_utc": done.kickoff_utc,
                         "team_id": done.away_id, "opp_id": done.home_id, "local": "fora",
                         "gf": done.away_goals.astype(int), "ga": done.home_goals.astype(int)})
    g = pd.concat([home, away], ignore_index=True)
    g["res"] = np.where(g.gf > g.ga, "V", np.where(g.gf == g.ga, "E", "D"))
    g["pts"] = g.res.map({"V": 3, "E": 1, "D": 0})
    return g.sort_values(["season", "team_id", "kickoff_utc"]).reset_index(drop=True)


def _rank(df: pd.DataFrame) -> pd.Series:
    """Posição pela ordem pontos, vitórias, saldo, gols pró; empate total fica em ordem alfabética
    (confronto direto e cartões não entram nas métricas históricas)."""
    order = df.sort_values(["pts", "v", "sg", "gp", "team_id"], ascending=[False, False, False, False, True]).index
    pos = pd.Series(0, index=df.index)
    pos.loc[order] = np.arange(1, len(df) + 1)
    return pos


def team_round_stats(matches: pd.DataFrame) -> pd.DataFrame:
    """Tabela acumulada depois de cada rodada, para cada temporada.

    "Depois da rodada R" = todos os jogos com rodada <= R já disputados (adiados entram quando
    forem disputados, na rodada original deles).
    """
    g = team_games(matches)
    out = []
    for season, gs in g.groupby("season"):
        rules = season_rules(int(season))
        zones = rules["zonas"]
        teams = sorted(set(matches[matches.season == season].home_id) | set(matches[matches.season == season].away_id))
        for rnd in sorted(gs["round"].unique()):
            upto = gs[gs["round"] <= rnd]
            agg = upto.groupby("team_id").agg(j=("pts", "size"), pts=("pts", "sum"), gp=("gf", "sum"), gc=("ga", "sum"),
                                              v=("res", lambda s: (s == "V").sum()), e=("res", lambda s: (s == "E").sum()),
                                              d=("res", lambda s: (s == "D").sum()))
            agg = agg.reindex(teams, fill_value=0).reset_index().rename(columns={"index": "team_id"})
            agg["sg"] = agg.gp - agg.gc
            agg["posicao"] = _rank(agg).to_numpy()
            by_pos = agg.sort_values("posicao").pts.to_numpy()
            leader = by_pos[0]
            g4 = by_pos[zones["g4"][1] - 1]
            g6 = by_pos[zones["g6"][1] - 1]
            safe = by_pos[zones["rebaixamento"][0] - 2]  # último fora do Z4
            agg["dist_lider"] = leader - agg.pts
            agg["dist_g4"] = g4 - agg.pts
            agg["dist_g6"] = g6 - agg.pts
            agg["dist_z4"] = agg.pts - by_pos[zones["rebaixamento"][0] - 1]  # folga sobre o 1º do Z4
            agg["dist_fora_z4"] = safe - agg.pts
            agg["aproveitamento"] = np.where(agg.j > 0, agg.pts / (3 * agg.j.clip(lower=1)), np.nan)
            agg["season"], agg["round"] = int(season), int(rnd)
            out.append(agg)
    trs = pd.concat(out, ignore_index=True)
    # médias móveis de pontos por jogo (5 e 10 jogos), pela ordem dos jogos do time
    g["mm5"] = g.groupby(["season", "team_id"]).pts.transform(lambda s: s.rolling(5, min_periods=1).mean())
    g["mm10"] = g.groupby(["season", "team_id"]).pts.transform(lambda s: s.rolling(10, min_periods=1).mean())
    last = g.groupby(["season", "team_id", "round"])[["mm5", "mm10"]].last().reset_index()
    trs = trs.merge(last, on=["season", "team_id", "round"], how="left")
    trs[["mm5", "mm10"]] = trs.groupby(["season", "team_id"])[["mm5", "mm10"]].ffill()
    return trs


def _longest(flags: list[bool]) -> int:
    best = cur = 0
    for f in flags:
        cur = cur + 1 if f else 0
        best = max(best, cur)
    return best


def _current(flags: list[bool]) -> int:
    n = 0
    for f in reversed(flags):
        if not f:
            break
        n += 1
    return n


STREAKS = {
    "invicto": lambda r: r.res != "D",
    "vitorias": lambda r: r.res == "V",
    "derrotas": lambda r: r.res == "D",
    "sem_vencer": lambda r: r.res != "V",
    "sem_marcar": lambda r: r.gf == 0,
    "sem_sofrer": lambda r: r.ga == 0,
}


def fit_pythagorean(tss: pd.DataFrame) -> tuple[float, float, float]:
    """Expoente k e reta pontos/jogo = a + b * GP^k/(GP^k+GC^k), por mínimos quadrados no histórico."""
    gf, ga, ppg = tss.gp.to_numpy(float), tss.gc.to_numpy(float), (tss.pts / tss.j).to_numpy(float)

    def fit_line(k):
        x = gf**k / (gf**k + ga**k)
        A = np.vstack([np.ones_like(x), x]).T
        coef, *_ = np.linalg.lstsq(A, ppg, rcond=None)
        return coef, float(np.mean((A @ coef - ppg) ** 2))

    k = float(minimize_scalar(lambda k: fit_line(k)[1], bounds=(0.5, 4), method="bounded").x)
    (a, b), _ = fit_line(k)
    return k, float(a), float(b)


def team_season_stats(matches: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    g = team_games(matches)
    rows = []
    for (season, team), t in g.groupby(["season", "team_id"]):
        n = len(t)
        row = {"season": int(season), "team_id": team, "j": n, "pts": int(t.pts.sum()),
               "v": int((t.res == "V").sum()), "e": int((t.res == "E").sum()), "d": int((t.res == "D").sum()),
               "gp": int(t.gf.sum()), "gc": int(t.ga.sum())}
        for side in ("casa", "fora"):
            s = t[t.local == side]
            row.update({f"{side}_j": len(s), f"{side}_pts": int(s.pts.sum()), f"{side}_gp": int(s.gf.sum()),
                        f"{side}_gc": int(s.ga.sum())})
        row.update({
            "gp_por_jogo": t.gf.mean(), "gc_por_jogo": t.ga.mean(),
            "clean_sheets": int((t.ga == 0).sum()), "sem_marcar": int((t.gf == 0).sum()),
            "jogos_3mais_gols": int(((t.gf + t.ga) >= 3).sum()),
            "ambos_marcam_pct": float(((t.gf > 0) & (t.ga > 0)).mean()),
            "placar_mais_comum": t.apply(lambda r: f"{r.gf}-{r.ga}", axis=1).value_counts().idxmax(),
        })
        recs = list(t.itertuples())
        for name, f in STREAKS.items():
            flags = [bool(f(r)) for r in recs]
            row[f"maior_seq_{name}"] = _longest(flags)
            row[f"seq_atual_{name}"] = _current(flags)
        rows.append(row)
    tss = pd.DataFrame(rows)
    tss["sg"] = tss.gp - tss.gc
    tss["aproveitamento"] = tss.pts / (3 * tss.j)
    tss["pts_por_jogo"] = tss.pts / tss.j
    # força relativa à média da liga na temporada
    lg = tss.groupby("season")[["gp_por_jogo", "gc_por_jogo"]].transform("mean")
    tss["ataque_relativo"] = tss.gp_por_jogo / lg.gp_por_jogo
    tss["defesa_relativa"] = tss.gc_por_jogo / lg.gc_por_jogo
    # Pitagórico (só temporadas com pelo menos 10 jogos por time no ajuste)
    k, a, b = fit_pythagorean(tss[tss.j >= 10])
    x = tss.gp**k / (tss.gp**k + tss.gc**k)
    tss["pts_pitagoricos"] = (a + b * x) * tss.j
    tss["pts_menos_pitagoricos"] = tss.pts - tss.pts_pitagoricos
    # posição final (ou atual, se a temporada não acabou)
    tss["posicao"] = 0
    for _season, d in tss.groupby("season"):
        tss.loc[d.index, "posicao"] = _rank(d).to_numpy()
    return tss, {"expoente": k, "intercepto": a, "inclinacao": b}


def gini(x: np.ndarray) -> float:
    x = np.sort(np.asarray(x, float))
    n = len(x)
    return float((2 * np.arange(1, n + 1) - n - 1) @ x / (n * x.sum())) if x.sum() > 0 else 0.0


def league_season_stats(matches: pd.DataFrame, tss: pd.DataFrame, trs: pd.DataFrame) -> pd.DataFrame:
    rows = []
    done = matches[(matches.status == "FINISHED") & matches.home_goals.notna()]
    for season, d in done.groupby("season"):
        rules = season_rules(int(season))
        z = rules["zonas"]
        t = tss[tss.season == season].sort_values("posicao")
        pts = t.pts.to_numpy()
        hg, ag = d.home_goals.astype(int), d.away_goals.astype(int)
        # disputa pelo título: times que, faltando 5 rodadas, ainda podiam alcançar o líder
        last_round = int(trs[trs.season == season]["round"].max())
        cut = trs[(trs.season == season) & (trs["round"] == max(last_round - 5, 1))]
        max_possible = cut.pts + 3 * (2 * (rules["clubes"] - 1) - cut.j)
        in_race = int((max_possible >= cut.pts.max()).sum())
        rows.append({
            "season": int(season), "jogos": len(d),
            "encerrada": len(d) >= rules["jogos_esperados"],
            "pts_campeao": int(pts[0]), "pts_vice": int(pts[1]),
            "pts_g4": int(pts[z["g4"][1] - 1]), "pts_g6": int(pts[z["g6"][1] - 1]),
            "pts_16": int(pts[z["rebaixamento"][0] - 2]), "pts_17": int(pts[z["rebaixamento"][0] - 1]),
            "pts_ultimo": int(pts[-1]), "campeao": t.team_id.iloc[0],
            "gols_por_jogo": float((hg + ag).mean()), "empates_pct": float((hg == ag).mean()),
            "vitorias_mandante_pct": float((hg > ag).mean()), "vitorias_visitante_pct": float((hg < ag).mean()),
            "vantagem_mando_gols": float((hg - ag).mean()),
            "desvio_pontos": float(np.std(pts, ddof=1)), "gini_pontos": gini(pts),
            "times_na_briga_5_rodadas_antes": in_race,
        })
    lss = pd.DataFrame(rows)
    # concentração de títulos e permanência na elite (até cada temporada)
    titles = lss.campeao.value_counts()
    lss["titulos_do_campeao_ate_aqui"] = [int((lss.campeao.iloc[: i + 1] == c).sum()) for i, c in enumerate(lss.campeao)]
    lss.attrs["titulos"] = titles.to_dict()
    return lss


def build_all(matches: pd.DataFrame) -> dict[str, pd.DataFrame | dict]:
    trs = team_round_stats(matches)
    tss, pyth = team_season_stats(matches)
    lss = league_season_stats(matches, tss, trs)
    # permanência na elite: temporadas na Série A por clube (até a temporada da linha)
    tss = tss.sort_values(["team_id", "season"])
    tss["temporadas_na_elite_ate_aqui"] = tss.groupby("team_id").cumcount() + 1
    prev = {s: set(tss[tss.season == s].team_id) for s in tss.season.unique()}
    tss["promovido"] = [int((s - 1) in prev and t not in prev[s - 1]) for s, t in zip(tss.season, tss.team_id)]
    return {"team_round_stats": trs, "team_season_stats": tss.reset_index(drop=True),
            "league_season_stats": lss, "pitagorico": pyth}

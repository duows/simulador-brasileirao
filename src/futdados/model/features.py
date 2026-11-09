"""Cálculo dos fatores de cada jogo usando SOMENTE informação anterior ao jogo.

Os jogos são percorridos em ordem cronológica. Para cada horário de início, primeiro
calculamos os fatores de todos os jogos daquele horário e só depois atualizamos o
estado com os resultados. Assim nenhum jogo enxerga o próprio placar nem o futuro.

Fatores (todos do ponto de vista do time que ataca, contra o adversário):
- ataque              log da taxa de gols marcados (com decaimento) / média da liga
- defesa_adversario   log da taxa de gols sofridos pelo adversário / média da liga
- mando               1 se o time joga em casa
- forma               pontos por jogo nos últimos N jogos do time menos os do adversário
- descanso            dias de descanso do time menos os do adversário (limitados)
- meio_de_semana      1 se o jogo é de terça a quinta (horário de Brasília)
- tecnico_novo        1 se só o time está nos primeiros jogos com técnico novo,
                      -1 se só o adversário, 0 caso contrário
"""

from __future__ import annotations

import math
from collections import defaultdict, deque
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

FEATURES = ["ataque", "defesa_adversario", "mando", "forma", "descanso", "meio_de_semana",
            "tecnico_novo"]
DEFAULT_PPG = 1.36  # pontos por jogo médios do Brasileirão (centro neutro da forma)


@dataclass
class TeamState:
    gf: float = 0.0        # gols marcados ajustados, com decaimento
    ga: float = 0.0        # gols sofridos ajustados, com decaimento
    w: float = 0.0         # peso acumulado (número "efetivo" de jogos)
    t: float | None = None
    last_points: deque = field(default_factory=lambda: deque(maxlen=5))
    last_season: int | None = None
    last_kickoff: pd.Timestamp | None = None


def _days(ts: pd.Timestamp) -> float:
    return ts.value / 86_400e9


def coach_change_dates(matches: pd.DataFrame, extra: pd.DataFrame | None = None) -> dict[str, list]:
    """Datas de início de cada técnico novo por time.

    Vêm (a) da troca de nome do técnico entre jogos consecutivos no histórico,
    (b) de `extra` (snapshots da API e config/coach_changes.csv), colunas team_id e start.
    """
    changes: dict[str, list] = defaultdict(list)
    last: dict[str, str] = {}
    for r in matches.sort_values("kickoff_utc").itertuples():
        for tid, coach in ((r.home_id, r.home_coach), (r.away_id, r.away_coach)):
            if not isinstance(coach, str) or not coach:
                continue
            if tid in last and last[tid] != coach:
                changes[tid].append(r.kickoff_utc)
            last[tid] = coach
    if extra is not None:
        for r in extra.itertuples():
            changes[r.team_id].append(pd.Timestamp(r.start, tz="UTC") if pd.Timestamp(r.start).tzinfo is None
                                      else pd.Timestamp(r.start))
    return {k: sorted(v) for k, v in changes.items()}


def build_features(matches: pd.DataFrame, mcfg: dict, coach_extra: pd.DataFrame | None = None,
                   half_life_days: float | None = None) -> pd.DataFrame:
    """Devolve uma linha por jogo com os fatores do mandante (_h) e do visitante (_a)."""
    hl = float(half_life_days or mcfg["half_life_days"])
    k = float(mcfg["prior_matches"])
    p_att, p_def = float(mcfg["prior_attack_ratio"]), float(mcfg["prior_defense_ratio"])
    n_form = int(mcfg["form_matches"])
    rest_lo, rest_hi = mcfg["rest_clip_days"]
    midweek = set(mcfg["midweek_days"])
    n_coach = int(mcfg["new_coach_matches"])
    adjust = bool(mcfg.get("opponent_adjust", True))

    df = matches.sort_values(["kickoff_utc", "home_id"]).reset_index(drop=True)
    changes = coach_change_dates(df, coach_extra)
    teams: dict[str, TeamState] = defaultdict(lambda: TeamState(last_points=deque(maxlen=n_form)))
    league = {"g": 0.0, "w": 0.0, "t": None}
    coach_count: dict[str, int] = defaultdict(int)     # jogos desde a última troca
    coach_idx: dict[str, int] = defaultdict(int)       # quantas trocas já passaram

    def decay(t_prev, t_now):
        return 1.0 if t_prev is None else 0.5 ** ((t_now - t_prev) / hl)

    def league_mu(t_now):
        if league["w"] <= 0:
            return 1.25
        return league["g"] / league["w"]  # razão não depende do decaimento comum

    def strength(tid, t_now, mu):
        s = teams[tid]
        f = decay(s.t, t_now)
        gf, ga, w = s.gf * f, s.ga * f, s.w * f
        att = (gf + k * p_att * mu) / (w + k) / mu
        dfn = (ga + k * p_def * mu) / (w + k) / mu
        return math.log(att), math.log(dfn), w

    def ppg(tid, season):
        s = teams[tid]
        if s.last_season != season or not s.last_points:
            return DEFAULT_PPG, 0
        return sum(s.last_points) / len(s.last_points), len(s.last_points)

    def rest(tid, ko):
        s = teams[tid]
        if s.last_kickoff is None:
            return float(rest_hi)
        return float(np.clip((ko - s.last_kickoff).total_seconds() / 86400, rest_lo, rest_hi))

    def new_coach(tid, ko):
        lst = changes.get(tid, [])
        # avança o índice de trocas que já começaram até este jogo
        while coach_idx[tid] < len(lst) and lst[coach_idx[tid]] <= ko:
            coach_idx[tid] += 1
            coach_count[tid] = 0
        return int(coach_idx[tid] > 0 and coach_count[tid] < n_coach)

    out = []
    for ko, group in df.groupby("kickoff_utc", sort=True):
        t_now = _days(ko)
        mu = league_mu(t_now)
        rows = []
        for r in group.itertuples():
            att_h, def_h, w_h = strength(r.home_id, t_now, mu)
            att_a, def_a, w_a = strength(r.away_id, t_now, mu)
            ppg_h, nf_h = ppg(r.home_id, r.season)
            ppg_a, nf_a = ppg(r.away_id, r.season)
            rest_h, rest_a = rest(r.home_id, ko), rest(r.away_id, ko)
            nc_h, nc_a = new_coach(r.home_id, ko), new_coach(r.away_id, ko)
            local_wd = (ko - pd.Timedelta(hours=3)).weekday()
            mw = int(local_wd in midweek)
            rows.append({
                "season": r.season, "round": r.round, "kickoff_utc": ko, "status": r.status,
                "home_id": r.home_id, "away_id": r.away_id,
                "home_goals": r.home_goals, "away_goals": r.away_goals, "mu": mu,
                # fatores do mandante atacando
                "ataque_h": att_h, "defesa_adversario_h": def_a, "mando_h": 1,
                "forma_h": ppg_h - ppg_a, "descanso_h": rest_h - rest_a, "meio_de_semana_h": mw,
                "tecnico_novo_h": nc_h - nc_a,
                # fatores do visitante atacando
                "ataque_a": att_a, "defesa_adversario_a": def_h, "mando_a": 0,
                "forma_a": ppg_a - ppg_h, "descanso_a": rest_a - rest_h, "meio_de_semana_a": mw,
                "tecnico_novo_a": nc_a - nc_h,
                # valores brutos para a explicação
                "raw_ppg_h": ppg_h, "raw_ppg_a": ppg_a, "raw_nform_h": nf_h, "raw_nform_a": nf_a,
                "raw_rest_h": rest_h, "raw_rest_a": rest_a, "raw_newcoach_h": nc_h,
                "raw_newcoach_a": nc_a, "raw_weight_h": w_h, "raw_weight_a": w_a,
            })
        out.extend(rows)

        # ---- atualização do estado com os jogos já disputados neste horário
        for r, row in zip(group.itertuples(), rows):
            if r.status != "FINISHED" or pd.isna(r.home_goals):
                # jogo ainda não disputado: só conta para o calendário (descanso)
                for tid in (r.home_id, r.away_id):
                    teams[tid].last_kickoff = ko
                continue
            hg, ag = float(r.home_goals), float(r.away_goals)
            for tid, gf, ga, opp_def, opp_att in (
                (r.home_id, hg, ag, row["defesa_adversario_h"], row["ataque_a"]),
                (r.away_id, ag, hg, row["defesa_adversario_a"], row["ataque_h"]),
            ):
                s = teams[tid]
                f = decay(s.t, t_now)
                adj_gf = gf / math.exp(opp_def) if adjust else gf
                adj_ga = ga / math.exp(opp_att) if adjust else ga
                s.gf, s.ga, s.w, s.t = s.gf * f + adj_gf, s.ga * f + adj_ga, s.w * f + 1, t_now
                pts = 3 if gf > ga else (1 if gf == ga else 0)
                if s.last_season != r.season:
                    s.last_points.clear()
                    s.last_season = r.season
                s.last_points.append(pts)
                s.last_kickoff = ko
                coach_count[tid] += 1
            f = decay(league["t"], t_now)
            league["g"] = league["g"] * f + hg + ag
            league["w"] = league["w"] * f + 2
            league["t"] = t_now
    return pd.DataFrame(out)


def long_format(feat: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Empilha mandante e visitante: X (2n x p), y (gols), offset log(mu), id do jogo."""
    xh = feat[[f"{c}_h" for c in FEATURES]].to_numpy(float)
    xa = feat[[f"{c}_a" for c in FEATURES]].to_numpy(float)
    X = np.vstack([xh, xa])
    y = np.concatenate([feat["home_goals"].to_numpy(float), feat["away_goals"].to_numpy(float)])
    off = np.log(np.concatenate([feat["mu"].to_numpy(float)] * 2))
    gid = np.concatenate([np.arange(len(feat))] * 2)
    return X, y, off, gid

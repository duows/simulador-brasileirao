"""Regras por temporada, flags de casos especiais, checagens de qualidade e cobertura.

- `season_rules(season)`: config/seasons.yaml (default + exceções do ano).
- `compute_flags(matches)`: adiado, remarcado, campo neutro e portões fechados.
- `quality_issues(matches)`: lista de problemas (vazia = ok).
- `coverage(matches)`: jogos esperados x existentes por temporada, com fonte e licença.
"""

from __future__ import annotations

import copy
from functools import lru_cache
from pathlib import Path

import pandas as pd
import yaml

from .config import ROOT

SEASONS_YAML = ROOT / "config" / "seasons.yaml"

SOURCE_INFO = {
    "footballcsv": ("footballcsv/cache.wfb", "CC0 1.0 (procedência: cache do worldfootball.net, ver D14)"),
    "football-data": ("football-data.org API v4", "plano grátis; atribuição obrigatória (D02, D15)"),
    "adaoduque": ("adaoduque/Brasileirao_Dataset", "SEM licença: só local, nunca exportado"),
    "teste": ("dados sintéticos de teste", "—"),
}


@lru_cache(maxsize=2)
def _seasons_cfg(path: str) -> dict:
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def season_rules(season: int, path: str | Path = SEASONS_YAML) -> dict:
    cfg = _seasons_cfg(str(path))
    rules = copy.deepcopy(cfg["default"])
    for k, v in (cfg.get("temporadas", {}).get(season) or {}).items():
        if isinstance(v, dict) and isinstance(rules.get(k), dict):
            rules[k].update(v)
        else:
            rules[k] = v
    return rules


def compute_flags(matches: pd.DataFrame, today: pd.Timestamp | None = None) -> pd.DataFrame:
    """Flags por jogo.

    - postponed: jogo não disputado de uma rodada que já teve outros jogos disputados, ou com
      status POSTPONED/SUSPENDED.
    - rescheduled: jogo disputado a 7 dias ou mais da data mediana da sua rodada.
    - behind_closed_doors: dentro do período de portões fechados da temporada (seasons.yaml).
    - neutral_venue: sem fonte para isso hoje; fica 0 (TODO: fonte licenciada).
    """
    df = matches.copy()
    ko = pd.to_datetime(df["kickoff_utc"], utc=True)
    median = ko.groupby([df["season"], df["round"]]).transform("median")
    finished = df["status"] == "FINISHED"
    any_finished_in_round = finished.groupby([df["season"], df["round"]]).transform("any")
    df["postponed"] = ((~finished & any_finished_in_round) | df["status"].isin(["POSTPONED", "SUSPENDED"])).astype(int)
    df["rescheduled"] = (finished & ((ko - median).abs() >= pd.Timedelta(days=7))).astype(int)
    df["neutral_venue"] = 0
    closed = pd.Series(0, index=df.index)
    for season in df["season"].unique():
        win = season_rules(int(season)).get("portoes_fechados")
        if win:
            sel = (df["season"] == season) & (ko >= pd.Timestamp(win["inicio"], tz="UTC")) & (ko < pd.Timestamp(win["fim"], tz="UTC"))
            closed[sel] = 1
    df["behind_closed_doors"] = closed
    return df[["season", "home_id", "away_id", "postponed", "rescheduled", "neutral_venue", "behind_closed_doors"]]


def quality_issues(matches: pd.DataFrame) -> list[str]:
    """Checagens que valem para qualquer temporada (fechada ou em andamento)."""
    issues: list[str] = []
    m = matches
    dup = m.duplicated(["season", "home_id", "away_id"])
    if dup.any():
        issues.append(f"{int(dup.sum())} jogos duplicados (mesma temporada, mandante e visitante)")
    if (m["home_id"] == m["away_id"]).any():
        issues.append("time jogando contra si mesmo")
    done = m[m["status"] == "FINISHED"]
    if done[["home_goals", "away_goals"]].isna().any().any():
        issues.append("jogo encerrado sem placar")
    if (done[["home_goals", "away_goals"]] < 0).any().any():
        issues.append("placar negativo")
    # mesmo time duas vezes na mesma rodada
    long = pd.concat([m[["season", "round", "home_id"]].rename(columns={"home_id": "team"}),
                      m[["season", "round", "away_id"]].rename(columns={"away_id": "team"})])
    twice = long.duplicated(["season", "round", "team"])
    if twice.any():
        ex = long[twice].iloc[0]
        issues.append(f"{int(twice.sum())} casos de time com 2 jogos na mesma rodada (ex.: {ex.team}, {ex.season} R{ex['round']})")
    # simetria: em cada temporada, se A recebe B, B recebe A
    for season, g in m.groupby("season"):
        pairs = set(zip(g.home_id, g.away_id))
        missing = [(a, b) for a, b in pairs if (b, a) not in pairs]
        rules = season_rules(int(season))
        allowed = rules["clubes"] * (rules["clubes"] - 1) - rules["jogos_esperados"]
        if len(missing) > allowed:
            issues.append(f"{season}: {len(missing)} jogos sem o returno correspondente")
    return issues


def closed_season_issues(matches: pd.DataFrame, season: int) -> list[str]:
    """Checagens extras para temporada encerrada: total de jogos, 38 por time e soma de pontos."""
    rules = season_rules(season)
    g = matches[matches["season"] == season]
    issues = []
    if len(g) != rules["jogos_esperados"]:
        issues.append(f"{season}: {len(g)} jogos, esperado {rules['jogos_esperados']}")
    n_games = pd.concat([g.home_id, g.away_id]).value_counts()
    expected = 2 * (rules["clubes"] - 1)
    short = n_games[n_games != expected]
    if rules["jogos_esperados"] == rules["clubes"] * (rules["clubes"] - 1) and len(short):
        issues.append(f"{season}: times sem {expected} jogos: {dict(short)}")
    if len(n_games) != rules["clubes"]:
        issues.append(f"{season}: {len(n_games)} clubes, esperado {rules['clubes']}")
    done = g[g.status == "FINISHED"]
    hp = (done.home_goals > done.away_goals) * 3 + (done.home_goals == done.away_goals)
    ap = (done.away_goals > done.home_goals) * 3 + (done.home_goals == done.away_goals)
    draws = int((done.home_goals == done.away_goals).sum())
    if int(hp.sum() + ap.sum()) != 3 * (len(done) - draws) + 2 * draws:
        issues.append(f"{season}: soma de pontos inconsistente")
    return issues


def coverage(matches: pd.DataFrame, first: int = 2006, last: int = 2026) -> pd.DataFrame:
    rows = []
    for season in range(first, last + 1):
        rules = season_rules(season)
        g = matches[matches["season"] == season]
        sources = sorted(g["source"].unique()) if len(g) else []
        rows.append({
            "temporada": season, "esperados": rules["jogos_esperados"], "existentes": len(g),
            "encerrados": int((g["status"] == "FINISHED").sum()) if len(g) else 0,
            "fontes": ", ".join(SOURCE_INFO.get(s, (s, ""))[0] for s in sources) or "—",
            "licenca": "; ".join(SOURCE_INFO.get(s, ("", "?"))[1] for s in sources) or "—",
            "notas": " ".join(rules.get("notas") or []),
        })
    return pd.DataFrame(rows)

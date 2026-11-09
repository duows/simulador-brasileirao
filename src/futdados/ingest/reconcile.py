"""Reconciliação entre fontes que cobrem os mesmos jogos.

Regra de escolha (explícita): football-data.org > footballcsv > adaoduque. O banco guarda a
fonte de maior prioridade; as demais servem para conferir placar e data. A fonte adaoduque
(sem licença) só é lida com LOCAL_ONLY_SOURCES=1, fica em data/external (gitignored) e nunca
é gravada no banco nem exportada.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd

from ..teams import team_id
from .historical import load_season

PRIORITY = ["football-data", "footballcsv", "adaoduque"]
ADAODUQUE_URL = "https://github.com/adaoduque/Brasileirao_Dataset"


def local_only_enabled() -> bool:
    return os.environ.get("LOCAL_ONLY_SOURCES") == "1"


def load_adaoduque(repo_dir: str | Path, first: int = 2006) -> pd.DataFrame:
    """CSV consolidado 2003-2024 do adaoduque (só local). Temporada pela quebra de rodada."""
    repo_dir = Path(repo_dir)
    if not (repo_dir / "campeonato-brasileiro-full.csv").exists():
        repo_dir.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "clone", "--depth", "1", ADAODUQUE_URL, str(repo_dir)], check=True)
    df = pd.read_csv(repo_dir / "campeonato-brasileiro-full.csv", dtype=str)
    df["ID"] = df["ID"].astype(int)
    df = df.sort_values("ID")
    r = df["rodata"].astype(int).to_numpy()
    df["season"] = 2003 + np.concatenate([[0], np.cumsum(np.diff(r) < -20)])
    df = df[df.season >= first]
    return pd.DataFrame({
        "season": df.season.astype(int),
        "home_id": df.mandante.map(team_id), "away_id": df.visitante.map(team_id),
        "home_goals": df.mandante_Placar.astype(int), "away_goals": df.visitante_Placar.astype(int),
        "kickoff_utc": pd.to_datetime(df.data, dayfirst=True).dt.tz_localize("UTC") + pd.Timedelta(hours=3),
        "source": "adaoduque",
    })


def compare(base: pd.DataFrame, other: pd.DataFrame, label: str) -> tuple[pd.DataFrame, int]:
    """Jogos em comum com placar diferente ou data a mais de 1 dia de distância, e faltantes."""
    keys = ["season", "home_id", "away_id"]
    b = base[base.status == "FINISHED"][keys + ["home_goals", "away_goals", "kickoff_utc", "source"]]
    o = other[keys + ["home_goals", "away_goals", "kickoff_utc"]]
    m = b.merge(o, on=keys, how="outer", suffixes=("", "_outra"), indicator=True)
    m = m[m.season.isin(o.season.unique())].rename(columns={"_merge": "merge_"})
    rows = []
    for r in m.itertuples():
        if r.merge_ == "right_only":
            rows.append({**{k: getattr(r, k) for k in keys}, "tipo": "só na outra fonte", "banco": "—",
                         "outra": f"{int(r.home_goals_outra)}-{int(r.away_goals_outra)}"})
            continue
        if r.merge_ == "left_only":
            continue  # a outra fonte não cobre este jogo (ex.: cache parado em set/2024)
        if (r.home_goals, r.away_goals) != (r.home_goals_outra, r.away_goals_outra):
            rows.append({**{k: getattr(r, k) for k in keys}, "tipo": "placar",
                         "banco": f"{int(r.home_goals)}-{int(r.away_goals)} ({r.source})",
                         "outra": f"{int(r.home_goals_outra)}-{int(r.away_goals_outra)} ({label})"})
        elif abs(pd.Timestamp(r.kickoff_utc) - pd.Timestamp(r.kickoff_utc_outra)) > pd.Timedelta(days=1):
            rows.append({**{k: getattr(r, k) for k in keys}, "tipo": "data",
                         "banco": pd.Timestamp(r.kickoff_utc).strftime("%Y-%m-%d"),
                         "outra": pd.Timestamp(r.kickoff_utc_outra).strftime("%Y-%m-%d")})
    out = pd.DataFrame(rows, columns=keys + ["tipo", "banco", "outra"])
    out["fonte_comparada"] = label
    return out, int((m.merge_ == "both").sum())


def reconcile(db_matches: pd.DataFrame, cfg: dict) -> tuple[pd.DataFrame, list[str]]:
    """Compara o banco com as fontes secundárias disponíveis. Devolve (divergências, resumo)."""
    summary, frames = [], []
    # footballcsv x API onde se sobrepõem (2024: o cache vai até set/2024)
    api_seasons = sorted(db_matches[db_matches.source == "football-data"].season.unique())
    wfb_dir = cfg["paths"]["historical_repo"]
    wfb_rows = []
    for s in api_seasons:
        if (Path(wfb_dir) / str(int(s)) / "br.1.csv").exists():
            wfb_rows += load_season(wfb_dir, int(s))[0]
    if wfb_rows:
        wfb = pd.DataFrame(wfb_rows)
        wfb["kickoff_utc"] = pd.to_datetime(wfb.kickoff_utc, utc=True)
        d, n = compare(db_matches, wfb, "footballcsv")
        frames.append(d)
        summary.append(f"football-data.org x footballcsv ({', '.join(map(str, api_seasons))}): {n} jogos em comum, {len(d)} divergências.")
    if local_only_enabled():
        ad = load_adaoduque(Path(cfg["paths"]["historical_repo"]).parent / "Brasileirao_Dataset")
        d, n = compare(db_matches, ad, "adaoduque (local)")
        frames.append(d)
        summary.append(f"banco x adaoduque (local, 2006-2024): {n} jogos em comum, {len(d)} divergências.")
    else:
        summary.append("adaoduque (sem licença) não comparado: rode com LOCAL_ONLY_SOURCES=1 para validar localmente.")
    div = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    return div, summary

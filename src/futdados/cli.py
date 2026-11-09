"""Linha de comando do futdados. Use `futdados --help` para ver os subcomandos."""

from __future__ import annotations

import argparse
import sys

from .config import load_config
from .db import Repository


def _repo(cfg) -> Repository:
    return Repository(cfg["paths"]["db"])


def cmd_ingest_historical(args, cfg) -> None:
    from .ingest.historical import ingest_historical

    counts = ingest_historical(_repo(cfg), cfg)
    print(f"Histórico carregado: {sum(counts.values())} jogos em {len(counts)} temporadas.")


def cmd_ingest_api(args, cfg) -> None:
    from .ingest.football_data import ingest_api

    res = ingest_api(_repo(cfg), cfg, args.season)
    print(f"API: {res['matches']} jogos, {res['standings']} linhas de classificação.")
    for tid, coach in res["coach_changes"]:
        print(f"  Troca de técnico detectada: {tid} -> {coach}")


def cmd_fit(args, cfg) -> None:
    from .backtest.walkforward import tune_half_life
    from .model.poisson import fit
    from .model.predict import features_for
    from .reports import weights_markdown, write

    repo = _repo(cfg)
    tune = None
    if args.half_life:
        hl = args.half_life
    else:
        hl, tune = tune_half_life(repo.matches(), cfg)
        print(f"Meia-vida escolhida no walk-forward: {hl:.0f} dias")
    feat = features_for(repo, cfg, hl)
    train = feat[feat.season >= cfg["model"]["train_first_season"]]
    w = fit(train, cfg["model"], hl, seed=cfg["simulation"]["seed"])
    w.save(cfg["paths"]["weights"])
    write(f"{cfg['paths']['reports']}/pesos.md", weights_markdown(w, tune))
    print(f"Pesos salvos ({w.model_version}) em {cfg['paths']['weights']} e reports/pesos.md")


def _print_projection(table, meta) -> None:
    from .teams import display_name

    print(f"Tabela projetada depois da rodada {meta['target_round']} "
          f"(resultados reais até a rodada {meta['based_on_round']}, {meta['n_sims']} simulações)")
    print(f"{'#':>2} {'Time':<16}{'Pts':>4}{'Pts esp.':>9}{'Faixa':>8}{'Título':>8}{'G4':>7}{'G6':>7}{'Reb.':>7}")
    for i, r in enumerate(table.itertuples(), start=1):
        faixa = f"{r.pos_p10:.0f}-{r.pos_p90:.0f}"
        print(f"{i:>2} {display_name(r.team_id):<16}{r.pontos_atuais:>4}{r.exp_points:>9.1f}{faixa:>8}"
              f"{r.p_titulo:>8.1%}{r.p_g4:>7.1%}{r.p_g6:>7.1%}{r.p_rebaixamento:>7.1%}")


def cmd_project(args, cfg) -> None:
    from .pipeline import project, projection_json

    table, meta = project(_repo(cfg), cfg, args.season, args.round, args.as_of_round, args.sims)
    _print_projection(table, meta)
    print(f"JSON: {projection_json(cfg, table, meta)}")


def cmd_backtest(args, cfg) -> None:
    import pandas as pd

    from .backtest.walkforward import (brier, calibration_table, log_loss, outcome_index, score,
                                       walk_forward)
    from .model.predict import features_for
    from .model.poisson import Weights
    from .reports import backtest_markdown, write

    repo = _repo(cfg)
    try:
        hl = Weights.load(cfg["paths"]["weights"]).half_life_days
    except FileNotFoundError:
        hl = cfg["model"]["half_life_days"]
    seasons = cfg["backtest"]["test_seasons"]
    feat = features_for(repo, cfg, hl)
    pred = walk_forward(repo.matches(), cfg, seasons, hl, feat=feat)
    sc = score(pred)
    rows = []
    for s, g in pred.groupby("season"):
        y = outcome_index(g.home_goals, g.away_goals)
        p, f = g[["p_h", "p_d", "p_a"]].to_numpy(), g[["f_h", "f_d", "f_a"]].to_numpy()
        rows.append({"temporada": s, "n": len(g), "brier_modelo": brier(p, y), "brier_freq": brier(f, y),
                     "ll_modelo": log_loss(p, y), "ll_freq": log_loss(f, y)})
    y = outcome_index(pred.home_goals, pred.away_goals)
    p = pred[["p_h", "p_d", "p_a"]].to_numpy()
    calib = calibration_table(p, y, cfg["backtest"]["calibration_bins"])
    md = backtest_markdown(sc, pd.DataFrame(rows), calib, hl, seasons, len(pred),
                           (float(p[:, 1].mean()), float((y == 1).mean())))
    write(f"{cfg['paths']['reports']}/backtest.md", md)
    for k, v in sc.items():
        print(f"{k:<22} Brier {v['brier']:.4f}  log loss {v['log_loss']:.4f}  acerto {v['acerto']:.1%}")
    print("Relatório: reports/backtest.md")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="futdados", description=__doc__)
    p.add_argument("--config", help="caminho do model.yaml")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("ingest-historical", help="carrega 2003-2025 do dataset adaoduque")
    s = sub.add_parser("ingest-api", help="baixa a temporada do football-data.org")
    s.add_argument("--season", type=int, required=True)
    s = sub.add_parser("fit", help="estima os pesos e gera reports/pesos.md")
    s.add_argument("--half-life", type=float, help="pula a escolha automática da meia-vida")
    s = sub.add_parser("project", help="tabela projetada depois da rodada X (padrão: fim do campeonato)")
    s.add_argument("--season", type=int, required=True)
    s.add_argument("--round", type=int, help="rodada X da tabela projetada (padrão: última)")
    s.add_argument("--as-of-round", type=int,
                   help="reconstitui a projeção escondendo resultados depois desta rodada (demonstração)")
    s.add_argument("--sims", type=int, help="número de simulações (padrão no YAML)")
    sub.add_parser("backtest", help="walk-forward por temporada e reports/backtest.md")
    return p


COMMANDS = {
    "ingest-historical": cmd_ingest_historical,
    "ingest-api": cmd_ingest_api,
    "fit": cmd_fit,
    "project": cmd_project,
    "backtest": cmd_backtest,
}


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = build_parser().parse_args(argv)
    cfg = load_config(args.config)
    COMMANDS[args.command](args, cfg)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Linha de comando do futdados. Use `futdados --help` para ver os subcomandos."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

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
    from .db import utc_now
    from .pipeline import project, projection_json
    from .reports import projection_markdown, write
    from .teams import display_name

    repo = _repo(cfg)
    # reconstituições (--as-of-round) usam pesos que viram o futuro: não entram no histórico
    table, meta = project(repo, cfg, args.season, args.round, args.as_of_round, args.sims,
                          record=args.as_of_round is None)
    _print_projection(table, meta)
    print(f"JSON: {projection_json(cfg, table, meta)}")
    if args.as_of_round is None:
        m = repo.matches(args.season)
        todo = m[m.status != "FINISHED"]
        last_full = meta["based_on_round"]
        adiados = todo[todo["round"] <= last_full]
        pending = {"restantes": len(todo),
                   "rodadas": f"{int(todo['round'].min())}–{int(todo['round'].max())}" if len(todo) else "—",
                   "adiados": ", ".join(f"{display_name(r.home_id)} x {display_name(r.away_id)} (R{r.round})"
                                        for r in adiados.itertuples())}
        md = projection_markdown(table, meta, display_name, cfg["output"]["aviso"], cfg["output"]["atribuicao"],
                                 utc_now(), pending)
        out = f"{cfg['paths']['reports']}/tabela_projetada_{args.season}.md"
        write(out, md)
        print(f"Relatório: {out}")


def cmd_backtest(args, cfg) -> None:
    """Placar entre modelos (walk-forward por temporada), ablação e relatórios."""
    import json
    from pathlib import Path

    import pandas as pd

    from .backtest.models import (
        ALL_MODELS,
        ablation,
        add_ensemble,
        all_oos,
        goal_mae,
        overdispersion,
        probs,
        scoreboard,
        season_bootstrap_diff,
    )
    from .backtest.walkforward import calibration_table
    from .model.poisson import Weights
    from .ratings.elo import EloParams
    from .reports import ablation_markdown, models_markdown, write

    repo = _repo(cfg)
    m = repo.matches()
    ep = repo.get_json("elo_params")
    if ep is None:
        raise SystemExit("Rode `futdados build-ratings` antes.")
    elo = EloParams(**{k: ep[k] for k in ("k", "home", "regression", "promoted")})
    try:
        hl = Weights.load(cfg["paths"]["weights"]).half_life_days
    except FileNotFoundError:
        hl = cfg["model"]["half_life_days"]
    first_train = int(cfg["model"]["train_first_season"])
    eval_seasons = cfg["backtest"]["test_seasons"]
    oos_seasons = list(range(min(eval_seasons) - 4, max(eval_seasons) + 1))
    df = all_oos(m, cfg, oos_seasons, elo, hl, first_train)
    df, ens = add_ensemble(df)
    tab, per, d = scoreboard(df, eval_seasons)
    diffs = {mm: season_bootstrap_diff(d, mm, "base_elo") for mm in ALL_MODELS if mm not in ("base_elo", "base_mandante")}
    pv = per.pivot(index="season", columns="modelo", values="rps")
    wins = {mm: f"{int((pv[mm] < pv['base_elo']).sum())} de {len(pv)}" for mm in ALL_MODELS if mm != "base_elo"}
    show = ["conjunto", "base_elo", "forcas_map", "poisson", "base_freq"]
    d["fase"] = pd.cut(d["round"], [0, 10, 28, 38], labels=["rodadas 1-10", "rodadas 11-28", "rodadas 29-38"])
    d["era"] = pd.cut(d.season, [2014, 2019, 2026], labels=["2015-2019", "2020-2026"])
    phases = d.groupby("fase", observed=True)[[f"rps_{x}" for x in show]].mean().set_axis(show, axis=1)
    eras_tab = d.groupby("era", observed=True)[[f"rps_{x}" for x in show]].mean().set_axis(show, axis=1)
    calib = calibration_table(probs(d, "conjunto"), d.y.to_numpy(), cfg["backtest"]["calibration_bins"])
    extra = {"n": len(d), "mae": goal_mae(d), "dispersao": overdispersion(d)}
    ab = ablation(m, cfg, eval_seasons, hl, first_train)
    write(f"{cfg['paths']['reports']}/backtest.md",
          models_markdown(tab, per, diffs, wins, extra, ens, eval_seasons, phases, eras_tab, calib))
    write(f"{cfg['paths']['reports']}/ablacao.md", ablation_markdown(ab))
    summary = {"temporadas": eval_seasons, "n": len(d), "placar": tab.to_dict("records"),
               "por_temporada": per.to_dict("records"), "diferenca_vs_elo": diffs, "temporadas_melhor_que_elo": wins,
               "por_fase": phases.reset_index().astype({"fase": str}).to_dict("records"),
               "por_era": eras_tab.reset_index().astype({"era": str}).to_dict("records"),
               "calibracao": calib.to_dict("records"), "extra": extra, "conjunto": ens,
               "ablacao": ab.to_dict("records"), "elo": ep}
    Path(cfg["paths"]["weights"]).with_name("backtest.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    print(tab.round(4).to_string(index=False))
    print(ab[["fator", "delta_rps", "decisao"]].to_string(index=False))
    print("Relatórios: reports/backtest.md e reports/ablacao.md")


def cmd_update(args, cfg) -> None:
    """Atualiza dados da temporada pela API e reestima os pesos."""
    cmd_ingest_api(args, cfg)
    cmd_fit(args, cfg)


def cmd_predict_round(args, cfg) -> None:
    from .pipeline import predict_round

    path, info = predict_round(_repo(cfg), cfg, args.season, args.round, repeat=args.repetir)
    rotulo = f"Rodada {info['round']}" if info["round"] is not None else "Sem rodada cheia pendente"
    print(f"{rotulo}: {info['games']} jogos da rodada, {info['postponed']} adiados; "
          f"{info['registered']} previsões novas gravadas no registro imutável.")
    for s in info["skipped"]:
        print(f"  Não gravado de novo: {s}")
    print(f"JSON: {path}")


def cmd_post_round(args, cfg) -> None:
    from .pipeline import post_round

    path, info = post_round(_repo(cfg), cfg, args.season, args.round)
    print(f"Rodada {args.round}: Brier {info['brier']:.4f} em {info['n']} jogos.")
    print(f"JSON: {path}")


def cmd_verify(args, cfg) -> None:
    ok = _repo(cfg).verify_prediction_chain()
    print("Cadeia de hashes do registro: " + ("íntegra" if ok else "QUEBRADA"))
    if not ok:
        raise SystemExit(1)


def cmd_simulate_season(args, cfg) -> None:
    from .pipeline import preseason_json, simulate_preseason
    from .teams import display_name, team_id

    teams = [team_id(t.strip()) for t in args.teams.split(",")] if args.teams else None
    table, meta = simulate_preseason(_repo(cfg), cfg, args.season, teams, args.sims)
    print(f"Pré-temporada {meta['season']} · calendário: {meta['calendar']} · {meta['n_sims']} simulações")
    pp = meta["prior_promovidos"]
    print(f"Prior dos promovidos: ataque {pp['ataque']:.2f}, defesa {pp['defesa']:.2f} (1,00 = média da liga)")
    print(f"{'#':>2} {'Time':<16}{'Pts esp.':>9}{'Faixa':>8}{'Título':>8}{'G4':>7}{'G6':>7}{'Reb.':>7}")
    for i, r in enumerate(table.itertuples(), start=1):
        name = display_name(r.team_id) + (" (P)" if r.promovido else "")
        faixa = f"{r.pos_p10:.0f}-{r.pos_p90:.0f}"
        print(f"{i:>2} {name:<16}{r.exp_points_final:>9.1f}{faixa:>8}{r.p_titulo:>8.1%}"
              f"{r.p_g4:>7.1%}{r.p_g6:>7.1%}{r.p_rebaixamento:>7.1%}")
    if meta["dias_sem_dados"] and meta["dias_sem_dados"] > 200:
        print(f"ALERTA: último jogo no histórico em {meta['ultimo_jogo_historico']}.")
    print(f"JSON: {preseason_json(cfg, table, meta)}")


def cmd_export_site(args, cfg) -> None:
    from .site_export import export_site

    out = export_site(_repo(cfg), cfg, args.season, args.as_of_round, args.sims)
    print(f"Dados do site em {out}. Para ver: cd site && npm run dev")


def cmd_coverage(args, cfg) -> None:
    """Flags de casos especiais, qualidade, cobertura 2006-2026 e divergências entre fontes."""
    from .ingest.reconcile import reconcile
    from .quality import closed_season_issues, compute_flags, coverage, quality_issues
    from .reports import coverage_markdown, divergence_markdown, write

    repo = _repo(cfg)
    m = repo.matches()
    repo.set_match_flags(compute_flags(m))
    m = repo.matches()
    issues = quality_issues(m)
    for s in sorted(m.season.unique()):
        if int(s) < args.current_season:
            issues += closed_season_issues(m, int(s))
    cov = coverage(m, 2006, args.current_season)
    flags = m.groupby("season")[["postponed", "rescheduled", "behind_closed_doors"]].sum()
    div, summary = reconcile(m, cfg)
    if not args.no_write:
        write(f"{cfg['paths']['reports']}/cobertura.md", coverage_markdown(cov, issues, flags))
        write(f"{cfg['paths']['reports']}/divergencias.md", divergence_markdown(div, summary))
    print(cov[["temporada", "esperados", "existentes", "encerrados", "fontes"]].to_string(index=False))
    print("Problemas de qualidade:", len(issues))
    for i in issues:
        print("  -", i)
    for s in summary:
        print(s)
    print("Relatórios: reports/cobertura.md e reports/divergencias.md")
    if issues and args.strict:
        raise SystemExit(1)


def cmd_metrics(args, cfg) -> None:
    """Recalcula o catálogo de métricas (tabelas derivadas no banco)."""
    from .metrics import build_all

    repo = _repo(cfg)
    out = build_all(repo.matches())
    for name in ("team_round_stats", "team_season_stats", "league_season_stats"):
        n = repo.replace_table(name, out[name].astype({c: "string" for c in out[name].columns if out[name][c].dtype == object}))
        print(f"{name}: {n} linhas")
    repo.put_json("pitagorico", out["pitagorico"])
    p = out["pitagorico"]
    print(f"Pitagórico: expoente {p['expoente']:.2f} (pontos/jogo = {p['intercepto']:.2f} + {p['inclinacao']:.2f} × fração)")


def cmd_build_ratings(args, cfg) -> None:
    """Calibra o Elo (K, regressão, promovidos; mando pelos dados) e grava a série de ratings."""
    from dataclasses import asdict

    from .ratings.elo import EloParams, calibrate, ratings_table, run_elo

    repo = _repo(cfg)
    m = repo.matches()
    best, table = calibrate(m, cfg["elo"]["tune_seasons"])
    repo.put_json("elo_params", {**asdict(best), "rps_ajuste": float(table.rps.iloc[0]),
                                 "temporadas_ajuste": cfg["elo"]["tune_seasons"]})
    r = run_elo(m, EloParams(**asdict(best)))
    n = repo.replace_table("elo_ratings", ratings_table(r))
    print(f"Elo: K={best.k:.0f}, mando={best.home:.0f}, regressão={best.regression:.2f}, "
          f"promovido={best.promoted:+.0f} (RPS no ajuste {table.rps.iloc[0]:.4f}); {n} linhas de rating")


def cmd_trends(args, cfg) -> None:
    """Tendências da liga e dos times (Theil-Sen, Mann-Kendall, LOESS, ponto de mudança, eras)."""
    from .reports import trends_markdown, write
    from .trends import league_trends, team_trends

    repo = _repo(cfg)
    lss, tss, elo = repo.table("league_season_stats"), repo.table("team_season_stats"), repo.table("elo_ratings")
    closed = lss[lss.encerrada.astype(bool)].season.astype(int).tolist()
    elo_end = elo.sort_values("kickoff_utc").groupby(["season", "team_id"]).tail(1)[["season", "team_id", "elo"]]
    lt = league_trends(lss)
    tt = team_trends(tss, elo_end, closed)
    repo.put_json("trends", {"liga": lt, "times": tt})
    write(f"{cfg['paths']['reports']}/tendencias.md", trends_markdown(lt))
    for _k, v in lt.items():
        print(f"{v['nome']:<45} {v['rotulo']:<20} Theil-Sen {v['theil_sen']['inclinacao']:+.3f}/ano  p={v['mann_kendall']['p']:.3f}")
    print("Relatório: reports/tendencias.md")


def cmd_cartola(args, cfg) -> None:
    """Rodada do Cartola: pontuação esperada, registro antes do fechamento, previsto x real das
    rodadas já encerradas e o melhor time para um orçamento (estudo, só local)."""
    from .cartola.optimize import best_team
    from .cartola.project import (
        cartola_report,
        describe_team,
        live_record,
        players_frame,
        project,
        register,
        registered_teams,
        write_site_json,
    )
    from .reports import write

    repo = _repo(cfg)
    doc = project(repo, cfg)
    digest = None if args.no_register else register(repo, cfg, doc, again=getattr(args, "regravar", False))
    doc["ao_vivo"] = live_record(repo, cfg, doc["temporada"], doc["rodada"])
    doc["times_gravados"] = registered_teams(repo, doc)
    path = write_site_json(doc, Path(cfg["paths"]["site_data"]) / "cartola.json")
    write(f"{cfg['paths']['reports']}/cartola.md", cartola_report(doc["backtest"], doc["ao_vivo"]))
    ev = doc["backtest"]
    print(f"Rodada {doc['rodada']}: {len(doc['atletas'])} atletas disponíveis. Temporadas no treino: {doc['temporadas_no_treino']}.")
    print(f"Backtest: erro {ev['mae_modelo']:.2f} x média {ev['mae_media']:.2f}; melhor em {ev['rodadas_modelo_melhor']} de {ev['rodadas']} rodadas.")
    print(f"Previsões gravadas no registro: {digest[:12] + '…' if digest else 'não (já gravada nesta rodada, mercado fechado ou --no-register)'}")
    for x in doc["ao_vivo"]:
        print(f"  Rodada {x['rodada']}: erro {x['erro_modelo']:.2f} x média {x['erro_media_cartola']:.2f}; "
              + "; ".join(f"C$ {b}: {v['esperado']:.1f} esperado, {v['real']:.1f} real" for b, v in x["times"].items()))
    if doc["jogos_fora_da_rodada"]:
        print("Jogos fora da rodada (não pontuam):", ", ".join(doc["jogos_fora_da_rodada"]))
    budget = args.budget if args.budget is not None else float(doc["cartoletas_iniciais"] or 100)
    res = best_team(players_frame(doc), budget, doc["esquemas"], doc["multiplicador_capitao"], args.esquema,
                    reserves=doc["reservas"], vice=doc["vice_capitao"])
    print(describe_team(res))
    print(f"Página /cartola atualizada (local, fora do git): {path}")


def cmd_backtest_sim(args, cfg) -> None:
    """Backtest da simulação de campeonato nas rodadas de corte 10, 20 e 30."""
    import json

    from .reports import write
    from .simulate.backtest_sim import markdown, run, summarize

    seasons = list(range(args.first, args.last + 1))
    df = run(_repo(cfg), cfg, seasons, [10, 20, 30], n_sims=args.sims)
    summ = summarize(df)
    write(f"{cfg['paths']['reports']}/backtest_simulacao.md", markdown(summ, seasons))
    Path(cfg["paths"]["weights"]).with_name("backtest_simulacao.json").write_text(
        json.dumps(summ, ensure_ascii=False, indent=1), encoding="utf-8")
    for r in summ["por_corte"]:
        print(f"Rodada {r['corte']}: Brier título {r['brier_titulo']:.3f} (base {r['brier_base_titulo']:.3f}), "
              f"G4 {r['brier_g4']:.3f} (base {r['brier_base_g4']:.3f}), rebaixamento {r['brier_rebaixamento']:.3f} "
              f"(base {r['brier_base_rebaixamento']:.3f}); faixa p10-p90 acertou {r['dentro_da_faixa']:.0%}")
    print("Relatório: reports/backtest_simulacao.md")


def cmd_atualizar(args, cfg) -> None:
    """Rotina completa da rodada, em ordem, seguindo em frente se uma etapa opcional falhar."""
    import os
    import traceback
    from types import SimpleNamespace

    season = int(args.season or cfg.get("temporada_atual", cfg["cartola"]["season"]))
    steps = []
    if os.environ.get("FOOTBALL_DATA_TOKEN"):
        steps.append(("Jogos da API football-data.org", lambda: cmd_ingest_api(SimpleNamespace(season=season), cfg)))
        steps.append(("Pesos do modelo", lambda: cmd_fit(SimpleNamespace(half_life=args.half_life), cfg)))
    else:
        print("Sem FOOTBALL_DATA_TOKEN: os jogos não serão atualizados (o resto roda com o que já está no banco).")
    steps += [
        ("Qualidade e flags dos jogos", lambda: cmd_coverage(SimpleNamespace(current_season=season, strict=False, no_write=False), cfg)),
        ("Métricas", lambda: cmd_metrics(SimpleNamespace(), cfg)),
        ("Elo", lambda: cmd_build_ratings(SimpleNamespace(), cfg)),
        ("Tendências", lambda: cmd_trends(SimpleNamespace(), cfg)),
        ("Previsões da rodada (registro)", lambda: cmd_predict_round(SimpleNamespace(season=season, round=None, repetir=False), cfg)),
        ("Cartola", lambda: cmd_cartola(SimpleNamespace(budget=None, esquema=None, no_register=False, regravar=False), cfg)),
        ("Site", lambda: cmd_export_site(SimpleNamespace(season=season, as_of_round=None, sims=None), cfg)),
    ]
    failed = []
    for name, fn in steps:
        print(f"\n=== {name} ===", flush=True)
        try:
            fn()
        except SystemExit as exc:
            if exc.code not in (0, None):
                failed.append(name)
        except Exception:  # noqa: BLE001 - uma etapa opcional não derruba as outras
            traceback.print_exc()
            failed.append(name)
    print("\nPronto." if not failed else f"\nTerminou com falha em: {', '.join(failed)}")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="futdados", description=__doc__)
    p.add_argument("--config", help="caminho do model.yaml")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("ingest-historical", help="carrega 2010-2024 do footballcsv (CC0)")
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
    s = sub.add_parser("update", help="ingest-api + fit (atualiza dados e pesos)")
    s.add_argument("--season", type=int, required=True)
    s.add_argument("--half-life", type=float, help="pula a escolha automática da meia-vida")
    s = sub.add_parser("predict-round", help="estima a próxima rodada e grava no registro")
    s.add_argument("--season", type=int, required=True)
    s.add_argument("--round", type=int,
                   help="padrão: primeira rodada sem nenhum jogo disputado (adiados à parte)")
    s.add_argument("--repetir", action="store_true",
                   help="grava nova previsão mesmo para jogo que já está no registro")
    s = sub.add_parser("post-round", help="compara estimado x real e atualiza a projeção")
    s.add_argument("--season", type=int, required=True)
    s.add_argument("--round", type=int, required=True)
    sub.add_parser("verify-registry", help="confere a cadeia de hashes das previsões")
    sub.add_parser("build-ratings", help="calibra o Elo e grava a série de ratings")
    sub.add_parser("trends", help="tendências da liga e dos times (precisa de metrics e build-ratings)")
    s = sub.add_parser("cartola", help="estudo: pontuação esperada no Cartola e melhor time para um orçamento")
    s.add_argument("--budget", type=float, help="cartoletas disponíveis (padrão: as iniciais do jogo)")
    s.add_argument("--esquema", help="fixa o esquema, ex.: 4-3-3 (padrão: o melhor)")
    s.add_argument("--no-register", action="store_true", help="não grava as previsões no registro")
    s.add_argument("--regravar", action="store_true", help="grava de novo mesmo que a rodada já tenha previsão gravada")
    s = sub.add_parser("backtest-sim", help="backtest da simulação de campeonato (rodadas 10, 20 e 30)")
    s.add_argument("--first", type=int, default=2015)
    s.add_argument("--last", type=int, default=2025)
    s.add_argument("--sims", type=int, default=4000)
    s = sub.add_parser("atualizar", help="rotina completa: API, pesos, métricas, Elo, previsões, Cartola e site")
    s.add_argument("--season", type=int, help="padrão: temporada_atual do model.yaml")
    s.add_argument("--half-life", type=float, default=180, help="meia-vida fixa (pula a escolha automática, mais rápido)")
    sub.add_parser("metrics", help="recalcula o catálogo de métricas (tabelas derivadas)")
    s = sub.add_parser("coverage", help="cobertura 2006-2026, qualidade e divergências entre fontes")
    s.add_argument("--current-season", type=int, default=2026, help="temporada em andamento")
    s.add_argument("--strict", action="store_true", help="sai com erro se houver problema de qualidade")
    s.add_argument("--no-write", action="store_true", help="só confere, sem regravar os relatórios")
    s = sub.add_parser("export-site", help="gera os dados do site estático em site/public/data")
    s.add_argument("--season", type=int, required=True)
    s.add_argument("--as-of-round", type=int, help="demonstração: reconstitui a temporada nesta rodada")
    s.add_argument("--sims", type=int, help="simulações da tabela projetada (padrão no YAML)")
    s = sub.add_parser("simulate-season", help="projeção de pré-temporada (campeonato inteiro)")
    s.add_argument("--season", type=int, required=True)
    s.add_argument("--teams", help="times separados por vírgula, se a API ainda não tem o calendário")
    s.add_argument("--sims", type=int, help="número de simulações (padrão no YAML: 10 mil)")
    return p


COMMANDS = {
    "ingest-historical": cmd_ingest_historical,
    "ingest-api": cmd_ingest_api,
    "fit": cmd_fit,
    "project": cmd_project,
    "backtest": cmd_backtest,
    "update": cmd_update,
    "predict-round": cmd_predict_round,
    "post-round": cmd_post_round,
    "verify-registry": cmd_verify,
    "simulate-season": cmd_simulate_season,
    "export-site": cmd_export_site,
    "coverage": cmd_coverage,
    "metrics": cmd_metrics,
    "build-ratings": cmd_build_ratings,
    "trends": cmd_trends,
    "cartola": cmd_cartola,
    "backtest-sim": cmd_backtest_sim,
    "atualizar": cmd_atualizar,
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

"""Pontuação esperada da próxima rodada do Cartola e dados para a página /cartola (só local)."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from ..db import Repository, utc_now
from ..model.features import build_features
from ..model.poisson import Weights, fit
from ..pipeline import season_features
from ..teams import display_name
from . import model as cm
from .ingest import ingest


def backtest(repo: Repository, cfg: dict, data: dict) -> tuple[dict, pd.DataFrame]:
    """Walk-forward na temporada: pesos do modelo de jogos só até a temporada anterior."""
    c = cfg["cartola"]
    w_live = Weights.load(cfg["paths"]["weights"])
    allf = build_features(repo.matches(), cfg["model"], half_life_days=w_live.half_life_days)
    season = int(data["status"]["temporada"])
    w_bt = fit(allf[(allf.season >= cfg["model"]["train_first_season"]) & (allf.season < season)], cfg["model"],
               w_live.half_life_days, bootstrap=0)
    feat = allf[allf.season == season]
    ctx = cm.match_context(data["partidas"], feat, w_bt)
    table = cm.training_table(data["pontos"], ctx, c["shrink"])
    pred = cm.walk_forward(table, c["first_backtest_round"], c["alpha"])
    return cm.evaluate(pred), pred


def project(repo: Repository, cfg: dict, refresh: bool = True) -> dict:
    c = cfg["cartola"]
    season = int(cfg["cartola"]["season"])
    data = ingest(Path(cfg["paths"]["db"]).parent / "cartola", season)
    status = data["status"]
    rnd = int(status["rodada_atual"])
    w = Weights.load(cfg["paths"]["weights"])
    feat = season_features(repo, cfg, w, season)
    ctx = cm.match_context(data["partidas"], feat, w)
    table = cm.training_table(data["pontos"], ctx, c["shrink"])
    coefs = cm.fit_position_models(table, c["alpha"])

    # média ajustada de cada atleta com todas as rodadas já disputadas
    played = data["pontos"][data["pontos"].jogou]
    agg = played.groupby("atleta_id").pontos.agg(["sum", "count"])
    pos_mean = played.groupby("posicao").pontos.mean()
    a = data["atletas"].copy()
    a = a[a.status.isin(c["p_jogar"].keys()) & a.team_id.notna()]
    a = a.join(agg, on="atleta_id")
    a[["sum", "count"]] = a[["sum", "count"]].fillna(0)
    a["media_ajustada"] = (a["sum"] + c["shrink"] * a.posicao.map(pos_mean)) / (a["count"] + c["shrink"])
    cur = ctx[ctx.rodada == rnd]
    a = a.merge(cur, on="team_id", how="inner")
    a = a[a.valida]  # jogo fora da rodada do Cartola não pontua
    a["previsto"] = cm.predict(a, coefs)
    a["p_jogar"] = a.status.map(c["p_jogar"]).astype(float)
    a["esperado"] = a.p_jogar * a.previsto
    players = []
    for _, r in a.iterrows():
        dec = cm.decompose(r, coefs[r.posicao])
        players.append({
            "id": int(r.atleta_id), "apelido": r.apelido, "time": r.team_id, "time_nome": display_name(r.team_id),
            "adversario": display_name(r.adversario), "mando": bool(r.mando), "posicao": r.posicao, "status": r.status,
            "preco": float(r.preco), "media_cartola": float(r.media), "jogos": int(r.jogos),
            "media_ajustada": round(float(r.media_ajustada), 2), "p_jogar": float(r.p_jogar),
            "previsto_se_jogar": round(float(r.previsto), 2), "esperado": round(float(r.esperado), 2),
            "contexto": {"p_sg": round(float(r.p_sg), 3), "gols_time": round(float(r.gols_time), 2),
                         "p_vitoria": round(float(r.p_vitoria), 3)},
            "fatores": {k: round(v, 2) for k, v in dec.items()},
        })
    schemes = {e["nome"]: e["posicoes"] for e in data["esquemas"]}
    ev, _ = backtest(repo, cfg, data)
    invalid = data["partidas"][(data["partidas"].rodada == rnd) & ~data["partidas"].valida]
    return {
        "aviso": cfg["output"]["aviso"], "atribuicao": cfg["output"]["atribuicao"], "gerado_em": utc_now(),
        "versao_modelo": w.model_version, "temporada": season, "rodada": rnd,
        "fechamento": status.get("fechamento"), "cartoletas_iniciais": status.get("cartoleta_inicial"),
        "multiplicador_capitao": c["captain_multiplier"], "p_jogar": c["p_jogar"],
        "esquemas": schemes, "atletas": sorted(players, key=lambda x: -x["esperado"]),
        "coeficientes": {pos: dict(zip(["base", *cm.FEATURES], map(float, v))) for pos, v in coefs.items()},
        "rotulos_fatores": cm.LABELS,
        "jogos_fora_da_rodada": [f"{display_name(r.home_id)} x {display_name(r.away_id)}" for r in invalid.itertuples()],
        "backtest": ev,
        "fonte": "API pública (não oficial) do Cartola FC, uso pessoal e local; contexto dos jogos: modelo futdados.",
    }


def write_site_json(doc: dict, path: str | Path) -> Path:
    from ..site_export import clean_json

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(clean_json(doc), ensure_ascii=False, indent=1, allow_nan=False), encoding="utf-8")
    return path


def players_frame(doc: dict) -> pd.DataFrame:
    return pd.DataFrame([{k: v for k, v in p.items() if k not in ("contexto", "fatores")} for p in doc["atletas"]])


def cartola_report(ev: dict) -> str:
    """Relatório agregado (sem dados de atletas: pode ser versionado)."""
    pp = ev["por_posicao"]
    lines = ["# Cartola FC: backtest da pontuação esperada (estudo de caso)", "",
             "Walk-forward dentro da temporada: cada rodada prevista só com rodadas anteriores; o modelo de jogos usado "
             "no contexto foi ajustado só até a temporada anterior. Avaliado em atletas que entraram em campo (a chance "
             "de jogar não é avaliada: não há histórico do status do mercado). Baseline: a média do próprio Cartola.", "",
             "| Métrica | Modelo | Média do Cartola |", "|---|---|---|",
             f"| Erro absoluto médio (pontos) | {ev['mae_modelo']:.3f} | {ev['mae_media']:.3f} |".replace(".", ","),
             f"| Correlação de ordem na posição (Spearman) | {ev['spearman_modelo']:.3f} | {ev['spearman_media']:.3f} |".replace(".", ","),
             f"| Rodadas em que o modelo erra menos | {ev['rodadas_modelo_melhor']} de {ev['rodadas']} | — |", "",
             "| Posição | Erro do modelo | Erro da média | Atletas-rodada |", "|---|---|---|---|"]
    for pos, v in pp.items():
        lines.append(f"| {pos} | {v['mae_modelo']:.3f} | {v['mae_media']:.3f} | {v['n']} |".replace(".", ","))
    lines += ["", "Ganho real, mas modesto: a pontuação do Cartola tem muito acaso e o modelo não sabe a escalação.", ""]
    return "\n".join(lines)


def describe_team(res: dict) -> str:
    if not res["ok"]:
        return res["motivo"]
    lines = [f"Esquema {res['esquema']} · custo C$ {res['custo']:.2f} de {res['orcamento']:.2f} · "
             f"pontuação esperada {res['pontos_esperados']:.1f}"]
    for r in res["time"].itertuples():
        cap = " (C)" if r.capitao else ""
        lines.append(f"  {r.posicao.upper():<4} {r.apelido:<22}{cap:<4} {r.time_nome:<14} C$ {r.preco:>6.2f}  esperado {r.esperado:>5.2f}")
    return "\n".join(lines)


_ = np  # numpy usado indiretamente pelos módulos acima

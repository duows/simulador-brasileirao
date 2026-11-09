"""Orquestração: projeção da tabela, previsões da rodada e pós-rodada.

Todas as saídas para vídeo passam por `video_json`, que acrescenta fontes, versão do
modelo, data de geração e o campo obrigatório "aviso".
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from .db import Repository, utc_now
from .model.poisson import Weights
from .model.predict import coach_extra, match_payload
from .model.features import build_features
from .simulate.montecarlo import simulate_season
from .teams import display_name

SOURCES = [
    {"nome": "football-data.org (API v4, competição BSA)", "url": "https://www.football-data.org",
     "uso": "jogos e classificação da temporada corrente"},
    {"nome": "footballcsv/cache.wfb (domínio público, CC0 1.0)", "url": "https://github.com/footballcsv/cache.wfb",
     "uso": "resultados históricos 2010-2024"},
]

LINGUAGEM = ("Os números são probabilidades estimadas pelo modelo e projeções. "
             "Descrevem o que é provável com base no desempenho recente e no histórico; "
             "não dizem o que vai acontecer.")


def load_weights(cfg) -> Weights:
    path = cfg["paths"]["weights"]
    if not Path(path).exists():
        raise FileNotFoundError("Pesos não encontrados. Rode `futdados fit` antes.")
    return Weights.load(path)


def video_json(cfg, w: Weights, tipo: str, dados: dict, slug: str) -> Path:
    doc = {
        "tipo": tipo,
        "gerado_em": utc_now(),
        "versao_modelo": w.model_version,
        "meia_vida_dias": w.half_life_days,
        "aviso": cfg["output"]["aviso"],
        "atribuicao": cfg["output"]["atribuicao"],
        "linguagem": LINGUAGEM,
        "fontes": SOURCES,
        **dados,
    }
    out = Path(cfg["paths"]["videos"]) / f"{slug}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def season_features(repo: Repository, cfg, w: Weights, season: int,
                    as_of_round: int | None = None,
                    extra_matches: list[dict] | None = None) -> pd.DataFrame:
    """Fatores de todos os jogos da temporada. Com `as_of_round`, esconde os resultados
    das rodadas seguintes (para reconstituir o que o modelo veria naquela data).
    `extra_matches` acrescenta jogos que não estão no banco (calendário gerado)."""
    matches = repo.matches()
    if extra_matches:
        extra = pd.DataFrame(extra_matches)
        extra["kickoff_utc"] = pd.to_datetime(extra["kickoff_utc"], utc=True)
        matches = pd.concat([matches, extra], ignore_index=True)
    if as_of_round is not None:
        hide = (matches.season == season) & (matches["round"] > as_of_round)
        matches.loc[hide, ["home_goals", "away_goals"]] = np.nan
        matches.loc[hide, "status"] = "SCHEDULED"
        # ignora tudo que veio depois da temporada (sem vazamento)
        matches = matches[matches.season <= season]
    feat = build_features(matches, cfg["model"], coach_extra(repo, cfg["paths"]["coach_changes"]),
                          half_life_days=w.half_life_days)
    return feat[feat.season == season].reset_index(drop=True)


def last_complete_round(feat: pd.DataFrame) -> int:
    done = feat.groupby("round").apply(lambda g: (g.status == "FINISHED").all(), include_groups=False)
    complete = done[done].index
    return int(complete.max()) if len(complete) else 0


# ------------------------------------------------------------------- projeção
def project(repo: Repository, cfg, season: int, target_round: int | None = None,
            as_of_round: int | None = None, n_sims: int | None = None,
            record: bool = True) -> tuple[pd.DataFrame, dict]:
    w = load_weights(cfg)
    feat = season_features(repo, cfg, w, season, as_of_round)
    max_round = int(feat["round"].max())
    target = max_round if target_round is None else int(target_round)
    based_on = last_complete_round(feat)
    table = simulate_season(feat, w, cfg, target, n_sims=n_sims)
    meta = {"season": season, "based_on_round": based_on, "target_round": target,
            "model_version": w.model_version, "n_sims": int(n_sims or cfg["simulation"]["n_sims"]),
            "max_round": max_round}
    if record:
        repo.insert_projection(meta, table)
    return table, meta


def projection_json(cfg, table: pd.DataFrame, meta: dict) -> Path:
    w = load_weights(cfg)
    linhas = []
    for i, r in enumerate(table.itertuples(), start=1):
        linhas.append({
            "posicao_projetada": i,
            "time": {"id": r.team_id, "nome": display_name(r.team_id)},
            "jogos": int(r.jogos), "pontos_atuais": int(r.pontos_atuais), "saldo_atual": int(r.saldo_atual),
            "pontos_esperados": round(float(r.exp_points), 1),
            "faixa_posicao": {"p10": int(round(r.pos_p10)), "mediana": int(round(r.pos_p50)),
                              "p90": int(round(r.pos_p90))},
            "pontos_esperados_fim": round(float(r.exp_points_final), 1),
            "chance_titulo": round(float(r.p_titulo), 4),
            "chance_g4": round(float(r.p_g4), 4),
            "chance_g6": round(float(r.p_g6), 4),
            "chance_rebaixamento": round(float(r.p_rebaixamento), 4),
        })
    titulo = (f"Tabela projetada depois da rodada {meta['target_round']}"
              + (" (fim do campeonato)" if meta["target_round"] == meta["max_round"] else ""))
    dados = {
        "titulo": titulo,
        "temporada": meta["season"],
        "resultados_reais_ate_rodada": meta["based_on_round"],
        "rodada_alvo": meta["target_round"],
        "simulacoes": meta["n_sims"],
        "metodo": ("Simulação Monte Carlo do restante do campeonato a partir da matriz de placares de "
                   "cada jogo. Ordem pelos pontos esperados; a faixa de posição vai do percentil 10 ao 90. "
                   "As chances de título, G4, G6 e rebaixamento referem-se ao fim do campeonato."),
        "criterios_desempate": cfg["simulation"]["tiebreakers"],
        "tabela": linhas,
    }
    slug = f"tabela-projetada-{meta['season']}-apos-r{meta['target_round']:02d}-base-r{meta['based_on_round']:02d}"
    return video_json(cfg, w, "tabela_projetada", dados, slug)


# --------------------------------------------------------- previsão da rodada
def next_round(feat: pd.DataFrame) -> int | None:
    pending = feat[feat.status != "FINISHED"]
    return None if pending.empty else int(pending["round"].min())


def predict_round(repo: Repository, cfg, season: int, round_: int | None = None,
                  now: pd.Timestamp | None = None) -> tuple[Path, dict]:
    """Estima os jogos da rodada, grava no registro imutável e gera o JSON do vídeo.

    Só jogos que ainda não começaram são registrados (o banco também recusa o contrário).
    """
    w = load_weights(cfg)
    now = now or pd.Timestamp.now(tz="UTC")
    feat = season_features(repo, cfg, w, season)
    rnd = round_ or next_round(feat)
    if rnd is None:
        raise ValueError(f"Não há jogos pendentes na temporada {season}.")
    games = feat[(feat["round"] == rnd) & (feat.status != "FINISHED")]
    jogos, skipped = [], []
    created = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    for _, row in games.iterrows():
        payload = match_payload(row, w, cfg["model"]["max_goals"])
        if pd.Timestamp(row["kickoff_utc"]) <= now:
            skipped.append(payload["inicio_utc"] + f" {row['home_id']} x {row['away_id']}")
            continue
        p = payload["probabilidade_estimada"]
        digest = repo.insert_prediction({
            "season": season, "round": rnd, "home_id": row["home_id"], "away_id": row["away_id"],
            "kickoff_utc": payload["inicio_utc"], "model_version": w.model_version,
            "lambda_home": payload["gols_esperados"]["mandante"],
            "lambda_away": payload["gols_esperados"]["visitante"],
            "p_home": p["mandante"], "p_draw": p["empate"], "p_away": p["visitante"], "payload": payload,
        }, created_at=created)
        payload["registro"] = {"gravado_em": created, "hash": digest}
        jogos.append(payload)

    # projeção antes da rodada (fica gravada para o pós-rodada comparar)
    table, meta = project(repo, cfg, season, None)
    focus = cfg["output"]["focus_team"]
    dados = {
        "titulo": f"Probabilidades estimadas pelo modelo · rodada {rnd} · {season}",
        "temporada": season, "rodada": rnd,
        "jogos": sorted(jogos, key=lambda j: j["inicio_utc"]),
        "jogos_nao_registrados_ja_iniciados": skipped,
        "time_foco": _focus_block(table, focus),
        "explicacao_fatores": ("Para cada time, 'efeito_gols' é quanto o fator somou ou tirou dos gols "
                               "esperados em relação aos gols base. A soma dos efeitos mais os gols base "
                               "dá os gols esperados."),
    }
    slug = f"rodada-{season}-r{rnd:02d}-estimativas"
    return video_json(cfg, w, "estimativas_rodada", dados, slug), {"round": rnd, "registered": len(jogos),
                                                                    "skipped": skipped, "meta": meta}


def _focus_block(table: pd.DataFrame, team: str) -> dict | None:
    row = table[table.team_id == team]
    if row.empty:
        return None
    r = row.iloc[0]
    return {"id": team, "nome": display_name(team), "pontos_atuais": int(r.pontos_atuais),
            "pontos_esperados_fim": round(float(r.exp_points_final), 1),
            "chance_titulo": round(float(r.p_titulo), 4), "chance_g4": round(float(r.p_g4), 4),
            "chance_g6": round(float(r.p_g6), 4), "chance_rebaixamento": round(float(r.p_rebaixamento), 4)}


# ------------------------------------------------------------------ pós-rodada
def post_round(repo: Repository, cfg, season: int, round_: int) -> tuple[Path, dict]:
    """Compara estimado x real, calcula o Brier da rodada e a variação das chances do time foco."""
    from .backtest.walkforward import brier, log_loss, outcome_index

    w = load_weights(cfg)
    preds = repo.predictions(season, round_)
    if preds.empty:
        raise ValueError(f"Nenhuma previsão registrada para a rodada {round_} de {season}.")
    preds = preds[preds.created_at < preds.kickoff_utc]
    preds = preds.sort_values("id").groupby(["home_id", "away_id"]).tail(1)  # última antes do jogo
    m = repo.matches(season)
    merged = preds.merge(m[["home_id", "away_id", "home_goals", "away_goals", "status"]],
                         on=["home_id", "away_id"])
    done = merged[merged.status == "FINISHED"].dropna(subset=["home_goals"])
    if done.empty:
        raise ValueError("Os jogos da rodada ainda não têm resultado no banco. Rode `update` antes.")
    y = outcome_index(done.home_goals, done.away_goals)
    p = done[["p_home", "p_draw", "p_away"]].to_numpy()
    labels = ["mandante", "empate", "visitante"]
    jogos = []
    for k, r in enumerate(done.itertuples()):
        jogos.append({
            "mandante": {"id": r.home_id, "nome": display_name(r.home_id)},
            "visitante": {"id": r.away_id, "nome": display_name(r.away_id)},
            "placar": {"mandante": int(r.home_goals), "visitante": int(r.away_goals)},
            "resultado": labels[y[k]],
            "probabilidade_estimada": {"mandante": r.p_home, "empate": r.p_draw, "visitante": r.p_away},
            "probabilidade_do_que_aconteceu": round(float(p[k, y[k]]), 4),
            "gols_esperados": {"mandante": r.lambda_home, "visitante": r.lambda_away},
            "brier_jogo": round(float(np.sum((p[k] - np.eye(3)[y[k]]) ** 2)), 4),
            "versao_modelo_da_previsao": r.model_version,
            "previsao_gravada_em": r.created_at,
            "hash_registro": r.hash,
        })

    max_round = int(m["round"].max())
    before = repo.projection(season, round_ - 1, max_round)
    reconstituted = False
    if before.empty:
        bt, _ = project(repo, cfg, season, None, as_of_round=round_ - 1, record=False)
        before, reconstituted = bt, True
    after, meta = project(repo, cfg, season, None)
    focus = cfg["output"]["focus_team"]

    def pick(df, col):
        row = df[df.team_id == focus]
        return float(row.iloc[0][col]) if not row.empty else None

    variacao = {}
    for col, name in (("p_titulo", "titulo"), ("p_g4", "g4"), ("p_g6", "g6"),
                      ("p_rebaixamento", "rebaixamento")):
        a, b = pick(before, col), pick(after, col)
        variacao[name] = None if a is None or b is None else {
            "antes": round(a, 4), "depois": round(b, 4), "variacao_pp": round(100 * (b - a), 1)}

    dados = {
        "titulo": f"Estimado x real · rodada {round_} · {season}",
        "temporada": season, "rodada": round_,
        "brier_rodada": round(brier(p, y), 4),
        "log_loss_rodada": round(log_loss(p, y), 4),
        "referencia_brier": {"backtest_modelo": "ver reports/backtest.md",
                             "chute_um_terco": round(2 / 3, 4)},
        "jogos": jogos,
        "time_foco": {"id": focus, "nome": display_name(focus), "variacao_chances": variacao,
                      "projecao_anterior_reconstituida": reconstituted},
        "tabela_projetada_atualizada": f"tabela-projetada-{season}-apos-r{max_round:02d}-base-r{meta['based_on_round']:02d}.json",
    }
    projection_json(cfg, after, meta)
    slug = f"pos-rodada-{season}-r{round_:02d}"
    return video_json(cfg, w, "pos_rodada", dados, slug), {"brier": dados["brier_rodada"], "n": len(jogos)}


# ------------------------------------------------------------- pré-temporada
def simulate_preseason(repo: Repository, cfg, season: int, teams: list[str] | None = None,
                       n_sims: int | None = None) -> tuple[pd.DataFrame, dict]:
    """Projeção de pré-temporada: nenhum jogo da temporada é considerado disputado.

    Calendário: o da API, se já estiver no banco; senão uma tabela balanceada gerada a
    partir de `teams`. A força inicial de cada time vem só das temporadas anteriores, com
    regressão à média; promovidos partem do desempenho histórico médio de promovidos.
    """
    from .simulate.schedule import generate_schedule

    w = load_weights(cfg)
    season_m = repo.matches(season)
    extra, calendar = None, "api"
    if season_m.empty:
        if not teams:
            raise ValueError(f"Não há calendário de {season} no banco. Rode `ingest-api --season "
                             f"{season}` ou informe os times com --teams.")
        pcfg = cfg.get("preseason", {})
        extra = generate_schedule(teams, season, pcfg.get("start_date", "04-11"),
                                  int(pcfg.get("kickoff_hour_utc", 22)))
        calendar = "gerado"
    elif season_m.status.eq("FINISHED").any():
        calendar = "api (resultados da temporada escondidos para a pré-temporada)"
    feat = season_features(repo, cfg, w, season, as_of_round=0, extra_matches=extra)
    table = simulate_season(feat, w, cfg, int(feat["round"].max()), n_sims=n_sims)

    # força inicial: fatores no primeiro jogo de cada time
    first = {}
    for r in feat.sort_values("kickoff_utc").itertuples():
        for tid, att, dfn, promo in ((r.home_id, r.ataque_h, r.defesa_adversario_a, r.raw_promoted_h),
                                     (r.away_id, r.ataque_a, r.defesa_adversario_h, r.raw_promoted_a)):
            first.setdefault(tid, (float(np.exp(att)), float(np.exp(dfn)), bool(promo)))
    table["ataque_inicial"] = table.team_id.map(lambda t: first[t][0])
    table["defesa_inicial"] = table.team_id.map(lambda t: first[t][1])
    table["promovido"] = table.team_id.map(lambda t: first[t][2])

    hist = repo.matches()
    hist = hist[(hist.season < season) & (hist.status == "FINISHED")]
    last_game = hist.kickoff_utc.max() if not hist.empty else None
    season_start = feat.kickoff_utc.min()
    gap_days = int((season_start - last_game).days) if last_game is not None else None
    meta = {"season": season, "calendar": calendar, "model_version": w.model_version,
            "n_sims": int(n_sims or cfg["simulation"]["n_sims"]), "max_round": int(feat["round"].max()),
            "prior_promovidos": {"ataque": round(float(feat.raw_prior_att.iloc[0]), 3),
                                 "defesa": round(float(feat.raw_prior_def.iloc[0]), 3)},
            "ultimo_jogo_historico": None if last_game is None else last_game.strftime("%Y-%m-%d"),
            "dias_sem_dados": gap_days}
    return table, meta


def preseason_json(cfg, table: pd.DataFrame, meta: dict) -> Path:
    w = load_weights(cfg)
    linhas = []
    for i, r in enumerate(table.itertuples(), start=1):
        linhas.append({
            "posicao_projetada": i,
            "time": {"id": r.team_id, "nome": display_name(r.team_id)},
            "promovido": bool(r.promovido),
            "forca_inicial": {"ataque": round(float(r.ataque_inicial), 3),
                              "defesa": round(float(r.defesa_inicial), 3),
                              "leitura": "1,00 = média da liga; ataque acima de 1 marca mais, "
                                         "defesa acima de 1 sofre mais"},
            "pontos_esperados": round(float(r.exp_points_final), 1),
            "faixa_posicao_final": {"p10": int(round(r.pos_p10)), "mediana": int(round(r.pos_p50)),
                                    "p90": int(round(r.pos_p90))},
            "chance_titulo": round(float(r.p_titulo), 4),
            "chance_g4": round(float(r.p_g4), 4),
            "chance_g6": round(float(r.p_g6), 4),
            "chance_rebaixamento": round(float(r.p_rebaixamento), 4),
        })
    alertas = []
    if meta["dias_sem_dados"] is not None and meta["dias_sem_dados"] > 200:
        alertas.append(f"O último jogo no histórico é de {meta['ultimo_jogo_historico']} "
                       f"({meta['dias_sem_dados']} dias antes do início). As forças podem estar "
                       "desatualizadas: complete as temporadas que faltam com `ingest-api`.")
    if meta["calendar"] == "gerado":
        alertas.append("Calendário gerado pelo sistema (tabela balanceada, uma rodada por semana). "
                       "Descanso e jogos no meio da semana não refletem o calendário oficial.")
    dados = {
        "titulo": f"Projeção de pré-temporada · Brasileirão {meta['season']}",
        "temporada": meta["season"],
        "calendario": meta["calendar"],
        "simulacoes": meta["n_sims"],
        "metodo": ("Antes da primeira rodada. A força inicial de cada time vem das temporadas anteriores, "
                   "com decaimento no tempo e regressão à média (5 jogos fictícios na média da liga). "
                   "Promovidos partem do desempenho médio histórico de promovidos no primeiro ano. "
                   "O campeonato inteiro é simulado a partir da matriz de placares de cada jogo; a faixa "
                   "de posição final vai do percentil 10 ao 90."),
        "prior_promovidos": meta["prior_promovidos"],
        "ultimo_jogo_historico": meta["ultimo_jogo_historico"],
        "alertas": alertas,
        "criterios_desempate": cfg["simulation"]["tiebreakers"],
        "tabela": linhas,
    }
    return video_json(cfg, w, "pre_temporada", dados, f"pre-temporada-{meta['season']}")

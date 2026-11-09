"""Geração dos relatórios em Markdown (reports/)."""

from __future__ import annotations

import math
from pathlib import Path

import pandas as pd

from .model.features import FEATURES
from .model.poisson import Weights

# Para cada fator: (variação típica usada no exemplo, frase do exemplo, nome amigável)
FACTOR_TEXT = {
    "ataque": (math.log(1.2), "um ataque 20% melhor que a média da liga", "Força de ataque (longo prazo)"),
    "defesa_adversario": (math.log(1.2), "um adversário que sofre 20% mais gols que a média",
                          "Fragilidade da defesa adversária (longo prazo)"),
    "mando": (1.0, "jogar em casa", "Mando de campo"),
    "forma": (1.0, "ter 1 ponto por jogo a mais que o adversário nos últimos 5 jogos",
              "Forma recente (últimos 5)"),
    "descanso": (3.0, "ter 3 dias a mais de descanso que o adversário", "Descanso"),
    "meio_de_semana": (1.0, "jogo de terça a quinta (vale para os dois times)", "Jogo no meio da semana"),
    "tecnico_novo": (1.0, "estar nos 5 primeiros jogos de um técnico novo (e o adversário não)",
                     "Troca recente de técnico"),
}


def pct(x: float) -> str:
    return f"{x:+.1%}".replace(".", ",")


def num(x: float, d: int = 3) -> str:
    return f"{x:.{d}f}".replace(".", ",")


def weights_markdown(w: Weights, tune: pd.DataFrame | None = None) -> str:
    lines = [
        "# Pesos do modelo",
        "",
        f"- Versão do modelo: `{w.model_version}`",
        f"- Ajustado em: {w.fitted_at}",
        f"- Temporadas de treino: {w.train_seasons[0]}–{w.train_seasons[-1]} ({w.n_matches} jogos)",
        f"- Meia-vida da força de longo prazo: {w.half_life_days:.0f} dias",
        f"- Intercepto: {num(w.intercept)} (gols esperados base = média da liga × {num(math.exp(w.intercept))})",
        f"- Ajuste de placares baixos (Dixon-Coles, rho): {num(w.rho, 4)}",
        "",
        "Fórmula: `log(gols esperados) = log(média da liga) + intercepto + Σ peso × fator`.",
        "O intervalo é de 95%, por bootstrap de jogos. Quando ele cruza o zero, os dados",
        "não permitem afirmar que o fator tem efeito.",
        "",
        "| Fator | Peso | Intervalo 95% | O que significa |",
        "|---|---|---|---|",
    ]
    for f in FEATURES:
        step, phrase, label = FACTOR_TEXT[f]
        b = w.coef[f]
        lo, hi = w.ci_low.get(f, float("nan")), w.ci_high.get(f, float("nan"))
        eff = math.exp(b * step) - 1
        clear = not (lo <= 0 <= hi)
        meaning = f"{phrase.capitalize()} muda os gols esperados em {pct(eff)}."
        if w.feature_std.get(f, 1.0) == 0:
            meaning = "Sem dados no histórico (fator sempre 0): peso não estimável, fixado em 0."
        elif not clear:
            meaning += " Efeito não distinguível de zero."
        lines.append(f"| {label} | {num(b)} | [{num(lo)}; {num(hi)}] | {meaning} |")
    lines += [
        "",
        "## Como ler",
        "",
        "- **Ataque e defesa** são taxas de gols com decaimento: um jogo de "
        f"{w.half_life_days:.0f} dias atrás vale metade de um jogo de hoje. Os gols são ajustados "
        "pela força do adversário. Cada time é puxado para a média com 5 jogos fictícios "
        "(regressão à média); promovidos são puxados para o desempenho médio histórico de "
        "promovidos no primeiro ano, estimado só com temporadas anteriores.",
        "- Pesos de ataque e defesa menores que 1 significam que a diferença observada entre os "
        "times é em parte ruído: o modelo puxa as forças em direção à média.",
        "- **Forma** é medida além da força de longo prazo. Peso pequeno quer dizer que a "
        "sequência recente acrescenta pouco ao que o histórico com decaimento já captura.",
        "- **Descanso** só conta jogos da Série A (copas não estão nos dados). Ver limitações no README.",
        "- **Técnico novo**: a fonte histórica (footballcsv) não traz técnicos, então o fator vale "
        "0 em todo o histórico e o peso não é estimável (fica 0). Só passa a contar quando houver "
        "trocas registradas (API ou config/coach_changes.csv) **e** um histórico com técnicos para estimar o peso.",
    ]
    if tune is not None and not tune.empty:
        lines += ["", "## Escolha da meia-vida (walk-forward nas temporadas de ajuste)", "",
                  "| Meia-vida (dias) | Brier | Log loss | Jogos |", "|---|---|---|---|"]
        for r in tune.itertuples():
            lines.append(f"| {r.meia_vida_dias:.0f} | {num(r.brier, 4)} | {num(r.log_loss, 4)} | {r.n} |")
    return "\n".join(lines) + "\n"


def write(path: str | Path, text: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(text, encoding="utf-8")


def p1(x: float) -> str:
    """Percentual com 1 casa; valores raros mas possíveis não aparecem como 0% ou 100%."""
    if 0 < x < 0.0005:
        return "<0,1%"
    if 0.9995 <= x < 1:
        return ">99,9%"
    return f"{x:.1%}".replace(".", ",")


def backtest_markdown(scores: dict, per_season: pd.DataFrame, calib: pd.DataFrame,
                      half_life: float, seasons: list[int], n: int, draw_rate: tuple[float, float]) -> str:
    m, f, h = scores["modelo"], scores["frequencia_historica"], scores["sempre_mandante"]
    beats_freq = m["brier"] < f["brier"] and m["log_loss"] < f["log_loss"]
    gain_b = (f["brier"] - m["brier"]) / f["brier"]
    gain_l = (f["log_loss"] - m["log_loss"]) / f["log_loss"]
    worse = per_season[per_season.brier_modelo >= per_season.brier_freq].temporada.tolist()
    verdict = (
        f"O modelo **supera os dois baselines** no Brier e no log loss. A vantagem sobre a "
        f"frequência histórica é de {p1(gain_b)} no Brier e {p1(gain_l)} no log loss: real, mas "
        "pequena. Futebol tem muito acaso e um modelo sem escalação e sem xG não vai muito além disso."
        if beats_freq else
        "O modelo **não supera** a frequência histórica em todas as métricas. Ver detalhes abaixo."
    )
    lines = [
        "# Backtest walk-forward",
        "",
        f"Temporadas de teste: {seasons[0]}–{seasons[-1]} ({n} jogos). Para prever a temporada S, os "
        "pesos foram ajustados só com temporadas anteriores a S, e os fatores de cada jogo usam só "
        "resultados anteriores àquele jogo. A meia-vida "
        f"({half_life:.0f} dias) foi escolhida em temporadas anteriores ao período de teste.",
        "",
        "## Resultado",
        "",
        verdict,
        "",
        "| Método | Brier (menor é melhor) | Log loss (menor é melhor) | Acerto do resultado mais provável |",
        "|---|---|---|---|",
        f"| Modelo | {num(m['brier'], 4)} | {num(m['log_loss'], 4)} | {p1(m['acerto'])} |",
        f"| Frequência histórica (mandante/empate/visitante) | {num(f['brier'], 4)} | {num(f['log_loss'], 4)} | {p1(f['acerto'])} |",
        f"| Sempre mandante (100% vitória do mandante) | {num(h['brier'], 4)} | {num(h['log_loss'], 2)}* | {p1(h['acerto'])} |",
        "",
        "\\* \"Sempre mandante\" dá probabilidade zero a empates e derrotas, então o log loss é "
        "enorme (limitado numericamente). Ele serve de referência de acerto, não de probabilidade.",
        "",
        "Brier multiclasse: soma dos erros quadráticos nas três classes (0 = perfeito, 2 = pior "
        "possível; chutar 1/3 para tudo dá 0,667).",
        "",
        "## Por temporada",
        "",
        "| Temporada | Jogos | Brier modelo | Brier frequência | Log loss modelo | Log loss frequência |",
        "|---|---|---|---|---|---|",
    ]
    for r in per_season.itertuples():
        lines.append(f"| {r.temporada} | {r.n} | {num(r.brier_modelo, 4)} | {num(r.brier_freq, 4)} | "
                     f"{num(r.ll_modelo, 4)} | {num(r.ll_freq, 4)} |")
    if worse:
        lines += ["", f"Temporadas em que o modelo **não** bateu a frequência histórica no Brier: "
                      f"{', '.join(map(str, worse))}."]
    lines += [
        "",
        "## Calibração",
        "",
        "Se o modelo diz 40%, o evento deveria acontecer perto de 40% das vezes.",
        f"Empates: o modelo estimou em média {p1(draw_rate[0])} e aconteceram {p1(draw_rate[1])}.",
        "",
        "| Resultado | Faixa estimada | Jogos | Estimado (média) | Observado |",
        "|---|---|---|---|---|",
    ]
    for r in calib.itertuples():
        if r.n < 20:
            continue
        lines.append(f"| {r.resultado} | {r.faixa} | {r.n} | {p1(r.estimado)} | {p1(r.observado)} |")
    lines += ["", "Faixas com menos de 20 jogos foram omitidas.", ""]
    return "\n".join(lines)


def projection_markdown(table: pd.DataFrame, meta: dict, display, aviso: str, atribuicao: str,
                        generated_at: str, pending: dict | None = None) -> str:
    """Tabela projetada em Markdown (para ler sem abrir JSON)."""
    target = meta["target_round"]
    fim = target == meta["max_round"]
    lines = [
        f"# Tabela projetada {meta['season']} · depois da rodada {target}{' (fim do campeonato)' if fim else ''}",
        "",
        f"- Resultados reais até a rodada {meta['based_on_round']} (última rodada completa).",
    ]
    if pending:
        lines.append(f"- Jogos que faltam: {pending['restantes']} "
                     f"(rodadas {pending['rodadas']}{', inclui adiados: ' + pending['adiados'] if pending['adiados'] else ''}).")
    lines += [
        f"- {meta['n_sims']:,} simulações Monte Carlo · modelo `{meta['model_version']}` · gerado em {generated_at}.".replace(",", "."),
        "- Ordem pelos pontos esperados no fim. Faixa = percentis 10 e 90 da posição final.",
        "",
        "| # | Time | J | Pts | Pts esperados | Faixa (p10–p90) | Título | G4 | G6 | Rebaixamento |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for i, r in enumerate(table.itertuples(), start=1):
        lines.append(
            f"| {i} | {display(r.team_id)} | {r.jogos} | {r.pontos_atuais} | {num(r.exp_points_final, 1)} | "
            f"{r.pos_p10:.0f}º–{r.pos_p90:.0f}º | {p1(r.p_titulo)} | {p1(r.p_g4)} | {p1(r.p_g6)} | "
            f"{p1(r.p_rebaixamento)} |")
    lines += ["", f"_{aviso}_", "", f"{atribuicao}.", ""]
    return "\n".join(lines)


def coverage_markdown(cov: pd.DataFrame, issues: list[str], flags: pd.DataFrame) -> str:
    lines = ["# Cobertura de dados 2006-2026", "",
             "Jogos esperados contra existentes no banco, por temporada, com a fonte usada e a licença.",
             "Regra de fonte: football-data.org > footballcsv > adaoduque (este só local, nunca no banco).", "",
             "| Temporada | Esperados | No banco | Encerrados | Adiados | Remarcados | Portões fechados | Fonte | Licença |",
             "|---|---|---|---|---|---|---|---|---|"]
    for r in cov.itertuples():
        f = flags.loc[r.temporada] if r.temporada in flags.index else None
        fl = (int(f.postponed), int(f.rescheduled), int(f.behind_closed_doors)) if f is not None else (0, 0, 0)
        ok = "" if r.existentes == r.esperados else " ⚠"
        lines.append(f"| {r.temporada} | {r.esperados} | {r.existentes}{ok} | {r.encerrados} | {fl[0]} | {fl[1]} | {fl[2]} | {r.fontes} | {r.licenca} |")
    notes = [(r.temporada, r.notas) for r in cov.itertuples() if r.notas]
    if notes:
        lines += ["", "## Notas por temporada", ""] + [f"- **{s}**: {n}" for s, n in notes]
    lines += ["", "## Checagens de qualidade", ""]
    lines += [f"- ⚠ {i}" for i in issues] or ["- Nenhum problema: sem duplicados, placares válidos, sem time com dois jogos na mesma rodada, turno e returno simétricos, 38 jogos por time e soma de pontos consistente nas temporadas encerradas."]
    lines += ["", "Flags: adiado = não disputado numa rodada que já teve jogos; remarcado = disputado a 7+ dias da data "
              "mediana da rodada; portões fechados = período definido em config/seasons.yaml. Campo neutro: sem fonte (TODO).", ""]
    return "\n".join(lines)


def divergence_markdown(div: pd.DataFrame, summary: list[str]) -> str:
    lines = ["# Divergências entre fontes", "",
             "Onde duas fontes cobrem o mesmo jogo, comparamos placar e data. O banco guarda a fonte de maior "
             "prioridade (football-data.org > footballcsv > adaoduque local); nada é escolhido em silêncio.", ""]
    lines += [f"- {s}" for s in summary] + [""]
    if div is None or div.empty:
        lines.append("Nenhuma divergência de placar ou de data (mais de 1 dia) nos jogos em comum.")
    else:
        lines += ["| Temporada | Mandante | Visitante | Tipo | Banco | Outra fonte | Fonte comparada |", "|---|---|---|---|---|---|---|"]
        for r in div.itertuples():
            lines.append(f"| {r.season} | {r.home_id} | {r.away_id} | {r.tipo} | {r.banco} | {r.outra} | {r.fonte_comparada} |")
    return "\n".join(lines) + "\n"


def trends_markdown(lt: dict) -> str:
    lines = ["# Tendências do Brasileirão (temporadas encerradas desde 2006)", "",
             "São no máximo 20 temporadas: tendências curtas são frágeis. O rótulo só diz \"em alta\" ou \"em queda\" "
             "quando o teste de Mann-Kendall tem p < 0,05; senão, \"sem tendência clara\". A inclinação robusta (Theil-Sen) "
             "vem com intervalo de 90%. Ponto de mudança = ano em que a média muda, se a mudança compensar a penalidade.", "",
             "| Série | Rótulo | Inclinação por ano (IC 90%) | p (Mann-Kendall) | Mudança de média | Médias por era | Eras diferem? |",
             "|---|---|---|---|---|---|---|"]
    for v in lt.values():
        ts = v["theil_sen"]
        mud = v.get("mudanca")
        mud_txt = f"{mud['ano']}: {num(mud['media_antes'], 2)} → {num(mud['media_depois'], 2)}" if mud else "—"
        eras = " · ".join(f"{k}: {num(x, 2)}" for k, x in v["eras"]["medias"].items())
        lines.append(f"| {v['nome']} | {v['rotulo']} | {num(ts['inclinacao'], 3)} ({num(ts['ic90'][0], 3)} a {num(ts['ic90'][1], 3)}) | "
                     f"{num(v['mann_kendall']['p'], 3)} | {mud_txt} | {eras} | {'sim' if v['eras']['diferenca_clara'] else 'não'} (p={num(v['eras']['kruskal_p'], 3)}) |")
    return "\n".join(lines) + "\n"


MODEL_NAMES = {
    "conjunto": "Conjunto (média ponderada)", "conjunto_calibrado": "Conjunto calibrado (temperatura)",
    "forcas_map": "Forças por time (MAP, reajuste por rodada)", "base_elo": "Baseline: Elo puro",
    "ordinal": "Logística ordinal com fatores", "poisson": "Poisson de 7 fatores",
    "dixon_coles": "Poisson + Dixon-Coles", "boosting": "Gradient boosting", "base_freq": "Baseline: frequência histórica",
    "base_mandante": "Baseline: sempre mandante",
}


def _signed(x: float, d: int = 4) -> str:
    return f"{x:+.{d}f}".replace(".", ",")


def models_markdown(tab, per, diffs, wins, extra, ensemble_info, eval_seasons, phases, eras_tab, calib) -> str:
    lines = ["# Backtest walk-forward: placar entre modelos", "",
             f"Temporadas avaliadas: {eval_seasons[0]}–{eval_seasons[-1]} ({extra['n']} jogos; 2026 só com jogos já disputados). "
             "Para prever cada temporada, cada modelo só usou temporadas anteriores para estimar parâmetros; ratings e "
             "fatores de cada jogo usam só o que aconteceu antes dele. O conjunto e a calibração usam só previsões fora da "
             "amostra de temporadas anteriores. Métrica principal: **RPS** (ranked probability score, menor é melhor), que "
             "respeita a ordem vitória do mandante < empate < vitória do visitante.", "",
             "## Placar geral", "",
             "| Modelo | RPS | Log loss | Brier | Acerto | Diferença de RPS para o Elo (IC 90%) | Temporadas melhor que o Elo |",
             "|---|---|---|---|---|---|---|"]
    for r in tab.itertuples():
        d = diffs.get(r.modelo)
        dtxt = "—" if d is None else f"{_signed(d[0])} ({_signed(d[1])} a {_signed(d[2])})"
        ll = num(r.log_loss, 4) if r.log_loss < 5 else "infinito"
        lines.append(f"| {MODEL_NAMES.get(r.modelo, r.modelo)} | {num(r.rps, 4)} | {ll} | {num(r.brier, 4)} | "
                     f"{p1(r.acerto)} | {dtxt} | {wins.get(r.modelo, '—')} |")
    best = tab.iloc[0].modelo
    b = diffs[best]
    lines += ["", "## Conclusão honesta", "",
              f"- O melhor resultado é do **{MODEL_NAMES[best]}**, mas a vantagem sobre o **Elo puro** (um baseline) é "
              f"minúscula e o intervalo cruza o zero: {_signed(b[0])} ({_signed(b[1])} a {_signed(b[2])}).",
              f"- O **Poisson de 7 fatores** que estava em produção perde do Elo puro (melhor que o Elo em "
              f"{wins['poisson']} temporadas) e a diferença é clara. Ele continua bem melhor que a frequência histórica.",
              "- Todos os modelos (menos \"sempre mandante\") ganham com folga da frequência histórica: cerca de 5% no RPS.",
              "- Dixon-Coles, gradient boosting e calibração por temperatura **não melhoram**: ficam desligados.",
              f"- Sem sobredispersão: razão de Pearson {num(extra['dispersao']['dispersao_pearson'], 2)} (≈ 1 é Poisson). "
              "Binomial Negativa não foi adotada.",
              f"- Erro médio absoluto de gols por time: Poisson {num(extra['mae']['poisson'], 3)}, forças por time "
              f"{num(extra['mae']['forcas_map'], 3)}.", "",
              "## Por fase da temporada (RPS)", "",
              "| Fase | " + " | ".join(MODEL_NAMES[m] for m in phases.columns) + " |",
              "|---" * (len(phases.columns) + 1) + "|"]
    for idx, r in phases.iterrows():
        lines.append(f"| {idx} | " + " | ".join(num(v, 4) for v in r) + " |")
    lines += ["", "## Por era (RPS)", "", "| Era | " + " | ".join(MODEL_NAMES[m] for m in eras_tab.columns) + " |",
              "|---" * (len(eras_tab.columns) + 1) + "|"]
    for idx, r in eras_tab.iterrows():
        lines.append(f"| {idx} | " + " | ".join(num(v, 4) for v in r) + " |")
    show = ["conjunto", "base_elo", "forcas_map", "poisson", "base_freq"]
    lines += ["", "## Por temporada (RPS)", "", "| Temporada | " + " | ".join(MODEL_NAMES[m] for m in show) + " |",
              "|---" * (len(show) + 1) + "|"]
    pv = per.pivot(index="season", columns="modelo", values="rps")
    for s, r in pv.iterrows():
        lines.append(f"| {s} | " + " | ".join(num(r[m], 4) for m in show) + " |")
    last_season = max(ensemble_info)
    last = ensemble_info[last_season]
    lines += ["", "## Conjunto", "",
              f"Pesos estimados nas 5 temporadas anteriores, minimizando RPS. Pesos usados em {last_season}: "
              + ", ".join(f"{MODEL_NAMES[k]} {p1(v)}" for k, v in last["pesos"].items()) + ".", "",
              "## Calibração do conjunto", "", "| Resultado | Faixa | Jogos | Estimado | Observado |", "|---|---|---|---|---|"]
    for r in calib.itertuples():
        if r.n >= 30:
            lines.append(f"| {r.resultado} | {r.faixa} | {r.n} | {p1(r.estimado)} | {p1(r.observado)} |")
    lines += ["", "## Ablação dos fatores do Poisson", "", "Ver [ablacao.md](ablacao.md).", ""]
    return "\n".join(lines)


def ablation_markdown(ab) -> str:
    lines = ["# Ablação dos fatores (modelo Poisson)", "",
             "Para cada fator: quanto o RPS fora da amostra piora quando ele é retirado (positivo = o fator ajuda), com "
             "IC 90% por bootstrap de temporadas. Fator sem ganho fica documentado como neutro, não é apagado.", "",
             "| Fator | Δ RPS sem o fator | IC 90% | Decisão |", "|---|---|---|---|"]
    for r in ab.itertuples():
        if r.delta_rps != r.delta_rps:
            lines.append(f"| {r.fator} | — | — | {r.decisao} |")
        else:
            lines.append(f"| {r.fator} | {_signed(r.delta_rps, 5)} | {_signed(r.ic90[0], 5)} a {_signed(r.ic90[1], 5)} | {r.decisao} |")
    return "\n".join(lines) + "\n"

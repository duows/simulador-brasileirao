# Backtest walk-forward: placar entre modelos

Temporadas avaliadas: 2015–2026 (4518 jogos; 2026 só com jogos já disputados). Para prever cada temporada, cada modelo só usou temporadas anteriores para estimar parâmetros; ratings e fatores de cada jogo usam só o que aconteceu antes dele. O conjunto e a calibração usam só previsões fora da amostra de temporadas anteriores. Métrica principal: **RPS** (ranked probability score, menor é melhor), que respeita a ordem vitória do mandante < empate < vitória do visitante.

## Placar geral

| Modelo | RPS | Log loss | Brier | Acerto | Diferença de RPS para o Elo (IC 90%) | Temporadas melhor que o Elo |
|---|---|---|---|---|---|---|
| Conjunto (média ponderada) | 0,2069 | 1,0165 | 0,6092 | 50,0% | -0,0002 (-0,0006 a +0,0001) | 8 de 12 |
| Conjunto calibrado (temperatura) | 0,2070 | 1,0171 | 0,6096 | 50,0% | -0,0001 (-0,0004 a +0,0003) | 6 de 12 |
| Forças por time (MAP, reajuste por rodada) | 0,2071 | 1,0171 | 0,6096 | 50,0% | -0,0000 (-0,0007 a +0,0007) | 6 de 12 |
| Baseline: Elo puro | 0,2071 | 1,0173 | 0,6098 | 49,8% | — | — |
| Logística ordinal com fatores | 0,2072 | 1,0177 | 0,6100 | 50,1% | +0,0001 (-0,0002 a +0,0005) | 5 de 12 |
| Poisson de 7 fatores | 0,2084 | 1,0214 | 0,6125 | 49,6% | +0,0013 (+0,0009 a +0,0017) | 0 de 12 |
| Poisson + Dixon-Coles | 0,2085 | 1,0215 | 0,6126 | 49,6% | +0,0013 (+0,0009 a +0,0017) | 1 de 12 |
| Gradient boosting | 0,2115 | 1,0384 | 0,6229 | 48,7% | +0,0044 (+0,0031 a +0,0059) | 0 de 12 |
| Baseline: frequência histórica | 0,2184 | 1,0513 | 0,6333 | 48,3% | +0,0113 (+0,0089 a +0,0137) | 0 de 12 |
| Baseline: sempre mandante | 0,3827 | infinito | 1,0341 | 48,3% | — | 0 de 12 |

## Conclusão honesta

- O melhor resultado é do **Conjunto (média ponderada)**, mas a vantagem sobre o **Elo puro** (um baseline) é minúscula e o intervalo cruza o zero: -0,0002 (-0,0006 a +0,0001).
- O **Poisson de 7 fatores** que estava em produção perde do Elo puro (melhor que o Elo em 0 de 12 temporadas) e a diferença é clara. Ele continua bem melhor que a frequência histórica.
- Todos os modelos (menos "sempre mandante") ganham com folga da frequência histórica: cerca de 5% no RPS.
- Dixon-Coles, gradient boosting e calibração por temperatura **não melhoram**: ficam desligados.
- Sem sobredispersão: razão de Pearson 0,95 (≈ 1 é Poisson). Binomial Negativa não foi adotada.
- Erro médio absoluto de gols por time: Poisson 0,828, forças por time 0,825.

## Por fase da temporada (RPS)

| Fase | Conjunto (média ponderada) | Baseline: Elo puro | Forças por time (MAP, reajuste por rodada) | Poisson de 7 fatores | Baseline: frequência histórica |
|---|---|---|---|---|---|
| rodadas 1-10 | 0,2050 | 0,2052 | 0,2059 | 0,2077 | 0,2146 |
| rodadas 11-28 | 0,2092 | 0,2098 | 0,2090 | 0,2099 | 0,2205 |
| rodadas 29-38 | 0,2044 | 0,2041 | 0,2048 | 0,2065 | 0,2184 |

## Por era (RPS)

| Era | Conjunto (média ponderada) | Baseline: Elo puro | Forças por time (MAP, reajuste por rodada) | Poisson de 7 fatores | Baseline: frequência histórica |
|---|---|---|---|---|---|
| 2015-2019 | 0,2050 | 0,2048 | 0,2051 | 0,2064 | 0,2153 |
| 2020-2026 | 0,2082 | 0,2087 | 0,2085 | 0,2099 | 0,2207 |

## Por temporada (RPS)

| Temporada | Conjunto (média ponderada) | Baseline: Elo puro | Forças por time (MAP, reajuste por rodada) | Poisson de 7 fatores | Baseline: frequência histórica |
|---|---|---|---|---|---|
| 2015 | 0,2074 | 0,2068 | 0,2094 | 0,2083 | 0,2147 |
| 2016 | 0,2045 | 0,2045 | 0,2059 | 0,2056 | 0,2105 |
| 2017 | 0,2282 | 0,2277 | 0,2259 | 0,2287 | 0,2300 |
| 2018 | 0,1871 | 0,1872 | 0,1875 | 0,1887 | 0,2000 |
| 2019 | 0,1980 | 0,1980 | 0,1970 | 0,2008 | 0,2211 |
| 2020 | 0,2121 | 0,2129 | 0,2116 | 0,2151 | 0,2232 |
| 2021 | 0,2079 | 0,2086 | 0,2087 | 0,2087 | 0,2174 |
| 2022 | 0,2086 | 0,2093 | 0,2090 | 0,2116 | 0,2248 |
| 2023 | 0,2154 | 0,2168 | 0,2150 | 0,2173 | 0,2248 |
| 2024 | 0,2103 | 0,2101 | 0,2111 | 0,2108 | 0,2213 |
| 2025 | 0,2004 | 0,2016 | 0,2004 | 0,2020 | 0,2155 |
| 2026 | 0,2020 | 0,2011 | 0,2032 | 0,2030 | 0,2174 |

## Conjunto

Pesos estimados nas 5 temporadas anteriores, minimizando RPS. Pesos usados em 2026: Poisson de 7 fatores <0,1%, Baseline: Elo puro 40,7%, Logística ordinal com fatores <0,1%, Forças por time (MAP, reajuste por rodada) 59,3%.

## Calibração do conjunto

| Resultado | Faixa | Jogos | Estimado | Observado |
|---|---|---|---|---|
| mandante | 20%-30% | 181 | 27,1% | 21,5% |
| mandante | 30%-40% | 835 | 35,9% | 36,5% |
| mandante | 40%-50% | 1502 | 45,1% | 43,2% |
| mandante | 50%-60% | 1295 | 54,7% | 55,7% |
| mandante | 60%-70% | 604 | 64,0% | 65,9% |
| mandante | 70%-80% | 91 | 73,5% | 74,7% |
| empate | 10%-20% | 184 | 18,1% | 16,8% |
| empate | 20%-30% | 4188 | 26,7% | 27,1% |
| empate | 30%-40% | 145 | 30,7% | 32,4% |
| visitante | 0%-10% | 53 | 8,6% | 13,2% |
| visitante | 10%-20% | 1325 | 16,2% | 14,9% |
| visitante | 20%-30% | 1954 | 24,7% | 24,8% |
| visitante | 30%-40% | 941 | 33,9% | 33,7% |
| visitante | 40%-50% | 221 | 43,5% | 45,2% |

## Ablação dos fatores do Poisson

Ver [ablacao.md](ablacao.md).

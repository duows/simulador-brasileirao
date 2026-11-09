# Cartola FC: quanto o modelo erra (estudo de caso)

## Backtest da temporada

Walk-forward: cada rodada prevista só com rodadas anteriores; o modelo de jogos usado no contexto foi ajustado só até a temporada anterior. Avaliado em atletas que entraram em campo. Baseline: a média do próprio Cartola.

| Métrica | Modelo | Média do Cartola |
|---|---|---|
| Erro absoluto médio (pontos) | 2,838 | 2,946 |
| Correlação de ordem na posição (Spearman) | 0,237 | 0,193 |
| Rodadas em que o modelo erra menos | 24 de 29 | — |

| Posição | Erro do modelo | Erro da média | Atletas-rodada |
|---|---|---|---|
| ata | 3,143 | 3,190 | 2373 |
| gol | 3,255 | 3,428 | 537 |
| lat | 3,196 | 3,380 | 1358 |
| mei | 2,566 | 2,654 | 2935 |
| tec | 1,756 | 1,875 | 539 |
| zag | 2,797 | 2,949 | 1291 |

## Ao vivo (previsões gravadas antes do fechamento do mercado)

Ainda não há rodada registrada e encerrada.

Ganho real, mas modesto: a pontuação do Cartola tem muito acaso e o modelo não sabe a escalação.

# Cartola FC: backtest da pontuação esperada (estudo de caso)

Walk-forward dentro da temporada: cada rodada prevista só com rodadas anteriores; o modelo de jogos usado no contexto foi ajustado só até a temporada anterior. Avaliado em atletas que entraram em campo (a chance de jogar não é avaliada: não há histórico do status do mercado). Baseline: a média do próprio Cartola.

| Métrica | Modelo | Média do Cartola |
|---|---|---|
| Erro absoluto médio (pontos) | 2,837 | 2,946 |
| Correlação de ordem na posição (Spearman) | 0,230 | 0,193 |
| Rodadas em que o modelo erra menos | 24 de 29 | — |

| Posição | Erro do modelo | Erro da média | Atletas-rodada |
|---|---|---|---|
| ata | 3,143 | 3,190 | 2373 |
| gol | 3,256 | 3,428 | 537 |
| lat | 3,193 | 3,380 | 1358 |
| mei | 2,565 | 2,654 | 2935 |
| tec | 1,755 | 1,875 | 539 |
| zag | 2,796 | 2,949 | 1291 |

Ganho real, mas modesto: a pontuação do Cartola tem muito acaso e o modelo não sabe a escalação.

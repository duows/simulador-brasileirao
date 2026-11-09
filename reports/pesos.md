# Pesos do modelo

- Versão do modelo: `futdados-0.1.0+21d22b71`
- Ajustado em: 2026-11-09T01:50:24Z
- Temporadas de treino: 2011–2026 (6038 jogos)
- Meia-vida da força de longo prazo: 180 dias
- Intercepto: -0,231 (gols esperados base = média da liga × 0,794)
- Ajuste de placares baixos (Dixon-Coles, rho): 0,0000

Fórmula: `log(gols esperados) = log(média da liga) + intercepto + Σ peso × fator`.
O intervalo é de 95%, por bootstrap de jogos. Quando ele cruza o zero, os dados
não permitem afirmar que o fator tem efeito.

| Fator | Peso | Intervalo 95% | O que significa |
|---|---|---|---|
| Força de ataque (longo prazo) | 0,709 | [0,610; 0,808] | Um ataque 20% melhor que a média da liga muda os gols esperados em +13,8%. |
| Fragilidade da defesa adversária (longo prazo) | 0,648 | [0,545; 0,771] | Um adversário que sofre 20% mais gols que a média muda os gols esperados em +12,5%. |
| Mando de campo | 0,396 | [0,366; 0,426] | Jogar em casa muda os gols esperados em +48,6%. |
| Forma recente (últimos 5) | 0,023 | [0,004; 0,042] | Ter 1 ponto por jogo a mais que o adversário nos últimos 5 jogos muda os gols esperados em +2,3%. |
| Descanso | -0,002 | [-0,013; 0,008] | Ter 3 dias a mais de descanso que o adversário muda os gols esperados em -0,5%. Efeito não distinguível de zero. |
| Jogo no meio da semana | 0,047 | [0,011; 0,089] | Jogo de terça a quinta (vale para os dois times) muda os gols esperados em +4,8%. |
| Troca recente de técnico | 0,000 | [0,000; 0,000] | Sem dados no histórico (fator sempre 0): peso não estimável, fixado em 0. |

## Como ler

- **Ataque e defesa** são taxas de gols com decaimento: um jogo de 180 dias atrás vale metade de um jogo de hoje. Os gols são ajustados pela força do adversário. Cada time é puxado para a média com 5 jogos fictícios (regressão à média); promovidos são puxados para o desempenho médio histórico de promovidos no primeiro ano, estimado só com temporadas anteriores.
- Pesos de ataque e defesa menores que 1 significam que a diferença observada entre os times é em parte ruído: o modelo puxa as forças em direção à média.
- **Forma** é medida além da força de longo prazo. Peso pequeno quer dizer que a sequência recente acrescenta pouco ao que o histórico com decaimento já captura.
- **Descanso** só conta jogos da Série A (copas não estão nos dados). Ver limitações no README.
- **Técnico novo**: a fonte histórica (footballcsv) não traz técnicos, então o fator vale 0 em todo o histórico e o peso não é estimável (fica 0). Só passa a contar quando houver trocas registradas (API ou config/coach_changes.csv) **e** um histórico com técnicos para estimar o peso.

## Escolha da meia-vida (walk-forward nas temporadas de ajuste)

| Meia-vida (dias) | Brier | Log loss | Jogos |
|---|---|---|---|
| 60 | 0,6223 | 1,0351 | 1140 |
| 90 | 0,6213 | 1,0336 | 1140 |
| 180 | 0,6202 | 1,0322 | 1140 |
| 365 | 0,6204 | 1,0326 | 1140 |
| 730 | 0,6211 | 1,0338 | 1140 |
| 1460 | 0,6217 | 1,0346 | 1140 |

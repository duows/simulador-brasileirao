# Registro de decisões

Cada decisão tem data, contexto e o que foi escolhido. Decisões menores tomadas
sem consulta seguem a regra "o padrão mais simples, registrado aqui".

## D01 · 2026-11-08 · Versão do Python
O pedido era Python 3.12, mas a máquina só tem 3.14 (`py --list`). Instalar outra
versão mexe no sistema, então o ambiente `.venv` usa 3.14 e o código mira 3.12+
(`requires-python = ">=3.12"`), sem recursos exclusivos do 3.13/3.14.

## D02 · 2026-11-08 · football-data.org (termos e plano)
- Plano **Free**: €0/mês, "Free Forever", **10 requisições/minuto**, 12 competições.
  A página de cobertura lista "Serie A (Brazil)" entre as gratuitas (código BSA na API).
- No plano grátis: jogos (fixtures), classificação, placares e calendário **com atraso**.
  Sem escalações, artilheiros, cartões nem elenco detalhado.
- Histórico de temporadas passadas não é garantido no plano grátis ("10 seasons of
  history" aparece só no pacote pago). Por isso o histórico vem do dataset do item D03
  e a API é usada só para a temporada corrente.
- Não encontrei uma página de termos de uso pública (football-data.org/terms dá 404;
  as páginas de preço e cobertura não trazem termos). **TODO:** escrever para
  daniel@football-data.org confirmando o uso dos dados em vídeos monetizados do
  YouTube, e citar "dados: football-data.org" nos vídeos até lá.
- Fontes: https://www.football-data.org/pricing e https://www.football-data.org/coverage
  (consultadas em 2026-11-08).
- O token fica só na variável de ambiente `FOOTBALL_DATA_TOKEN`.
- Cada atualização faz 3 requisições (jogos, classificação, times). O limitador do
  cliente garante no máximo 10 por minuto em qualquer janela de 60 s.

## D03 · 2026-11-08 · Dataset histórico (adaoduque/Brasileirao_Dataset) · SUBSTITUÍDA por D14
- **Licença: o repositório não tem arquivo LICENSE e a API do GitHub devolve
  `license: null`.** Sem licença explícita, o padrão legal é "todos os direitos
  reservados" para a compilação. Decisão: (1) não versionamos cópia do dataset
  (`data/external/` está no .gitignore, o CLI clona na hora); (2) usamos só os
  resultados das partidas, que são fatos públicos; (3) citamos a fonte nos vídeos e no
  README. **TODO:** pedir autorização ao autor (adaoduquesn@gmail.com, contato do README).
- Colunas reais conferidas (commit `15f027c`, fev/2026): `ID, rodata, data, hora,
  mandante, visitante, formacao_*, tecnico_*, vencedor, arena, mandante_Placar,
  visitante_Placar, mandante_Estado, visitante_Estado`. "rodata" é a rodada (erro de
  digitação na origem). O README diz 2003-2024; o CSV vai até 2024 e existe também
  `data/brasileirao-2025.json` com as 380 partidas de 2025, que também ingerimos.
- O CSV **não tem coluna de temporada** e a temporada 2020 terminou em fev/2021: a
  temporada é deduzida pela ordem do ID (quebra quando a rodada cai de ~38 para 1).
  Resultado: 22 temporadas de 2003 a 2024 (552, 552, 462, depois 380 por ano; 2016 tem
  379 porque Chapecoense x Atlético-MG não foi disputado).
- Técnicos só existem a partir de 2014.
- Horário convertido de Brasília para UTC com +3 h (horário de verão ignorado; só
  afeta o horário, não o dia).

## D04 · 2026-11-08 · Chave dos jogos
A chave primária é (temporada, mandante, visitante): em pontos corridos cada mando
acontece uma única vez por temporada. Isso torna o upsert idempotente entre fontes.

## D05 · 2026-11-08 · Normalização de nomes
`config/teams.csv` guarda id canônico, nome de exibição e apelidos. A comparação é
feita sem acento, sem pontuação e sem espaços extras. Nome desconhecido gera erro
(nunca adivinhamos). Os nomes da API foram escritos a partir da convenção do
football-data.org ("São Paulo FC", "SE Palmeiras"…) e são conferidos na primeira
ingestão: qualquer nome sem alias para o processo com mensagem clara.

## D06 · 2026-11-08 · Critério de desempate
Ordem usada (imprensa sobre o Regulamento Específico da Série A 2026, Art. 15):
pontos, vitórias, saldo, gols pró, confronto direto (só entre exatamente dois clubes
empatados), cartões vermelhos, cartões amarelos, sorteio. **TODO: confirmar no PDF
oficial da CBF.** Houve polêmica pública sobre a leitura do § 2º do Art. 15. Cartões
não estão no plano grátis da API, então na simulação esses critérios caem no sorteio.
Configurável em `simulation.tiebreakers`.

## D07 · 2026-11-08 · Forma do modelo
Regressão de Poisson para os gols de cada time em cada jogo (duas linhas por jogo),
com `log(média da liga)` como offset. Sete fatores, exatamente os pedidos (força de
ataque, fragilidade da defesa adversária, mando, forma, descanso, meio de semana,
técnico novo). Força de longo prazo virou **dois** fatores (ataque próprio e defesa do
adversário) porque gols marcados e sofridos são informações diferentes; continuam sendo
"o fator a". Descanso e calendário viraram dois fatores (diferença de dias de descanso e
jogo de terça a quinta). Forma, descanso e técnico novo entram como **diferença** entre
os times para usar um único peso por fator. Nenhum fator extra foi adicionado.

## D08 · 2026-11-08 · Força de longo prazo (prior dos promovidos atualizado em D15)
- Taxa de gols com decaimento exponencial no calendário (meia-vida configurável).
- Gols ajustados pela força do adversário no momento do jogo (`opponent_adjust`),
  senão quem enfrentou tabela mais difícil seria subestimado.
- Puxão para a média com 5 jogos fictícios. Time sem histórico recente começa com
  ataque 0,85 e defesa 1,15 vezes a média: times recém-promovidos costumam ser mais
  fracos e a média da liga seria um ponto de partida otimista. Os valores 0,85/1,15 são
  um padrão simples, não estimado. **TODO:** estimar a partir dos promovidos 2006-2025.
- Meia-vida escolhida no walk-forward 2010-2014 (antes das temporadas de teste): 365
  dias. A curva é plana entre 180 e 730 dias.
- Treino a partir de 2006: 2003-2005 (24 e 22 clubes) só aquecem as forças.

## D09 · 2026-11-08 · Regularização, incerteza e Dixon-Coles
- Ridge na escala padronizada (`ridge_alpha` = 1). Com 7 pesos e ~15 mil linhas a
  penalidade quase não muda nada; fica como proteção se fatores forem adicionados.
- Intervalo de incerteza: bootstrap de 200 reamostragens de **jogos** (as duas linhas
  de um jogo juntas), percentis 2,5 e 97,5.
- O ajuste de Dixon-Coles (um parâmetro na matriz de placares, não é fator) foi
  implementado, mas o rho estimado foi -0,01, efeito desprezível. Desligado por
  simplicidade (`dixon_coles: false`). Pode ser religado no YAML.

## D10 · 2026-11-08 · Decomposição dos fatores
A contribuição de cada fator em gols usa a média logarítmica (LMDI): soma exatamente
`gols esperados - gols base`. O JSON traz também o multiplicador `exp(peso × fator)`,
mais fácil de narrar ("o mando multiplica por 1,5").

## D11 · 2026-11-08 · Técnico novo (ver D14: sem dados no histórico novo)
Técnico é "novo" nos primeiros 5 jogos dele no clube. No histórico, troca = nome do
técnico diferente do jogo anterior (só existe a partir de 2014; antes o fator vale 0, o
que atenua um pouco o peso estimado). Na temporada corrente o plano grátis da API não
traz técnico por jogo: o comando de ingestão guarda o técnico de cada time e marca a
troca quando ele muda; `config/coach_changes.csv` permite registrar a troca à mão com
fonte. Interinos e grafias diferentes do mesmo nome contam como troca (limitação).

## D12 · 2026-11-08 · Simulação da tabela
- Cada jogo restante é sorteado da matriz de placares (10 mil simulações por padrão).
- "Tabela depois da rodada X": jogos já disputados (inclusive adiantados) + jogos
  simulados com rodada ≤ X. Ordenada pelos pontos esperados, com faixa de posição
  p10-p90. Chances de título, G4, G6 e rebaixamento são sempre do fim do campeonato.
- Forma e técnico novo só valem para a próxima rodada; nas seguintes ficam neutros
  (não sabemos a forma futura). Descanso e meio de semana usam o calendário marcado.
- As forças não são atualizadas dentro da simulação (simplificação; tende a deixar a
  distribuição um pouco estreita demais no longo prazo).
- Zonas configuráveis. G4 = 1º-4º, G6 = 1º-6º, rebaixamento = 17º-20º.
- `--as-of-round` reconstitui uma projeção histórica escondendo os resultados
  seguintes. Os pesos usados são os atuais (podem ter sido ajustados com dados daquela
  temporada), então serve para demonstração, não para avaliação.

## D13 · 2026-11-08 · Dataset financeiro
- Formato longo (uma linha por clube, ano, campo e fonte), em R$ mil, com o sinal do balanço.
  Colunas: definição usada, tipo de fonte, URL, página do PDF, data de consulta, status.
- "Página do PDF" é o índice da página no arquivo (o rodapé impresso pode ser outro número).
- Status: `confirmado`, `conflito` (duas ou mais linhas para o mesmo campo), `nao_confirmado`
  (imprensa ou pista sem conferência no PDF), `lacuna`, `nao_aplicavel`. O validador em
  `futdados.finance` impede número sem fonte e conflito com uma fonte só.
- As pistas do pedido entram como `pista_usuario` e nunca como confirmadas.
- Quando o clube reapresenta um ano, os dois valores ficam registrados como conflito.
- Os PDFs baixados não são versionados (`data/finance/pdfs/` no .gitignore); a URL está em
  cada linha.
- Flamengo e Corinthians: PDF anual auditado não localizado nesta rodada; números da imprensa
  marcados como `nao_confirmado`.
- Campos extras além dos pedidos (`receita_estadio`, `obrigacoes_totais`, `passivo_total`,
  `patrimonio_liquido`) existem para explicar diferenças de definição de dívida e o Morumbis.

## D14 · 2026-11-08 · Troca da fonte histórica para footballcsv (CC0)
Pedido: usar github.com/footballcsv/world (CC0), de 2010 em diante, e remover o dataset do
Adão Duque.
- **O que existe no footballcsv/world** (commit `0783bd4`, jul/2024): Série A só em
  `2010s/2019/br.1.csv` (380 jogos) e `2020s/2020/br.1.csv` (380 linhas, 177 sem placar).
  Não dá para cobrir 2010+ com ele.
- **Decisão:** usar `footballcsv/cache.wfb` (mesma organização, mesma licença CC0 1.0,
  commit `399cc1f`, set/2024), que tem `br.1.csv` de 2003 a 2024 com rodada, data, horário
  em UTC e placar, sem odds. Usamos 2010-2024. Conferido: em 2019 a distribuição de placares
  é idêntica à do `world`.
- **Cobertura real:** 2010-2023 completos (2016 com 379 jogos, Chapecoense x Atlético-MG
  cancelado); **2024 só até setembro (252 de 380)**; **2025 não existe** em nenhum repositório
  da organização (o `cache.api.fbdat`, cache da API football-data.org, também para em set/2024).
  O restante vem da API (`ingest-api --season 2024/2025`), que sobrescreve pela mesma chave.
  **TODO:** verificar se o plano grátis libera temporadas passadas.
- **Ressalva de procedência:** o `cache.wfb` é um cache de dados do worldfootball.net. A
  organização footballcsv declara CC0, mas resultados de partidas são fatos; o risco legal é
  baixo, e citamos a fonte nos JSONs e no README.
- **Perdas com a troca:** não há técnico por jogo, então o fator "técnico novo" fica com peso
  0 (não estimável). Também saem as temporadas 2003-2009 e 2025.
- O dataset do Adão Duque foi removido do código, da configuração, dos testes e do disco. O
  banco foi recriado (o registro de previsões estava vazio; só projeções de demonstração foram
  descartadas).
- Novos parâmetros: treino a partir de 2011 (2010 aquece as forças), meia-vida escolhida em
  2012-2014 (180 dias), teste 2015-2024.

## D15 · 2026-11-08 · Atribuição do football-data.org
Os Termos e Condições do football-data.org (versão de 1º/jun/2018, exibidos em
https://www.football-data.org/client/register; o endereço api.football-data.org/register
não abre fora do navegador), cláusula 7.1, exigem a frase "Football data provided by the
Football-Data.org API" em local visível. Ela vai no campo `atribuicao` de todo JSON de saída
e no README. A mesma página diz que credenciais não podem ficar em repositório de código
aberto: o token continua só na variável de ambiente.

## D16 · 2026-11-08 · Pré-temporada (`simulate-season`)
- Nenhum jogo da temporada conta como disputado; se a temporada já tem resultados no banco,
  eles são escondidos e as temporadas seguintes são ignoradas.
- Calendário: o da API, se já estiver no banco. Se não estiver, uma tabela balanceada gerada
  pelo método do círculo (turno e returno espelhado, 19 jogos em casa por time, 9 ou 10 em
  casa no turno, no máximo 2 jogos seguidos com o mesmo mando), uma rodada por semana aos
  sábados a partir de `preseason.start_date`. Os times vêm de `--teams`.
- Força inicial com regressão à média: decaimento no tempo (a pausa entre temporadas já
  reduz o peso do passado), 5 jogos fictícios na média da liga e pesos de ataque e defesa
  menores que 1 no modelo.
- **Prior dos promovidos (substitui o 0,85/1,15 fixo do D08):** promovido é o time que não
  estava na temporada anterior. O prior é a média, entre os promovidos de todas as
  temporadas anteriores, de gols marcados e sofridos por jogo divididos pela média da liga
  naquela temporada. É recalculado no início de cada temporada só com temporadas
  encerradas (sem vazamento). Valor para 2025: ataque 0,88 e defesa 1,11. Times que estavam
  na temporada anterior são puxados para 1,0.
- Saída `out/videos/pre-temporada-<S>.json` com força inicial, pontos esperados, faixa p10-p90
  e chances de título, G4, G6 e rebaixamento, `aviso`, `atribuicao` e alertas (calendário
  gerado; histórico com mais de 200 dias sem jogos).
- Demonstração com 2023 (calendário real, resultados escondidos): os pesos atuais foram
  ajustados com dados até 2024, então a demonstração não é uma avaliação limpa.

## D17 · 2026-11-09 · Rodada-alvo e jogos adiados no `predict-round`
Problema: o `predict-round` escolhia a menor rodada com jogo pendente. Com o jogo adiado
Chapecoense x Vasco (rodada 21, remarcado para 14/11), ele gravou só essa previsão e ignorou a
rodada 35.
- **Próxima rodada** = a primeira rodada em que nenhum jogo foi disputado.
- **Adiado** = jogo pendente de rodada anterior à próxima rodada, ou com status
  POSTPONED/SUSPENDED. Recebe previsão própria, com `"adiado": true` no payload do registro e
  numa seção `adiados` do JSON. O registro guarda a rodada original do jogo.
- `--round N` estima os jogos pendentes da rodada N (inclusive o adiado dela).
- **Sem duplicar**: jogo que já tem previsão gravada antes do início não é gravado de novo; o
  JSON cita a previsão existente (hora, hash, versão do modelo). `--repetir` grava uma nova sem
  apagar a antiga. O registro imutável existente (1 linha, de 2026-11-09) não foi tocado.
- Na projeção, forma e técnico novo valem para a próxima rodada **e** para os adiados (jogos
  próximos); antes, o adiado fazia a forma valer só para ele.

## D18 · 2026-11-09 · Site estático (Next.js)
- Next 16.4.2 com React 19.3.1 (versões publicadas há mais de duas semanas), `output: "export"`:
  o build gera HTML puro em `site/out/`, sem servidor e sem chamadas à API por visitante.
- `futdados export-site --season S` grava em `site/public/data` seis JSONs derivados: meta,
  tabela, rodada (com adiados), simulador, modelo (pesos + `data/model/backtest.json`) e
  finanças (o dataset curado, com fonte por número). Todos têm `aviso`, `atribuicao` e
  `gerado_em`. Jogos disputados entram só agregados (tabela atual e confronto direto), nunca
  como lista de partidas: nada de dados brutos de terceiros. Os JSONs são versionados para o
  site compilar a partir de um clone.
- O simulador “e se” roda no navegador (`site/lib/simulate.mjs`) com o mesmo algoritmo do
  Python: matriz de Poisson, sorteio do placar e desempate com confronto direto só entre dois.
  Jogo com resultado escolhido é sorteado só entre placares compatíveis, para o saldo continuar
  realista. Um teste confere que, sem escolhas, os pontos esperados batem com o Python (±0,6).
- Tema escuro único. Cores das séries: slots 1-3 da paleta de referência da skill de
  visualização (mandante, empate, visitante), sempre com rótulo de texto ao lado.
- Backtest agora cobre 2015-2026 (2026 só com jogos já disputados), com 2024 e 2025 completos
  vindos da API.

## D19 · 2026-11-09 · Histórico de projeções por rodada (gráfico de evolução)
- Não havia histórico salvo antes da rodada 34 de 2026. **Não reconstruímos o passado**: os
  pesos atuais já viram os resultados seguintes, e uma projeção "da rodada 20" feita hoje
  pareceria melhor do que o modelo teria sido. O gráfico começa na rodada 34.
- Cada `export-site` (e `project`, `predict-round`) ao vivo grava a projeção na tabela
  imutável `projections`. O histórico usa, para cada rodada-base, a última projeção gravada.
- Reconstituições com `--as-of-round` não são mais gravadas (antes o `project` gravava).
- A simulação passou a devolver a distribuição completa da posição final (heatmap 20×20).

## D20 · 2026-11-09 · Fase A do prompt mestre: cobertura 2006-2026 e qualidade
- **2006-2009 vêm do `footballcsv/cache.wfb`** (CC0, mesma ressalva de procedência do D14), que
  tem as quatro temporadas completas. Assim a base 2006-2025 fica completa (380 jogos por
  temporada; 2016 com 379) sem usar dado sem licença. O prompt previa o adaoduque para 2006-2009;
  preferimos a fonte com licença declarada.
- **adaoduque/Brasileirao_Dataset**: só validação local, com `LOCAL_ONLY_SOURCES=1`, clonado em
  `data/external` (gitignored), nunca gravado no banco nem exportado. Resultado da validação de
  2026-11-09: 7.219 jogos em comum (2006-2024), **zero divergências de placar**, 29 de data
  (2007-2010). O relatório `reports/divergencias.md` registra essas 29 datas.
- **Prioridade de fontes:** football-data.org > footballcsv > adaoduque. O ingest histórico não
  sobrescreve jogo que veio da API. API x footballcsv em 2024: 252 jogos em comum, 0 divergências.
- **config/seasons.yaml**: regras por temporada (clubes, jogos esperados, desempate, zonas,
  períodos de portões fechados e notas). Vagas continentais mudaram muito e ficam como TODO; as
  zonas G4/G6/rebaixamento são configuráveis por temporada.
- **Flags no banco** (migração 1): postponed, rescheduled, neutral_venue (sem fonte, 0),
  behind_closed_doors (2020 inteiro e 2021 até outubro, TODO por jogo).
- **config/teams.csv** ganhou slug, sigla de 3 letras e cores (aproximadas, só para o monograma).
- **CI local**: `make check` ou `python scripts/check.py` (ruff, pytest, qualidade dos dados com
  `coverage --strict`, testes e build do site, varredura de token, escudo, odds e vocabulário).
  Não há `make` nesta máquina Windows; o script roda direto.
- Os pesos atuais foram ajustados antes de 2006-2009 entrarem no banco; a reestimação fica para
  a Fase D (modelos), junto com o backtest novo.

## D21 · 2026-11-09 · Fase B: catálogo de métricas
- `futdados metrics` recalcula três tabelas derivadas (regraváveis; as imutáveis nunca são
  tocadas): `team_round_stats` (tabela acumulada depois de cada rodada, posição, distância para
  líder/G4/G6/Z4, médias móveis de 5 e 10 jogos), `team_season_stats` (resultados, casa/fora,
  ataque e defesa por jogo, clean sheets, ambos marcam, 3+ gols, placar mais comum, maiores e
  atuais sequências, força relativa à média, Pitagórico) e `league_season_stats` (pontos do
  campeão, vice, G4, G6, 16º, 17º e último, gols por jogo, empates, mando, desvio e Gini dos
  pontos, times na briga pelo título 5 rodadas antes do fim).
- Posição nas métricas históricas: pontos, vitórias, saldo, gols pró; o resto do desempate
  (confronto direto, cartões) fica de fora e empates totais caem em ordem alfabética.
- **Pitagórico**: pontos/jogo = a + b · GP^k/(GP^k + GC^k), com k, a e b estimados por mínimos
  quadrados em todos os time-temporadas 2006-2026 (k = 1,38). "Pontos menos Pitagóricos" é o
  indicador de sorte/azar (positivo = mais pontos do que o saldo sugere).
- Gols por tempo não existem nas fontes: a métrica fica fora.

## D22 · 2026-11-09 · Fase C: Elo e tendências
- **Elo** (`futdados build-ratings`): multiplicador por saldo de gols (1; 1,5; (11+saldo)/8),
  regressão parcial à média entre temporadas e entrada de promovidos com deslocamento. K,
  regressão e promovido calibrados por **RPS** nas temporadas 2008-2014 (2006-2007 aquecem):
  K = 10, regressão = 0,30, promovido = -25. A superfície é plana (RPS 0,2067 a 0,2089 em
  toda a grade).
- **Mando do Elo estimado dos dados** (≈ 97 pontos): calibrado por RPS ele crescia sem limite
  (até 300) com ganho de 0,00007, porque a regressão ordinal que transforma diferença de
  rating em V/E/D já absorve o efeito médio do mando. Fixamos o valor que faz a pontuação
  esperada do mandante (ratings iguais) igual à média histórica.
- V/E/D a partir do Elo: regressão logística ordinal (1 coeficiente, 2 cortes).
- **Tendências** (`futdados trends`): Theil-Sen com IC 90%, Mann-Kendall, LOESS com faixa por
  bootstrap de resíduos, média móvel de 3 anos, um ponto de mudança na média (penalidade tipo
  BIC) e comparação de eras (Kruskal-Wallis). Rótulo só com p < 0,05. Resultado em
  `reports/tendencias.md`: liga mais desigual (Gini e desvio dos pontos em alta), menos gols
  por jogo e vantagem de mando em queda; pontos do campeão sem tendência clara.

## D23 · 2026-11-09 · Fase D: placar entre modelos (walk-forward 2015-2026)
- `futdados backtest` compara 10 modelos fora da amostra (detalhes em reports/backtest.md):
  baselines (frequência, sempre mandante, Elo puro), Poisson de 7 fatores, Poisson + Dixon-Coles,
  forças por time (MAP com prior gaussiano e decaimento, reajustado a cada rodada), logística
  ordinal com fatores, gradient boosting, conjunto e conjunto calibrado. RPS como métrica
  principal, IC 90% por bootstrap de temporadas inteiras.
- **Resultado**: conjunto 0,2069, forças por time 0,2071, Elo puro 0,2071, Poisson 0,2084,
  frequência 0,2184. O Poisson de produção **perde do Elo puro em todas as 12 temporadas**
  (diferença +0,0013, IC +0,0009 a +0,0017). O conjunto ganha do Elo em 8 de 12, mas o IC cruza
  o zero (-0,0006 a +0,0001).
- Desligados por não melhorarem: Dixon-Coles, boosting, temperatura. Sem sobredispersão (razão
  de Pearson 0,95): Binomial Negativa não entra. Bayesiano completo (PyMC) não instalado; o
  modelo de forças por time é a versão MAP (prior gaussiano = ridge).
- **Ablação do Poisson**: mando, ataque e defesa ajudam; forma, descanso e meio de semana são
  neutros (IC cruza o zero); técnico novo sem dados.
- Treino do Poisson agora começa em 2007 (2006 aquece as forças).
- **TODO (próximo passo de maior valor)**: trocar o modelo de produção (rodada, simulação, JSON)
  pelo conjunto Elo + forças por time, mantendo a explicação por fatores (ataque, defesa e
  mando do modelo de forças, mais a nota Elo) e mostrando "o Elo diz X, as forças dizem Y".

## D24 · 2026-11-09 · Cartola FC (estudo de caso pessoal)
- **Fonte**: API pública e não oficial do Cartola (api.cartola.globo.com; o host antigo
  api.cartolafc.globo.com redireciona). Não encontrei licença nem termos de uso específicos
  para ela. **Decisão**: uso pessoal e local. Respostas brutas em `data/cartola/` e o JSON da
  página em `site/public/data/cartola.json` ficam no .gitignore; nada do Cartola é versionado
  nem publicado. Só o relatório agregado (`reports/cartola.md`, sem dados de atletas) entra no
  git. Chamadas com pausa de 1 s; rodadas passadas ficam em cache. **TODO**: ler os termos de
  uso da Globo antes de qualquer publicação.
- **Modelo** (`src/futdados/cartola/model.py`): regressão linear por posição da pontuação do
  atleta em: média do atleta nas rodadas anteriores puxada para a média da posição (5 jogos
  fictícios), chance de não sofrer gol, gols esperados do time, mando e chance de vitória (as
  três últimas do modelo de jogos do futdados). Cada pontuação esperada se decompõe por fator.
- **Validação**: walk-forward dentro de 2026 (rodadas 6 a 34), cada rodada prevista só com as
  anteriores e com o modelo de jogos ajustado até 2025. Erro médio 2,84 pontos contra 2,95 da
  média do Cartola; Spearman 0,23 contra 0,19; melhor em 24 de 29 rodadas. Só atletas que
  entraram em campo: a chance de jogar não é avaliada.
- **Chance de jogar**: pelo status do mercado (provável 95%, dúvida 50%), fixo e não estimado
  (não há histórico de status). Jogos marcados como não válidos na rodada do Cartola não
  pontuam e ficam de fora.
- **Montagem do time**: programação linear inteira exata (scipy.milp) no Python e programação
  dinâmica exata no navegador (preços arredondados para cima em décimos, então o time sempre
  cabe no orçamento). Os dois batem com força bruta nos testes. Capitão ×1,5 (TODO: confirmar a
  regra vigente).
- Vocabulário do canal mantido: "pontuação esperada pelo modelo", nada de dica.

## D25 · 2026-11-09 · Cartola: histórico por temporada, registro, ao vivo e banco de reservas
- **Cache por temporada** (`data/cartola/<ano>/`): a API só mostra a temporada atual; o
  passado só existe no cache. O mercado de cada rodada também é guardado
  (`atletas_mercado_r{N}.json`), criando histórico de preço e de status. **Faça backup dessa
  pasta**: ela está fora do git.
- **Várias temporadas no treino**: os coeficientes usam todas as temporadas do cache; no início
  de uma temporada, a média de cada atleta parte da média dele na temporada anterior (5+ jogos).
- **Registro imutável** (`cartola_predictions`): a cada `futdados cartola` com o mercado aberto,
  grava a pontuação esperada de cada atleta e os times sugeridos para C$ 100/120/140/160, antes do
  fechamento (o banco recusa depois), sem alterar nem apagar.
- **Ao vivo**: o mesmo comando compara, para cada rodada registrada e já encerrada, o previsto com
  o real (erro do modelo x média do Cartola, % de prováveis que jogaram, pontos reais dos times
  sugeridos com a regra do banco) em `reports/cartola.md` e na página /cartola.
- **Banco de reservas**: um por posição (sem técnico), escolhido depois dos titulares. Regra
  configurável: não gasta cartoletas e custa no máximo o titular mais barato da posição (**TODO:
  confirmar a regra vigente**). Vale chance de algum titular faltar × esperado do reserva. Reserva
  de luxo: não implementada.

## D26 · 2026-11-09 · Motor de produção trocado para o conjunto forças + Elo
- Pelo placar do D23, o Poisson de 7 fatores perdia do Elo puro em todas as temporadas. Agora
  (`config: production.enabled`): **gols esperados** = modelo de forças por time (ataque e defesa
  com prior gaussiano, mando comum, média da liga, decaimento de 365 dias, últimas 3 temporadas),
  usados na simulação, no simulador, nas páginas e no contexto do Cartola. **Probabilidade
  mostrada e registrada** = conjunto forças + Elo com os pesos do backtest (59% / 41%).
- Fatores explicáveis por jogo: média de gols da liga, mando, ataque do time e defesa do
  adversário (decomposição exata na escala log). O card mostra também o que cada modelo diz.
- No Cartola, o contexto de cada rodada passada é recalculado com as forças daquele momento
  (sem vazamento). O erro ficou igual (2,84): o ganho do motor novo está nos jogos e na simulação.
- O Poisson de 7 fatores continua no código (backtest e `production.enabled: false`).

## D27 · 2026-11-09 · Simulação: incerteza, pontos necessários, jogos decisivos e backtest
- **20 mil simulações** por padrão (1,7 s para o restante de 2026).
- **Incerteza dos parâmetros**: em cada simulação, ataque e defesa de cada time são sorteados em
  torno da estimativa com o erro-padrão de Laplace (diagonal da informação de Fisher + prior;
  0,09 a 0,25 em 2026). A aproximação da hessiana do L-BFGS foi descartada (dava ~1 para todos).
- **Pontos necessários**: menor pontuação final que, nas simulações, garantiu cada objetivo em
  90% dos casos (2026: título 84, G4 62, G6 57, permanência 40).
- **Jogos decisivos**: para cada jogo restante, a diferença na chance de título, G4 ou
  rebaixamento do time mais afetado entre vitória do mandante e do visitante.
- **Backtest da simulação** (`futdados backtest-sim`, 2015-2025, cortes nas rodadas 10/20/30):
  Brier de título, G4 e rebaixamento sempre abaixo do baseline (mesma chance para todos); a
  posição final caiu na faixa p10–p90 em 89% dos casos (ideal ~80%: a faixa é conservadora).

## D28 · 2026-11-09 · Escudos e fotos só no modo local; rotina de um clique
- `CRESTS=local` (ligado por `npm run dev:local` e pelo atalho) mostra escudos dos clubes e fotos
  dos atletas pelos endereços que já vêm nos dados locais do Cartola. Nada é baixado nem
  versionado; sem a variável o site usa o monograma. Escudo é marca do clube e foto tem direito
  de imagem: **um build feito com CRESTS=local não deve ser publicado**.
- `futdados atualizar` roda a rotina inteira em ordem (API se houver token, pesos com meia-vida
  fixa de 180 dias, qualidade, métricas, Elo, tendências, registro da rodada, Cartola, site) e
  segue em frente se uma etapa opcional falhar. `ATUALIZAR_E_ABRIR.bat` chama essa rotina e
  abre o site.

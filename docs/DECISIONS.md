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

## D03 · 2026-11-08 · Dataset histórico (adaoduque/Brasileirao_Dataset)
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

## D08 · 2026-11-08 · Força de longo prazo
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

## D11 · 2026-11-08 · Técnico novo
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

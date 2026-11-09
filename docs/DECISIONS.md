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

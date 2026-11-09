@echo off
REM Atualiza tudo (jogos, modelo, previsoes, Cartola, site) e abre o site no navegador.
REM Duplo clique neste arquivo. Para atualizar os jogos, defina antes a variavel de ambiente
REM FOOTBALL_DATA_TOKEN com a sua chave do football-data.org.
chcp 65001 > nul
cd /d "%~dp0"
if not exist ".venv\Scripts\futdados.exe" (
  echo Ambiente Python nao encontrado em .venv. Veja o README, secao Instalacao.
  pause
  exit /b 1
)
.venv\Scripts\futdados atualizar
echo.
echo Abrindo o site em http://localhost:3001 (feche esta janela para desligar o site).
start "" http://localhost:3001
cd site
if not exist "node_modules" call npm install
npm run dev:local

@echo off
REM So abre o site (sem atualizar nada). A atualizacao roda sozinha pela tarefa agendada
REM (scripts\agendar_atualizacao.bat) ou pelo ATUALIZAR_E_ABRIR.bat.
chcp 65001 > nul
cd /d "%~dp0site"
if not exist "node_modules" call npm install
start "" http://localhost:3001
npm run dev:local

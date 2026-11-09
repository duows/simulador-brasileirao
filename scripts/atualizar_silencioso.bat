@echo off
REM Usado pela tarefa agendada do Windows: atualiza tudo sem abrir o site e guarda o log.
cd /d "%~dp0.."
if not exist "logs" mkdir logs
.venv\Scripts\futdados atualizar > logs\ultima_atualizacao.log 2>&1

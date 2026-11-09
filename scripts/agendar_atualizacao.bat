@echo off
REM Cria (ou recria) a tarefa agendada "futdados-atualizar": roda todo dia as 10:00 e as 17:00.
REM Para remover: schtasks /Delete /TN "futdados-atualizar" /F  e  schtasks /Delete /TN "futdados-atualizar-tarde" /F
set ALVO=%~dp0atualizar_silencioso.bat
schtasks /Create /F /SC DAILY /ST 10:00 /TN "futdados-atualizar" /TR "\"%ALVO%\""
schtasks /Create /F /SC DAILY /ST 17:00 /TN "futdados-atualizar-tarde" /TR "\"%ALVO%\""
echo.
echo Pronto: a atualizacao roda sozinha todo dia as 10:00 e as 17:00 (com o computador ligado).
echo O log fica em logs\ultima_atualizacao.log
pause

@echo off
rem Instala as bibliotecas do Python que o scriptLattes usa (uma vez por PC).
cd /d "%~dp0"
set PY=python
where python >nul 2>&1 || set PY="D:\anaconda3\python.exe"
%PY% -m pip install -r requirements.txt
pause

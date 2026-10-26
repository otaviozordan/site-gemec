@echo off
rem Duplo clique para abrir o app das atualizacoes do site. Detalhes em LEIA-ME.txt.
cd /d "%~dp0"
set PY=pythonw
where pythonw >nul 2>&1 || set PY="D:\anaconda3\pythonw.exe"
start "" %PY% app.py

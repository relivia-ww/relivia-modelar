@echo off
title Relivia Modelar
echo.
echo  Iniciando Relivia Modelar...
echo.

cd /d "C:\projetos\relivia-modelar"

:: Abre worker Celery em janela separada
start "Relivia Worker" cmd /k "cd /d C:\projetos\relivia-modelar && python start_worker.py"

:: Aguarda 2 segundos
timeout /t 2 /nobreak >nul

:: Inicia servidor Flask
start "Relivia Servidor" cmd /k "cd /d C:\projetos\relivia-modelar && python run.py"

:: Aguarda servidor subir
timeout /t 3 /nobreak >nul

:: Abre no navegador
start http://127.0.0.1:5050

echo.
echo  Relivia Modelar rodando em http://127.0.0.1:5050
echo  Feche as janelas do terminal para parar.
echo.

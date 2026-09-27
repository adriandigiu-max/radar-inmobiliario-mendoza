@echo off
title Radar Inmobiliario Mendoza
cd /d "%~dp0"
echo ===================================================
echo     Iniciando Radar Inmobiliario - Mendoza
echo ===================================================
echo Abriendo navegador en http://localhost:8501 ...
start "" http://localhost:8501
".venv\Scripts\python.exe" -m streamlit run app.py
pause

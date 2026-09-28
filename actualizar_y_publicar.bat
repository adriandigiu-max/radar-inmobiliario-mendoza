@echo off
title Radar Inmobiliario - Actualizar y Publicar
cd /d "%~dp0"
echo ===================================================
echo   Radar Inmobiliario Mendoza - Actualizar datos
echo ===================================================
echo.
echo [1/2] Ejecutando scraper y analisis...
".venv\Scripts\python.exe" main.py
if errorlevel 1 (
    echo ERROR al ejecutar el scraper. Revisa la consola.
    pause
    exit /b 1
)
echo.
echo [2/2] Subiendo resultados a GitHub...
"C:\Program Files\Git\cmd\git.exe" add data/
"C:\Program Files\Git\cmd\git.exe" commit -m "data: actualizacion de oportunidades %date% %time%"
"C:\Program Files\Git\cmd\git.exe" push origin main
echo.
echo ===================================================
echo  Listo! Los resultados ya estan en el link publico.
echo ===================================================
echo.
pause

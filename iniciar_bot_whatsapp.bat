@echo off
chcp 65001 >nul
title Radar Inmobiliario Mendoza - Bot WhatsApp & Scheduler
echo ==============================================================================
echo       RADAR INMOBILIARIO MENDOZA - BOT DE WHATSAPP Y BÚSQUEDA DIARIA
echo ==============================================================================
echo.
echo 1. Scheduler Diario Activo:
echo    - Ejecutará la búsqueda todos los días a las 08:00 AM automáticamente.
echo    - Si encuentra alguna propiedad con Score >= 80, la enviará por WhatsApp.
echo.
echo 2. Bot Interactivo de WhatsApp Activo:
echo    - Puerto local: 8000
echo    - Si un usuario envía un número del 1 al 5: responde con los avisos.
echo    - Si envía otro texto: pide un número del 1 al 5.
echo.
echo ==============================================================================
echo.

IF NOT EXIST ".venv\Scripts\python.exe" (
    echo [ERROR] No se encontró el entorno virtual en .venv.
    pause
    exit /b
)

echo Iniciando servidor FastAPI en http://127.0.0.1:8000 ...
.venv\Scripts\python.exe bot_service.py
pause

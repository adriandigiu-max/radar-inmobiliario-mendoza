@echo off
chcp 65001 >nul
title Tunel ngrok - Radar Inmobiliario Mendoza
echo ==============================================================================
echo       TÚNEL NGROK - RADAR INMOBILIARIO MENDOZA
echo ==============================================================================
echo.
echo Conectando tu bot local (puerto 8000) con Meta WhatsApp Cloud...
echo Dominio: https://attic-spinal-conjuror.ngrok-free.dev
echo.
echo Deja esta ventana abierta mientras quieras que el bot reciba WhatsApp.
echo ==============================================================================
echo.
ngrok http --domain=attic-spinal-conjuror.ngrok-free.dev 8000
pause

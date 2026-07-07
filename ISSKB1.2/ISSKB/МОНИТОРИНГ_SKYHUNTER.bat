@echo off
chcp 65001 >nul
title SkyHunter Live Monitor
cd /d "%~dp0security_dashboard"
echo.
echo  Запуск мониторинга SkyHunter...
echo  Подключаю LAN и жди данных. Ctrl+C для выхода.
echo.
python monitor_skyhunter.py
pause

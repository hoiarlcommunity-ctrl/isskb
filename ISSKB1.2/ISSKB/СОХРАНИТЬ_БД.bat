@echo off
chcp 65001 >nul
title ISSKB — Сохранение БД в дампы (dumps\)

echo.
echo  ╔══════════════════════════════════════════════════════╗
echo  ║     ISSKB — Выгрузка баз данных в dumps\*.sql        ║
echo  ╚══════════════════════════════════════════════════════╝
echo.

docker ps >nul 2>&1
if errorlevel 1 (
    echo  [ОШИБКА] Docker не запущен. Запусти Docker Desktop и повтори.
    pause
    exit /b 1
)

if not exist "%~dp0dumps" mkdir "%~dp0dumps"

echo  [1/2] Выгружаю sentinel_isskb...
docker exec sentinel-postgres pg_dump -U sentinel_user -d sentinel_isskb --clean --if-exists > "%~dp0dumps\sentinel_isskb.sql"
if errorlevel 1 ( echo  [ОШИБКА] Не удалось выгрузить sentinel_isskb & pause & exit /b 1 )

echo  [2/2] Выгружаю sentinel_auth...
docker exec sentinel-postgres pg_dump -U sentinel_user -d sentinel_auth --clean --if-exists > "%~dp0dumps\sentinel_auth.sql"
if errorlevel 1 ( echo  [ОШИБКА] Не удалось выгрузить sentinel_auth & pause & exit /b 1 )

echo.
echo  Готово. Дампы лежат в папке dumps\ рядом с этим файлом.
echo  Скопируйте всю папку проекта (включая dumps\) на другой ПК
echo  и запустите там ВОССТАНОВИТЬ_БД.bat
echo.
pause

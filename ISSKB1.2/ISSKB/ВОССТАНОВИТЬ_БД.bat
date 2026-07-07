@echo off
chcp 65001 >nul
title ISSKB — Восстановление БД в Docker

echo.
echo  ╔══════════════════════════════════════════════════════╗
echo  ║     ISSKB — Восстановление баз данных в Docker      ║
echo  ╚══════════════════════════════════════════════════════╝
echo.

REM Проверяем наличие dumps
if not exist "%~dp0dumps\sentinel_isskb.sql" (
    echo  [ОШИБКА] Файл dumps\sentinel_isskb.sql не найден!
    echo  Убедитесь что папка dumps\ рядом с этим bat-файлом.
    pause
    exit /b 1
)

echo  [1/5] Проверка Docker...
docker ps >nul 2>&1
if errorlevel 1 (
    echo  [ОШИБКА] Docker не запущен. Запусти Docker Desktop и повтори.
    pause
    exit /b 1
)
echo        Docker OK

echo  [2/5] Создание/запуск контейнера sentinel-postgres...
docker ps -a --filter "name=sentinel-postgres" --format "{{.Names}}" | findstr "sentinel-postgres" >nul 2>&1
if errorlevel 1 (
    echo        Контейнер не существует — создаём...
    docker run -d ^
        --name sentinel-postgres ^
        -e POSTGRES_USER=sentinel_user ^
        -e POSTGRES_PASSWORD=sentinel123 ^
        -e POSTGRES_DB=sentinel_isskb ^
        -v sentinel-pgdata:/var/lib/postgresql/data ^
        -p 5432:5432 ^
        postgres:16-alpine
) else (
    echo        Контейнер существует — запускаем...
    docker start sentinel-postgres
)

echo  [3/5] Ожидание готовности PostgreSQL (15 сек)...
timeout /t 15 /nobreak >nul

echo  [4/5] Создание баз данных...
docker exec sentinel-postgres psql -U sentinel_user -d sentinel_isskb -c "SELECT 1" >nul 2>&1
if errorlevel 1 (
    docker exec sentinel-postgres psql -U sentinel_user -d postgres -c "CREATE DATABASE sentinel_isskb OWNER sentinel_user;" 2>nul
)
docker exec sentinel-postgres psql -U sentinel_user -d postgres -c "CREATE DATABASE sentinel_auth OWNER sentinel_user;" 2>nul

echo  [5/5] Восстановление данных из дампов...
echo        Восстанавливаю sentinel_isskb...
type "%~dp0dumps\sentinel_isskb.sql" | docker exec -i sentinel-postgres psql -U sentinel_user -d sentinel_isskb -q
echo        Восстанавливаю sentinel_auth...
type "%~dp0dumps\sentinel_auth.sql" | docker exec -i sentinel-postgres psql -U sentinel_user -d sentinel_auth -q

echo.
echo  ╔══════════════════════════════════════════════════════╗
echo  ║   Готово! Теперь запускай: start.ps1                ║
echo  ╚══════════════════════════════════════════════════════╝
echo.
pause

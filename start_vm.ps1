#Requires -Version 5.1
# SENTINEL ISSKB — запуск с внешним PostgreSQL

$ErrorActionPreference = "Continue"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
chcp 65001 | Out-Null
$Host.UI.RawUI.WindowTitle = "SENTINEL ISSKB — Запуск"

$APP_DIR  = Join-Path $PSScriptRoot "security_dashboard"
$DATABASE = "sentinel_isskb"
$AUTH_DB  = "sentinel_auth"
$PORT     = 8001
$PG_USER  = "sentinel_user"
$PG_PASS  = "sentinel123"
$PG_HOST  = "127.0.0.1"
$PG_PORT  = "5432"

function Hdr($text) { Write-Host "  $text" -ForegroundColor Cyan }
function OK($text) {
    Write-Host "  [" -NoNewline -ForegroundColor DarkGray
    Write-Host " OK " -NoNewline -ForegroundColor Green
    Write-Host "] " -NoNewline -ForegroundColor DarkGray
    Write-Host $text
}
function INFO($text) {
    Write-Host "  [" -NoNewline -ForegroundColor DarkGray
    Write-Host " .. " -NoNewline -ForegroundColor Yellow
    Write-Host "] " -NoNewline -ForegroundColor DarkGray
    Write-Host $text -ForegroundColor Yellow
}
function FAIL($text) {
    Write-Host ""
    Write-Host "  [" -NoNewline -ForegroundColor DarkGray
    Write-Host "FAIL" -NoNewline -ForegroundColor Red
    Write-Host "] $text" -ForegroundColor Red
    Write-Host ""
    Write-Host "  Нажмите Enter для выхода..." -ForegroundColor DarkGray
    Read-Host | Out-Null
    exit 1
}
function Divider { Write-Host ("  " + ("─" * 52)) -ForegroundColor DarkGray }

function Get-WorkingPython {
    $candidates = @(
        @{ Exe = "py";     Args = @("-3.12") },
        @{ Exe = "py";     Args = @("-3.13") },
        @{ Exe = "py";     Args = @("-3.11") },
        @{ Exe = "py";     Args = @("-3") },
        @{ Exe = "python"; Args = @() }
    )
    foreach ($c in $candidates) {
        $exe = $c.Exe; $candArgs = $c.Args
        try {
            $v = & $exe @candArgs --version 2>&1
            if ($LASTEXITCODE -eq 0 -and "$v" -match "Python 3") {
                return @{ Exe = $exe; Args = $candArgs; Version = "$v" }
            }
        } catch { }
    }
    return $null
}

Clear-Host
Write-Host ""
Write-Host "  ╔══════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "  ║    SENTINEL  ·  ISSKB  ·  Запуск системы        ║" -ForegroundColor Cyan
Write-Host "  ║    База: sentinel_isskb   Порт: 8001             ║" -ForegroundColor DarkCyan
Write-Host "  ╚══════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# ── ШАГ 1: PostgreSQL ────────────────────────────────────────────────────────

Hdr "1/3  PostgreSQL (внешний)"
Divider

$pgPaths = @(
    "C:\Program Files\PostgreSQL\17\bin\psql.exe",
    "C:\Program Files\PostgreSQL\16\bin\psql.exe",
    "C:\Program Files\PostgreSQL\15\bin\psql.exe",
    "C:\Program Files\PostgreSQL\14\bin\psql.exe"
)
$psqlExe = $pgPaths | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $psqlExe) {
    $cmd = Get-Command psql -ErrorAction SilentlyContinue
    if ($cmd) { $psqlExe = $cmd.Source }
}
if (-not $psqlExe) {
    FAIL "psql не найден. Установите PostgreSQL с https://www.postgresql.org/download/windows/"
}
OK "psql найден: $psqlExe"

$env:PGPASSWORD = $PG_PASS
foreach ($db in @($DATABASE, $AUTH_DB)) {
    $dbTest = & $psqlExe -h $PG_HOST -p $PG_PORT -U $PG_USER -d $db -tAc "SELECT 1;" 2>&1
    if ($LASTEXITCODE -ne 0) {
        INFO "База $db не найдена — пробую создать..."
        & $psqlExe -h $PG_HOST -p $PG_PORT -U $PG_USER -d postgres -v ON_ERROR_STOP=1 -c "CREATE DATABASE $db OWNER $PG_USER;" | Out-Null
        if ($LASTEXITCODE -ne 0) {
            FAIL "Не удалось подключиться или создать БД $db. Проверьте PostgreSQL, пользователя $PG_USER и пароль."
        }
    }
    OK "База данных $db доступна"
}
Write-Host ""

# ── ШАГ 2: Python-зависимости ────────────────────────────────────────────────

Hdr "2/3  Python и зависимости"
Divider

$py = Get-WorkingPython
if (-not $py) { FAIL "Рабочий Python 3 не найден. Установите Python 3.12+ с https://www.python.org/downloads/." }
$PyExe = $py.Exe
$PyArgs = $py.Args
OK "Python: $($py.Version)  (запуск: $PyExe $($PyArgs -join ' '))"

$pyMajorMinor = (& $PyExe @PyArgs -c "import sys; print(str(sys.version_info.major)+'.'+str(sys.version_info.minor))" 2>&1).ToString().Trim()
$depsCheck = & $PyExe @PyArgs -c "import fastapi, uvicorn, asyncpg, multipart, psutil, bcrypt, jose, httpx; print('ok')" 2>&1
if ($LASTEXITCODE -ne 0 -or "$depsCheck" -notmatch "ok") {
    if ($pyMajorMinor -eq "3.12" -and (Test-Path (Join-Path $APP_DIR "wheels"))) {
        INFO "Устанавливаю зависимости ОФЛАЙН из wheels\ (Python 3.12)..."
        & $PyExe @PyArgs -m pip install --no-index --find-links (Join-Path $APP_DIR "wheels") `
            -r (Join-Path $APP_DIR "requirements.txt") --quiet
    } else {
        INFO "Для этой версии Python нужны свежие колёса — устанавливаю зависимости через pip..."
        & $PyExe @PyArgs -m pip install --disable-pip-version-check --no-cache-dir `
            -r (Join-Path $APP_DIR "requirements-py314.txt")
    }
    if ($LASTEXITCODE -ne 0) { FAIL "Установка зависимостей не удалась." }
    OK "Зависимости установлены"
} else {
    OK "Все зависимости установлены"
}
Write-Host ""

# ── ШАГ 3: Запуск сервера ────────────────────────────────────────────────────

Write-Host "  ╔══════════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "  ║   Все проверки пройдены. Запускаю сервер...     ║" -ForegroundColor Green
Write-Host "  ║                                                  ║" -ForegroundColor Green
Write-Host "  ║   Адрес:  http://localhost:8001                  ║" -ForegroundColor White
Write-Host "  ║   Docs:   http://localhost:8001/api/docs         ║" -ForegroundColor DarkGray
Write-Host "  ║                                                  ║" -ForegroundColor Green
Write-Host "  ║   Для остановки: Ctrl+C                          ║" -ForegroundColor DarkGray
Write-Host "  ╚══════════════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""

Set-Location $APP_DIR
$env:PYTHONUTF8 = "1"
$env:SENTINEL_PG_EMBEDDED = "0"
$env:SENTINEL_DSN = "postgresql://$PG_USER`:$PG_PASS@$PG_HOST`:$PG_PORT/$DATABASE"
$env:AUTH_DSN = "postgresql://$PG_USER`:$PG_PASS@$PG_HOST`:$PG_PORT/$AUTH_DB"
& $PyExe @PyArgs main.py

Write-Host ""
Write-Host "  Сервер завершил работу. Нажмите Enter для выхода..." -ForegroundColor Yellow
Read-Host | Out-Null

#Requires -Version 5.1
# SENTINEL ISSKB — запуск на нативном PostgreSQL (без Docker)

$ErrorActionPreference = "Continue"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
chcp 65001 | Out-Null
$Host.UI.RawUI.WindowTitle = "SENTINEL ISSKB — Запуск"

$APP_DIR  = Join-Path $PSScriptRoot "security_dashboard"
$DATABASE = "sentinel_isskb"
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

Clear-Host
Write-Host ""
Write-Host "  ╔══════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "  ║    SENTINEL  ·  ISSKB  ·  Запуск системы        ║" -ForegroundColor Cyan
Write-Host "  ║    База: sentinel_isskb   Порт: 8001             ║" -ForegroundColor DarkCyan
Write-Host "  ╚══════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# ── ШАГ 1: PostgreSQL ────────────────────────────────────────────────────────

Hdr "1/3  PostgreSQL (нативный)"
Divider

# Ищем psql в стандартных путях
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
$pgTest = & $psqlExe -h $PG_HOST -p $PG_PORT -U $PG_USER -d $DATABASE -c "SELECT 1;" 2>&1
if ($LASTEXITCODE -ne 0) {
    FAIL "Не удалось подключиться к БД $DATABASE. Убедитесь, что PostgreSQL запущен и БД создана."
}
OK "PostgreSQL и база $DATABASE доступны"
Write-Host ""

# ── ШАГ 2: Python-зависимости ────────────────────────────────────────────────

Hdr "2/3  Python и зависимости"
Divider

# Определяем РАБОЧИЙ интерпретатор Python (голый "python" здесь — заглушка
# Microsoft Store, молча ничего не запускает). Предпочитаем py -3.13.
$pyCandidates = @(
    @{ Exe = "py";     Args = @("-3.13") },
    @{ Exe = "py";     Args = @("-3") },
    @{ Exe = "python"; Args = @() }
)
$PyExe = $null; $PyArgs = @()
foreach ($c in $pyCandidates) {
    $exe = $c.Exe; $a = $c.Args
    try {
        $v = & $exe @a --version 2>&1
        if ($LASTEXITCODE -eq 0 -and "$v" -match "Python 3") { $PyExe = $exe; $PyArgs = $a; break }
    } catch { }
}
if (-not $PyExe) { FAIL "Рабочий Python 3 не найден. Установите Python 3.11+ (с лаунчером py) с https://www.python.org/downloads/ и отключите заглушку Microsoft Store." }
$pyVer = (& $PyExe @PyArgs --version 2>&1)
OK "Python: $pyVer  (запуск: $PyExe $($PyArgs -join ' '))"

$depsOK = & $PyExe @PyArgs -c "import fastapi, uvicorn, asyncpg, multipart, psutil, bcrypt, jose, httpx; print('ok')" 2>&1
if ($depsOK -notmatch "ok") {
    INFO "Устанавливаю зависимости ОФЛАЙН из wheels\ (без интернета)..."
    & $PyExe @PyArgs -m pip install --no-index --find-links (Join-Path $APP_DIR "wheels") `
        -r (Join-Path $APP_DIR "requirements.txt") --quiet
    if ($LASTEXITCODE -ne 0) { FAIL "Офлайн-установка не удалась. Проверьте папку security_dashboard\wheels\" }
    OK "Зависимости установлены (офлайн, без обращения к интернету)"
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
& $PyExe @PyArgs main.py

Write-Host ""
Write-Host "  Сервер завершил работу. Нажмите Enter для выхода..." -ForegroundColor Yellow
Read-Host | Out-Null

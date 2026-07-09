#Requires -Version 5.1
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
chcp 65001 | Out-Null

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$AppDir = Join-Path $Root "security_dashboard"
$DumpDir = Join-Path $Root "dumps"
$PgDump = Join-Path $AppDir "pgsql\bin\pg_dump.exe"
$SetupPg = Join-Path $AppDir "setup_postgres.ps1"
$Port = 5440
$User = "sentinel_user"

function Fail($msg) {
    Write-Host "[ERROR] $msg" -ForegroundColor Red
    Read-Host "Нажмите Enter для выхода" | Out-Null
    exit 1
}
function Get-WorkingPython {
    $candidates = @()
    $venv314 = Join-Path $AppDir ".venv314\Scripts\python.exe"
    if (Test-Path $venv314) { $candidates += @{ Exe = $venv314; Args = @() } }
    $candidates += @(
        @{ Exe = "py";     Args = @("-3.12") },
        @{ Exe = "py";     Args = @("-3.13") },
        @{ Exe = "py";     Args = @("-3.11") },
        @{ Exe = "py";     Args = @("-3") },
        @{ Exe = "python"; Args = @() }
    )
    foreach ($c in $candidates) {
        $exe = $c.Exe
        $candArgs = $c.Args
        try {
            $v = & $exe @candArgs --version 2>&1
            if ($LASTEXITCODE -eq 0 -and "$v" -match "Python 3") {
                return @{ Exe = $exe; Args = $candArgs; Version = "$v" }
            }
        } catch { }
    }
    return $null
}

if (-not (Test-Path $PgDump)) {
    Write-Host "[..] Портативный PostgreSQL не найден — запускаю установку..." -ForegroundColor Yellow
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File $SetupPg
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path $PgDump)) { Fail "pg_dump не найден" }
}

$py = Get-WorkingPython
if (-not $py) { Fail "Python 3 не найден" }
$PyExe = $py.Exe
$PyArgs = $py.Args

Set-Location $AppDir
$env:PYTHONUTF8 = "1"
$env:SENTINEL_PG_EMBEDDED = "1"
$env:SENTINEL_PG_PORT = "$Port"
$env:SENTINEL_DSN = "postgresql://$User@127.0.0.1:$Port/sentinel_isskb"
$env:AUTH_DSN = "postgresql://$User@127.0.0.1:$Port/sentinel_auth"
& $PyExe @PyArgs -c "from database import embedded_pg; embedded_pg.start()"
if ($LASTEXITCODE -ne 0) { Fail "Не удалось запустить PostgreSQL" }

if (-not (Test-Path $DumpDir)) { New-Item -ItemType Directory -Path $DumpDir | Out-Null }
$env:PGPASSWORD = $env:SENTINEL_PG_PASSWORD
if (-not $env:PGPASSWORD) { $env:PGPASSWORD = "sentinel123" }

Write-Host "[1/2] Выгружаю sentinel_isskb..." -ForegroundColor Cyan
& $PgDump -h 127.0.0.1 -p $Port -U $User -d sentinel_isskb --clean --if-exists -f (Join-Path $DumpDir "sentinel_isskb.sql")
if ($LASTEXITCODE -ne 0) { Fail "Не удалось выгрузить sentinel_isskb" }

Write-Host "[2/2] Выгружаю sentinel_auth..." -ForegroundColor Cyan
& $PgDump -h 127.0.0.1 -p $Port -U $User -d sentinel_auth --clean --if-exists -f (Join-Path $DumpDir "sentinel_auth.sql")
if ($LASTEXITCODE -ne 0) { Fail "Не удалось выгрузить sentinel_auth" }

Write-Host "[OK] Дампы сохранены в $DumpDir" -ForegroundColor Green
Read-Host "Нажмите Enter для выхода" | Out-Null

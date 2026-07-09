#Requires -Version 5.1
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
chcp 65001 | Out-Null
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$AppDir = Join-Path $Root "security_dashboard"
Set-Location $AppDir

$pyCandidates = @(
    @{ Exe = "py";     Args = @("-3.12") },
    @{ Exe = "py";     Args = @("-3") },
    @{ Exe = "python"; Args = @() }
)
$PyExe = $null
$PyArgs = @()
foreach ($c in $pyCandidates) {
    $exe = $c.Exe
    $candArgs = $c.Args
    try {
        $v = & $exe @candArgs --version 2>&1
        if ($LASTEXITCODE -eq 0 -and "$v" -match "Python 3") {
            $PyExe = $exe
            $PyArgs = $candArgs
            break
        }
    } catch { }
}
if (-not $PyExe) { throw "Python 3 не найден" }
$env:PYTHONUTF8 = "1"
& $PyExe @PyArgs monitor_skyhunter.py
Read-Host "Нажмите Enter для выхода" | Out-Null

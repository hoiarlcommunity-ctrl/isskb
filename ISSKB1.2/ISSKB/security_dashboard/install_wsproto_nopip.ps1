$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Site = Join-Path $Root ".venv314\Lib\site-packages"
$Vendor = Join-Path $Root "vendor_wsproto"

if (!(Test-Path $Site)) {
    Write-Host "[ERR] Не найдена папка venv: $Site" -ForegroundColor Red
    Write-Host "Сначала запустите setup_py314.ps1, чтобы создать .venv314" -ForegroundColor Yellow
    exit 1
}
if (!(Test-Path $Vendor)) {
    Write-Host "[ERR] Не найдена папка vendor_wsproto: $Vendor" -ForegroundColor Red
    exit 1
}

Copy-Item -Path (Join-Path $Vendor "wsproto") -Destination $Site -Recurse -Force
$distInfos = Get-ChildItem -Path $Vendor -Filter "wsproto-*.dist-info" -Directory -ErrorAction SilentlyContinue
foreach ($di in $distInfos) {
    Copy-Item -Path $di.FullName -Destination $Site -Recurse -Force
}

$Py = Join-Path $Root ".venv314\Scripts\python.exe"
& $Py -c "import wsproto; print('wsproto OK', getattr(wsproto, '__version__', 'unknown'))"
Write-Host "[OK] wsproto установлен локально без pip и без интернета." -ForegroundColor Green
Write-Host "Теперь остановите ISSKB через Ctrl+C и снова запустите .\run_py314.bat"

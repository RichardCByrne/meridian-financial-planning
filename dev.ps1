# Run backend (FastAPI/uvicorn) and frontend (Vite) together.
# Usage:  .\dev.ps1
# Stops both on Ctrl+C.

$ErrorActionPreference = "Stop"

$root = $PSScriptRoot
$backend = Join-Path $root "backend"
$frontend = Join-Path $root "frontend"

# Use latest installed Node LTS from fnm.
$fnmCmd = Get-Command fnm -ErrorAction SilentlyContinue
if (-not $fnmCmd) {
    $fnmCandidates = @(
        "$env:LOCALAPPDATA\Microsoft\WinGet\Packages\Schniz.fnm_Microsoft.Winget.Source_8wekyb3d8bbwe\fnm.exe",
        "$env:LOCALAPPDATA\fnm\fnm.exe"
    )
    $fnmPath = $fnmCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
    if ($fnmPath) { $fnmCmd = Get-Command $fnmPath }
}
if ($fnmCmd) {
    & $fnmCmd.Source env --use-on-cd --shell powershell | Out-String | Invoke-Expression
    & $fnmCmd.Source use lts-latest | Out-Null
} else {
    Write-Warning "fnm not found on PATH - falling back to system node."
}

Write-Host "Starting backend on http://127.0.0.1:8000 ..." -ForegroundColor Cyan
$be = Start-Process -PassThru -NoNewWindow `
    -FilePath (Join-Path $backend ".venv\Scripts\python.exe") `
    -ArgumentList @("-m", "uvicorn", "app.main:app", "--reload", "--port", "8000", "--host", "127.0.0.1") `
    -WorkingDirectory $backend

Write-Host "Starting frontend on http://localhost:5173 ..." -ForegroundColor Cyan
$fe = Start-Process -PassThru -NoNewWindow `
    -FilePath "npm.cmd" `
    -ArgumentList @("run", "dev") `
    -WorkingDirectory $frontend

try {
    Wait-Process -Id $be.Id, $fe.Id
} finally {
    Write-Host "`nShutting down..." -ForegroundColor Yellow
    Stop-Process -Id $be.Id -Force -ErrorAction SilentlyContinue
    Stop-Process -Id $fe.Id -Force -ErrorAction SilentlyContinue
}

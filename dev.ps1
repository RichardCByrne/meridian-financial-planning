# Run backend (FastAPI/uvicorn) and frontend (Vite) together.
# Usage:  .\dev.ps1
# Stops both on Ctrl+C.

$ErrorActionPreference = "Stop"

$root = $PSScriptRoot
$backend = Join-Path $root "backend"
$frontend = Join-Path $root "frontend"

# Use Node 18 from nvm if available — Node 25.x on this machine ships without npm.
$node18 = "C:\Users\Richard\AppData\Roaming\nvm\v18.6.0"
if (Test-Path $node18) {
    $env:Path = "$node18;$env:Path"
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

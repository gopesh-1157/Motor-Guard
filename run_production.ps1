# ==============================================================================
# MotorGuard — Production Edge Gateway Launch Script (Windows PowerShell)
# Launches Mosquitto/amqtt Broker and FastAPI Production Gateway.
# Serves the compiled production frontend directly from FastAPI (NO Vite dev server).
# ==============================================================================

Write-Host "==========================================================" -ForegroundColor Green
Write-Host "  MotorGuard Industrial Production Gateway" -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Green

$WorkspaceRoot = $PSScriptRoot

# 1. Verify production build exists
if (-not (Test-Path "$WorkspaceRoot\frontend\dist\index.html")) {
    Write-Host "[1/3] Building production frontend bundle (tsc + vite build)..." -ForegroundColor Yellow
    Push-Location "$WorkspaceRoot\frontend"
    npm run build
    Pop-Location
} else {
    Write-Host "[1/3] Verified production frontend build in frontend\dist" -ForegroundColor Cyan
}

# 2. Start Local MQTT Broker (port 1883)
Write-Host "[2/3] Starting MQTT Broker on port 1883..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "`$host.UI.RawUI.WindowTitle = 'MotorGuard: MQTT Broker'; cd '$WorkspaceRoot'; python infrastructure/local_broker.py"

Start-Sleep -Seconds 1

# 3. Start FastAPI Production Server (port 8000, serving API + WebSocket + Production Dashboard)
Write-Host "[3/3] Starting FastAPI Production Gateway (port 8000)..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "`$host.UI.RawUI.WindowTitle = 'MotorGuard: Production Gateway'; cd '$WorkspaceRoot'; python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --workers 2"

Write-Host "==========================================================" -ForegroundColor Green
Write-Host "  MotorGuard Production Stack Active!" -ForegroundColor Green
Write-Host "  Production Web Dashboard: http://localhost:8000/" -ForegroundColor White
Write-Host "  REST API Documentation:   http://localhost:8000/docs" -ForegroundColor White
Write-Host "  WebSocket Live Stream:    ws://localhost:8000/ws/telemetry" -ForegroundColor White
Write-Host "  (No Node.js / Vite dev server exposed in production)" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Green

# ==============================================================================
# MotorGuard — One-Click Development Launch Script (Windows PowerShell)
# Launches MQTT Broker, FastAPI Backend, React Frontend, and Motor Simulator
# in dedicated terminal windows for live log monitoring.
# ==============================================================================

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  Starting MotorGuard Platform..." -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

$WorkspaceRoot = $PSScriptRoot

# 1. Start Local MQTT Broker (amqtt on port 1883)
Write-Host "[1/4] Starting Local MQTT Broker (port 1883)..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "`$host.UI.RawUI.WindowTitle = 'MotorGuard: MQTT Broker'; cd '$WorkspaceRoot'; python infrastructure/local_broker.py"

Start-Sleep -Seconds 1

# 2. Start FastAPI Edge Gateway Backend (uvicorn on port 8000)
Write-Host "[2/4] Starting FastAPI Gateway API (port 8000)..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "`$host.UI.RawUI.WindowTitle = 'MotorGuard: FastAPI Backend'; cd '$WorkspaceRoot'; python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload"

Start-Sleep -Seconds 2

# 3. Start React Frontend Dashboard (Vite on port 5173)
Write-Host "[3/4] Starting React Industrial Dashboard (port 5173)..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "`$host.UI.RawUI.WindowTitle = 'MotorGuard: React Frontend'; cd '$WorkspaceRoot/frontend'; npm run dev"

Start-Sleep -Seconds 1

# 4. Start Virtual Motor Fleet Simulator
Write-Host "[4/5] Starting Virtual Motor Fleet Simulator..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "`$host.UI.RawUI.WindowTitle = 'MotorGuard: Motor Simulator'; cd '$WorkspaceRoot'; python simulator/simulator.py"

Start-Sleep -Seconds 1

# 5. Start ESP32 Hardware USB Serial Bridge (COM7)
Write-Host "[5/5] Starting ESP32 Hardware USB Serial Bridge..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "`$host.UI.RawUI.WindowTitle = 'MotorGuard: Hardware Serial Bridge'; cd '$WorkspaceRoot'; python infrastructure/serial_bridge.py"

Write-Host "==========================================================" -ForegroundColor Green
Write-Host "  MotorGuard services launched in 5 terminal windows!" -ForegroundColor Green
Write-Host "  Dashboard:     http://localhost:5173" -ForegroundColor White
Write-Host "  FastAPI Docs:  http://localhost:8000/docs" -ForegroundColor White
Write-Host "  Admin Login:   admin / adminpassword123" -ForegroundColor White
Write-Host "==========================================================" -ForegroundColor Green


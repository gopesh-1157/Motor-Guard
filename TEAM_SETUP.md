# MotorGuard — Team Onboarding & Setup Guide

Welcome to **MotorGuard**! This guide walks you through setting up and running the full MotorGuard platform locally on your machine.

---

## 📌 Prerequisites

Ensure you have the following installed before starting:

| Tool | Recommended Version | Verification Command | Notes |
| :--- | :--- | :--- | :--- |
| **Python** | 3.11 or higher | `python --version` | Ensure `pip` is in your PATH |
| **Node.js & npm** | Node 20 LTS (or 18+) | `node -v` & `npm -v` | Required for React frontend |
| **MongoDB** | 7.0+ (or Docker) | `mongod --version` or `docker --version` | Local Community Server or Docker container |
| **Git** | 2.x+ | `git --version` | For cloning and version control |

*(Optional)* If testing physical ESP32 hardware:
- Micro-USB cable connected to your PC
- Silicon Labs CP210x or CH340 USB-to-UART bridge drivers

---

## 🚀 Quick Setup (Step-by-Step)

### 1. Clone & Enter Workspace
```bash
git clone <repo-url>
cd MotorGuard
```

### 2. Configure Environment Variables
Copy the template `.env.example` to create your active `.env` configuration:

- **Windows (PowerShell):**
  ```powershell
  Copy-Item .env.example .env
  ```
- **macOS / Linux:**
  ```bash
  cp .env.example .env
  ```

*(Default values in `.env` are preconfigured to work out-of-the-box for local development.)*

---

### 3. Set Up Python Virtual Environment

Create and activate a virtual environment, then install all platform requirements:

- **Windows (PowerShell):**
  ```powershell
  python -m venv venv
  .\venv\Scripts\Activate.ps1
  python -m pip install --upgrade pip
  pip install -r requirements.txt
  ```

- **macOS / Linux (Bash/Zsh):**
  ```bash
  python3 -m venv venv
  source venv/bin/activate
  python3 -m pip install --upgrade pip
  pip install -r requirements.txt
  ```

---

### 4. Install Frontend Dependencies

```bash
cd frontend
npm install
cd ..
```

---

### 5. Start Supporting Database (MongoDB)

You have two options for MongoDB:

- **Option A (Docker Desktop - Recommended):**
  ```bash
  docker compose -f infrastructure/docker-compose.yml up -d mongodb
  ```

- **Option B (Native Windows / Mac Service):**
  Ensure MongoDB Community Service is running locally on port `27017`.
  *(Windows: Verify in `services.msc` or run `net start MongoDB`)*

---

## 🏃 Running the Application

### Option 1: One-Click Launch (Windows PowerShell)

Simply execute the automated runner script:
```powershell
.\run_dev.ps1
```
This script automatically opens 5 dedicated terminal windows for:
1. **MQTT Broker** (`0.0.0.0:1883`)
2. **FastAPI Backend API** (`0.0.0.0:8000`)
3. **React Vite Frontend** (`localhost:5173`)
4. **Virtual Motor Fleet Simulator** (generates real-time sensor telemetry)
5. **ESP32 Serial Bridge** (bridges physical hardware if connected)

---

### Option 2: Manual Terminal Launch (Cross-Platform)

If you are on macOS/Linux or prefer manual control, open 4 terminal tabs from the project root:

#### **Terminal 1: Local MQTT Broker**
```bash
# Activated virtual environment
python infrastructure/local_broker.py
```

#### **Terminal 2: FastAPI Gateway API**
```bash
# Activated virtual environment
python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```

#### **Terminal 3: React Frontend Dashboard**
```bash
cd frontend
npm run dev
```

#### **Terminal 4: Virtual Motor Simulator**
```bash
# Activated virtual environment
python simulator/simulator.py
```

*(Terminal 5 is only needed if physical ESP32 hardware is plugged into a USB port: `python infrastructure/serial_bridge.py`)*

---

## 🌐 URLs & Default Credentials

| Resource | URL | Credentials |
| :--- | :--- | :--- |
| **Web Dashboard** | [http://localhost:5173](http://localhost:5173) | Admin Login below |
| **API Swagger Docs** | [http://localhost:8000/docs](http://localhost:8000/docs) | N/A |
| **ReDoc Specifications** | [http://localhost:8000/redoc](http://localhost:8000/redoc) | N/A |
| **Default Admin Username** | `admin` | |
| **Default Admin Password** | `adminpassword123` | |

---

## 🧪 Running Tests

Ensure your virtual environment is active, then run pytest:
```bash
pytest tests/ -v
```

---

## ⚠️ Troubleshooting FAQ

1. **`Execution of scripts is disabled on this system` (PowerShell error):**
   Run PowerShell as Administrator and execute:
   ```powershell
   Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
   ```

2. **MongoDB Connection Refused (`127.0.0.1:27017`):**
   - Check if Docker container is up: `docker ps`
   - Or verify local MongoDB service is started: `net start MongoDB`

3. **Port 1883 or Port 8000 Already in Use:**
   - Stop any existing background Mosquitto or Uvicorn instances.
   - On Windows: `netstat -ano | findstr :1883` and kill PID using `taskkill /PID <PID> /F`.

4. **I don't have physical hardware. Can I still test everything?**
   - Yes! The `simulator/simulator.py` script automatically simulates full ADXL345 vibration, DHT11 temperature, ACS712 current, and Edge Impulse TinyML classification data. You can observe live graphs, triggers, and alerts directly in the dashboard.

# MotorGuard — Local Development Setup for Windows

## 1. Prerequisites Checklist

Ensure the following tools are installed on your Windows machine:
- **Windows OS**: Windows 10/11 (64-bit) with PowerShell 5.1 or PowerShell 7+
- **Python**: Version 3.11 or higher (Check with `python --version`)
- **Node.js & npm**: Node.js 20 LTS or higher (Check with `node -v` and `npm -v`)
- **Docker Desktop**: Recommended for running local MongoDB and Mosquitto containers (Check with `docker --version`)
- **Git**: For source control (Check with `git --version`)

---

## 2. Step-by-Step Workspace Setup (PowerShell)

### Step 2.1: Clone and Open Workspace
```powershell
# Open Windows PowerShell and navigate to your MotorGuard directory
cd C:\Users\<Username>\Downloads\MotorGuard
```

### Step 2.2: Configure Environment Variables
```powershell
# Copy the environment template to create your active .env file
Copy-Item .env.example .env
```

### Step 2.3: Set Up Python Backend Environment
```powershell
# Create a dedicated virtual environment in backend/
cd backend
python -m venv venv

# Activate the virtual environment
.\venv\Scripts\Activate.ps1

# Upgrade pip and install wheel
python -m pip install --upgrade pip setuptools wheel
cd ..
```

### Step 2.4: Set Up Frontend Node Environment
```powershell
# In a subsequent phase (Phase 1/3), when frontend package.json is initialized:
cd frontend
npm install
cd ..
```

---

## 3. Running Local Supporting Services (MongoDB & Mosquitto)

You have two convenient options to run MongoDB and Mosquitto on Windows:

### Option A: Via Docker Compose (Recommended)
```powershell
# Start local Mosquitto MQTT broker and MongoDB in the background
docker compose -f infrastructure/docker-compose.yml up -d mosquitto mongodb

# Verify running containers
docker ps
```

### Option B: Native Windows Services (Without Docker)
If Docker Desktop is not installed:
1. **Mosquitto**: Download and run the official Windows installer from [mosquitto.org](https://mosquitto.org/download/). Run in PowerShell:
   ```powershell
   & "C:\Program Files\mosquitto\mosquitto.exe" -v -c infrastructure/mosquitto/mosquitto.conf
   ```
2. **MongoDB Community Server**: Download and run the official Windows installer from [mongodb.com](https://www.mongodb.com/try/download/community). Run as a standard Windows Service.

---

## 4. Verification & Sanity Checks

Verify that your local environment is operational:

```powershell
# 1. Test MQTT broker listening on port 1883
Test-NetConnection -ComputerName 127.0.0.1 -Port 1883

# 2. Test MongoDB listening on port 27017
Test-NetConnection -ComputerName 127.0.0.1 -Port 27017

# 3. Test MQTT publish and subscribe (if mosquitto clients installed)
# Terminal A:
# mosquitto_sub -h 127.0.0.1 -t "motorguard/v1/#" -v
# Terminal B:
# mosquitto_pub -h 127.0.0.1 -t "motorguard/v1/test/heartbeat" -m '{"status":"ok"}'
```

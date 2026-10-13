# MotorGuard — Environment Variables Specification

## 1. Overview & Startup Validation

MotorGuard utilizes environment-based configuration following the 12-factor application methodology.
At startup, the FastAPI backend parses all variables through a strict **Pydantic `BaseSettings`** class. If any mandatory production secret or configuration is absent or malformed, the application will **fail fast** and log a clear configuration error rather than starting with unsafe defaults.

---

## 2. Complete Inventory Table

| Variable Name | Type | Default (Dev) | Required (Dev) | Required (Prod) | Description |
| :--- | :--- | :--- | :---: | :---: | :--- |
| **COMMON & SECURITY** | | | | | |
| `ENVIRONMENT` | String | `development` | Yes | Yes | `development`, `testing`, `production` |
| `LOG_LEVEL` | String | `INFO` | No | Yes | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `SECRET_KEY` | String (Hex/B64) | *dev-insecure-key* | No | **Yes** | 256-bit secret for signing JWT auth tokens |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Integer | `480` | No | Yes | JWT session validity duration |
| **GATEWAY & NETWORKING** | | | | | |
| `HOST` | String | `0.0.0.0` | No | Yes | Network interface for FastAPI to bind |
| `PORT` | Integer | `8000` | No | Yes | Gateway API port |
| `CORS_ORIGINS` | String | `http://localhost:5173` | No | Yes | Comma-separated list of allowed browser origins |
| **MONGODB PERSISTENCE** | | | | | |
| `MONGO_URI` | String | `mongodb://127.0.0.1:27017` | Yes | Yes | Full connection URI (with auth if enabled) |
| `MONGO_DB_NAME` | String | `motorguard_db` | Yes | Yes | Primary database name |
| `TELEMETRY_RETENTION_DAYS` | Integer | `90` | No | Yes | TTL cleanup horizon for raw telemetry |
| **MQTT MESSAGING (MOSQUITTO)** | | | | | |
| `MQTT_BROKER_HOST` | String | `127.0.0.1` | Yes | Yes | Local gateway IP/hostname for broker |
| `MQTT_BROKER_PORT` | Integer | `1883` | Yes | Yes | 1883 (TCP local), 8883 (MQTTS TLS) |
| `MQTT_USERNAME` | String | `motorguard_gateway` | No | **Yes** | Broker credential for backend subscriber |
| `MQTT_PASSWORD` | String | *empty* | No | **Yes** | Broker password for backend subscriber |
| `MQTT_CLIENT_ID` | String | `motorguard-fastapi-core` | No | Yes | Unique MQTT subscriber client ID |
| `MQTT_KEEPALIVE_SEC` | Integer | `60` | No | Yes | Broker ping interval |
| **DEVICE TIMEOUTS & RULES** | | | | | |
| `DEVICE_STALE_TIMEOUT_SEC` | Integer | `15` | No | Yes | Duration before quiet device marked STALE |
| `DEVICE_OFFLINE_TIMEOUT_SEC` | Integer | `35` | No | Yes | Duration before device marked OFFLINE |
| `DEFAULT_OVERCURRENT_LIMIT_A` | Float | `4.0` | No | Yes | Fallback hardware trip limit |
| `DEFAULT_MAX_TEMP_C` | Float | `50.0` | No | Yes | Fallback thermal warning limit |
| **FRONTEND CLIENT (`frontend/.env`)** | | | | | |
| `VITE_API_BASE_URL` | String | `http://localhost:8000` | Yes | Yes | Base URL for REST endpoints |
| `VITE_WS_BASE_URL` | String | `ws://localhost:8000/ws` | Yes | Yes | Base URL for live WebSockets stream |
| **VIRTUAL SIMULATOR (`simulator/.env`)** | | | | | |
| `SIM_BROKER_HOST` | String | `127.0.0.1` | Yes | Yes | Target Mosquitto broker IP |
| `SIM_BROKER_PORT` | Integer | `1883` | Yes | Yes | Target broker port |
| `SIM_DEVICE_ID` | String | `sim-node-001` | Yes | Yes | Simulated transmitter identity |
| `SIM_MOTOR_ID` | String | `mtr-775-sim` | Yes | Yes | Simulated target motor identity |
| `SIM_INTERVAL_MS` | Integer | `1000` | No | Yes | Transmission interval (ms) |

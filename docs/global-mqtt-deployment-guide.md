# MotorGuard — Global Cloud MQTT Deployment Guide

This guide details the procedure for transitioning MotorGuard from a local broker (`localhost:1883`) to a secure, globally accessible cloud MQTT broker (`MQTTS TLS 8883`) for geographically distributed ESP32 microcontrollers and cloud-hosted backends.

---

## 1. Security Architecture Summary

```
[ESP32 Hardware]  --(MQTTS 8883 | User: esp32_node_001 | CA: ISRG Root X1)-->┐
[Fleet Simulator] --(MQTTS 8883 | User: motorguard_simulator)--------------->┤
                                                                             │
                                                            [Managed Cloud Broker]
                                                            (HiveMQ Cloud / EMQX)
                                                                     │
                                                       (MQTTS 8883 | User: motorguard_gateway)
                                                                     v
                                                            [FastAPI Backend Gateway]
                                                                     │
                                                             (WebSocket WSS:443)
                                                                     v
                                                            [React SCADA Client]
```

### Key Security Controls
1. **In-Transit Encryption**: TLS 1.2+ mandatory on port 8883.
2. **Hardware Identity & Broker Verification**: ESP32 validates broker authenticity against the **ISRG Root X1 CA** certificate (`espClient.setCACert()`). No insecure certificate bypass in production.
3. **Least Privilege Topic ACLs**:
   - `motorguard_gateway`: READ-ONLY on `motorguard/v1/+/telemetry` and `status`.
   - `esp32_node_001`: WRITE-ONLY on `motorguard/v1/ESP32-NODE-001/#`.
   - `motorguard_simulator`: WRITE-ONLY on `motorguard/v1/sim-node-+/telemetry`.
4. **Git Protection**: Hardware secrets stored in `firmware/secrets.h` (git-ignored).

---

## 2. Option A: Managed Cloud Broker (HiveMQ Cloud / EMQX Serverless)

*Recommended for fast, maintenance-free deployment with automated Let's Encrypt TLS.*

### Step 1: Provision Free Cloud Cluster
1. Sign up for free at [HiveMQ Cloud](https://www.hivemq.com/cloud/) or [EMQX Cloud](https://www.emqx.com/en/cloud).
2. Create a Serverless cluster.
3. Note your cluster host, e.g.: `cluster-xyz.s1.eu.hivemq.cloud`, Port: `8883`.

### Step 2: Create Scoped Credentials
In the broker console, create 3 separate users:

| Username | Role | Permissions / Topic Scope |
| :--- | :--- | :--- |
| `motorguard_gateway` | Backend Subscriber | Read: `motorguard/v1/+/telemetry`, `motorguard/v1/+/status` |
| `motorguard_simulator` | Testing & Simulator | Write: `motorguard/v1/sim-node-+/telemetry` |
| `esp32_node_001` | Physical Motor Sensor Node 1 | Write: `motorguard/v1/ESP32-NODE-001/#` |

### Step 3: Configure Backend Environment
Set environment variables on your cloud hosting platform (e.g. Render, Railway, AWS ECS, or `.env`):
```bash
ENVIRONMENT=production
MQTT_BROKER_HOST=cluster-xyz.s1.eu.hivemq.cloud
MQTT_BROKER_PORT=8883
MQTT_USERNAME=motorguard_gateway
MQTT_PASSWORD=YourStrongGatewayPassword!
MQTT_USE_TLS=true
MQTT_TRANSPORT=tcp
```

### Step 4: Provision ESP32 Firmware
1. Copy the secrets template:
   ```bash
   cp firmware/secrets.h.example firmware/secrets.h
   ```
2. Edit `firmware/secrets.h` with your Wi-Fi and device credentials:
   ```cpp
   #define USE_CLOUD_MQTT 1
   #define STA_WIFI_SSID     "Your-Plant-WiFi"
   #define STA_WIFI_PASSWORD "Your-Plant-WiFi-Password"
   #define CLOUD_MQTT_BROKER "cluster-xyz.s1.eu.hivemq.cloud"
   #define CLOUD_MQTT_PORT   8883
   #define CLOUD_DEVICE_ID   "ESP32-NODE-001"
   #define CLOUD_MQTT_USER   "esp32_node_001"
   #define CLOUD_MQTT_PASS   "YourDevicePassword!"
   ```
3. Flash the sketch to the ESP32. The firmware automatically verifies the broker TLS certificate using the embedded **ISRG Root X1 CA** certificate.

---

## 3. Option B: Self-Hosted Mosquitto on Cloud VPS

For self-hosted deployments on AWS EC2, DigitalOcean, or Hetzner:

1. Copy configuration templates:
   - Configuration: [`infrastructure/mosquitto/mosquitto.production.conf`](../infrastructure/mosquitto/mosquitto.production.conf)
   - Topic ACLs: [`infrastructure/mosquitto/acl.conf`](../infrastructure/mosquitto/acl.conf)
2. Generate password file:
   ```bash
   mosquitto_passwd -c /mosquitto/config/passwords motorguard_gateway
   mosquitto_passwd /mosquitto/config/passwords motorguard_simulator
   mosquitto_passwd /mosquitto/config/passwords esp32_node_001
   ```
3. Mount Let's Encrypt certificates to `/mosquitto/certs/`:
   - `server.crt` -> `fullchain.pem`
   - `server.key` -> `privkey.pem`
4. Expose port `8883` on your cloud firewall.

---

## 4. Verification & Testing

### Test 1: Verify Configuration Guardrails
```powershell
python -m pytest tests/unit/test_config.py -v
```

### Test 2: Test MQTTS TLS Client Context
```powershell
python -m pytest tests/unit/test_mqtt_tls.py -v
```

### Test 3: Run Cloud Simulator Test
```powershell
$env:MQTT_BROKER_HOST = "cluster-xyz.s1.eu.hivemq.cloud"
$env:MQTT_BROKER_PORT = "8883"
$env:MQTT_USERNAME    = "motorguard_simulator"
$env:MQTT_PASSWORD    = "YourSimulatorPassword!"
$env:MQTT_USE_TLS     = "true"

python simulator/simulator.py
```
Observe published messages in the terminal and verify they appear in the cloud SCADA dashboard.

# MotorGuard — MQTT Topic & Messaging Specification

## 1. Topic Hierarchy & Architecture

All messaging uses a structured, versioned topic namespace under the root identifier `motorguard/v1/`:

```text
motorguard/v1/
├── {device_id}/
│   ├── telemetry    (QoS 1, Unretained)  - Sensor readings & inference frames
│   ├── status       (QoS 1, Retained)    - Device lifecycle (online, offline, degraded)
│   ├── heartbeat    (QoS 0, Unretained)  - Periodic keep-alive ping
│   ├── command      (QoS 1, Unretained)  - Gateway-to-device remote control
│   └── alerts       (QoS 1, Unretained)  - Edge-triggered emergency safety trips
```

---

## 2. Topic Specifications

### 2.1 Telemetry (`motorguard/v1/{device_id}/telemetry`)
- **Producer**: Physical ESP32 nodes or the Virtual Motor Simulator.
- **Consumer**: FastAPI MQTT Ingestion Worker.
- **Frequency**: Nominal 1.0 Hz (every 1000 ms).
- **QoS Level**: **1 (At-Least-Once)**.
- **Retained**: `false`.
- **Payload**: Full JSON payload defined in `docs/telemetry-contract.md`.

### 2.2 Device Status & LWT (`motorguard/v1/{device_id}/status`)
- **Producer**: ESP32 client connection handler & Mosquitto broker LWT mechanism.
- **Consumer**: FastAPI Ingestion Worker & Dashboard presence monitor.
- **QoS Level**: **1 (At-Least-Once)**.
- **Retained**: **`true`** (Ensures newly connected dashboard users immediately receive current state without waiting for a heartbeat).
- **Payload Schema**:
```json
{
  "device_id": "esp32-node-001",
  "motor_id": "mtr-775-001",
  "status": "online",
  "firmware_version": "1.0.1",
  "ip_address": "192.168.1.145",
  "timestamp": "2026-10-09T13:15:00.000Z",
  "reason": "boot"
}
```

#### Last Will and Testament (LWT) Configuration
When initiating the MQTT connection, each ESP32 registers the following LWT with the Mosquitto broker:
- **LWT Topic**: `motorguard/v1/{device_id}/status`
- **LWT QoS**: `1`
- **LWT Retain**: `true`
- **LWT Payload**:
```json
{
  "device_id": "esp32-node-001",
  "status": "offline",
  "timestamp": "2026-10-09T13:15:45.000Z",
  "reason": "unexpected_disconnect"
}
```
If the ESP32 loses power or Wi-Fi drops without an explicit graceful disconnect, Mosquitto automatically dispatches this payload to all subscribers, immediately marking the device as offline.

### 2.3 Heartbeat (`motorguard/v1/{device_id}/heartbeat`)
- **Producer**: Physical ESP32 nodes.
- **Frequency**: Every 10 seconds.
- **QoS Level**: **0 (At-Most-Once)** (Lightweight, low-overhead).
- **Retained**: `false`.
- **Payload Schema**:
```json
{
  "device_id": "esp32-node-001",
  "seq": 104,
  "uptime_seconds": 1040,
  "free_heap_bytes": 184512,
  "wifi_rssi_dbm": -63,
  "timestamp": "2026-10-09T13:15:30.000Z"
}
```
**Stale Evaluation**: The FastAPI backend runs a background check every 5 seconds. If no telemetry or heartbeat is received from an active device for $> 15$ seconds, the device state transitions to `"stale"`. After $> 35$ seconds, it transitions to `"offline"`.

### 2.4 Downstream Commands (`motorguard/v1/{device_id}/command`)
- **Producer**: FastAPI Backend.
- **Consumer**: Physical ESP32 or Simulator.
- **QoS Level**: **1 (At-Least-Once)**.
- **Retained**: `false`.
- **Payload Schema**:
```json
{
  "command_id": "cmd-48912-ab7",
  "action": "CALIBRATE_CURRENT_ZERO",
  "parameters": {
    "samples": 1000
  },
  "issued_by": "technician_1",
  "timestamp": "2026-10-09T13:16:00.000Z"
}
```

---

## 3. Delivery Guarantees & Deduplication

### Why MQTT is Not Exactly-Once
MQTT provides three Quality of Service (QoS) levels:
- QoS 0: At most once (messages may be lost).
- QoS 1: At least once (messages guaranteed to arrive, but duplicates may occur due to ACK timeouts).
- QoS 2: Exactly once (highest protocol overhead, four-step handshake, still vulnerable to application-level duplicate publishes upon reconnection).

In noisy industrial RF environments (such as motor EMI interference with Wi-Fi), QoS 1 is optimal for throughput and battery/compute efficiency. However, if an ESP32 sends a packet and its network socket drops before receiving the broker's `PUBACK`, the ESP32 will reconnect and re-publish the same packet.

### Consumer Idempotency Strategy
MotorGuard solves duplicate delivery at the **database ingestion layer**:
1. Every packet generated at the edge includes an immutable `event_id` (UUIDv4).
2. The FastAPI ingestion worker inserts documents using MongoDB's unique index:
   ```python
   # Unique compound index on collection:
   db.telemetry.create_index([("device_id", 1), ("event_id", 1)], unique=True)
   ```
3. If a duplicate packet arrives:
   ```python
   try:
       await db.telemetry.insert_one(payload.dict())
       await broadcast_to_websockets(payload)
   except DuplicateKeyError:
       logger.info(f"Ignored duplicate event {payload.event_id} from {payload.device_id}")
   ```
This guarantees strict idempotency without requiring heavyweight QoS 2 handshakes.

---

## 4. Edge Reconnection & Backoff Policy

When an ESP32 or simulator loses connection to the Mosquitto broker, it must **never** reconnect in a tight loop, which would flood the local gateway during network recovery.

### Reconnection Backoff Formula
```text
Delay = min(MAX_DELAY, INITIAL_DELAY * (2 ^ attempt)) + Jitter
```
- `INITIAL_DELAY`: 1.0 second
- `MAX_DELAY`: 60.0 seconds
- `Jitter`: Random integer between $0$ and $2000$ milliseconds
- `MAX_ATTEMPTS_BEFORE_DEGRADED`: After 5 consecutive failed reconnection attempts, the firmware logs an on-chassis error code and prepares safe shutdown defaults.

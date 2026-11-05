# Software Quality Assurance & Audit Report: Backend API

**Target Project:** `c:\Users\gopes\Downloads\project\backend_example`  
**Auditor:** AGENT 3 — BACKEND/API QA AGENT  
**Audit Date:** 2026-09-30  
**Target Framework:** FastAPI 0.141.1, Starlette 1.7.0, Pydantic 2.13.5, Motor 3.7.1, Paho-MQTT 2.1.0, Python 3.12.10  
**Mode:** READ-ONLY Codebase Audit & Empirical Test Execution  

---

## 1. Executive Summary

An exhaustive quality assurance inspection and runtime test suite were performed on the FastAPI backend in `backend_example/`. The audit encompassed application lifecycle, all 10 REST and WebSocket endpoints, Pydantic schema validation, status codes, MongoDB BSON serialization, MQTT asynchronous bridge mechanics, concurrency/thread safety, and security/CORS configurations.

### Key Audit Findings Summary
- **Total Endpoints Audited:** 10 (9 REST, 1 WebSocket)
- **Critical Severity Vulnerabilities:** 3 (BSON `ObjectId` 500 Crash, Critical CORS Wildcard Credential Reflection, Unauthenticated Motor Control)
- **High Severity Defects:** 3 (Orphaned Schema & Missing Request Validation causing unhandled 500 crashes, Motor Control Query Parameter Misconfiguration & False Positive Delivery)
- **Medium Severity Defects:** 2 (WebSocket Dead Connection Leak, Unbounded In-Memory Alerts Growth)
- **Low Severity / Hygiene Issues:** 2 (Deprecated `@app.on_event` Lifecycle Handlers, Missing Upper Bound on Pagination)

---

## 2. Test Execution & Evidence Matrix

The table below documents empirical test executions performed against the application using `httpx` ASGI transport, Starlette test client, and live MongoDB instance.

| # | Endpoint Tested | Input Condition | Expected Status / Behavior | Actual Status / Behavior | Verdict | Severity | Recommendation |
|---|---|---|---|---|---|---|---|
| 1 | `GET /` | Valid Request (`GET http://test/`) | HTTP 200 with service health info and MQTT status | HTTP 200: `{"status": "online", "service": "...", "mqtt_status": "connecting", "active_clients": 0}` | **PASS** | Low | When MQTT is disconnected, report `"offline"` instead of indefinite `"connecting"`. |
| 2 | `GET /api/system/status` | Valid Request | HTTP 200 with real-time status of FastAPI, MongoDB ping, MQTT | HTTP 200: `{"fastapi": "online", "mongodb": "online", "mqtt": "offline", ...}` | **PASS** | Info | Working as intended; ping check correctly detects live DB state. |
| 3 | `POST /api/telemetry` | Valid Payload: `{"motor_id": "MTR-001", "vibration_mm_s": 2.5, "temperature_c": 45.0, "current_a": 1.2, "anomaly_score": 0.05}` | HTTP 200 with ML enrichment, health score, DB persistence flag | HTTP 200: `{"status": "success", "health_score": 82.2, "persisted_to_mongodb": true}` | **PASS** | High | Enforce schema validation model instead of raw `Dict[str, Any]`. |
| 4 | `POST /api/telemetry` | Missing fields / Empty JSON `{}` | HTTP 422 Unprocessable Entity (Missing required telemetry fields) | HTTP 200: Calculates default health score `99.0%` and inserts empty/bogus telemetry record into DB | **FAIL** | High | Reject empty or missing fields with HTTP 422 via Pydantic model. |
| 5 | `POST /api/telemetry` | Invalid data types: `{"motor_id": "MTR-001", "vibration_mm_s": "not-a-number"}` | HTTP 422 Unprocessable Entity with validation error details | **HTTP 500 Internal Server Error** (`ValueError: could not convert string to float: 'not-a-number'`) | **FAIL** | High | Replace `payload: Dict[str, Any]` with Pydantic schema `SensorDataTestPayload` so FastAPI automatically rejects invalid types with HTTP 422. |
| 6 | `POST /api/test/sensor-data` | Valid Payload: `{"motor_id": "MTR-001", "vibration_mm_s": 3.2, ...}` | HTTP 200 with enriched telemetry, alerts list, DB persistence | HTTP 200: `{"status": "success", "mode": "test_pipeline", "enriched_telemetry": {...}}` | **PASS** | High | Enforce Pydantic schema validation. |
| 7 | `POST /api/test/sensor-data` | Invalid data types: `{"vibration_mm_s": 1.0, "current_a": "invalid"}` | HTTP 422 Unprocessable Entity | **HTTP 500 Internal Server Error** (`ValueError: could not convert string to float: 'invalid'`) | **FAIL** | High | Enforce Pydantic schema validation. |
| 8 | `GET /api/motors/{motor_id}/live` | Valid existing cached motor (`MTR-001`) | HTTP 200 with cached reading dict | HTTP 200 with full cached telemetry object | **PASS** | Info | Working as intended. |
| 9 | `GET /api/motors/{motor_id}/live` | Non-existent motor (`NON_EXISTENT`) | HTTP 404 Not Found | HTTP 200: `{"message": "No live reading received yet from ESP32", "motor_id": "NON_EXISTENT"}` | **FAIL** | Medium | Return HTTP 404 with standard HTTPException when motor cache has no record. |
| 10 | `GET /api/motors/{motor_id}/history` | Valid request with `limit=5` | HTTP 200 with array of telemetry records without `_id` | HTTP 200 with 5 records sorted in chronological order (`_id` excluded) | **PASS** | Low | Add query validation: `limit: int = Query(default=100, ge=1, le=1000)`. |
| 11 | `GET /api/alerts` | Valid request with `limit=5` | HTTP 200 with array of recent alerts without `_id` | HTTP 200 with recent alert documents | **PASS** | Medium | Cap in-memory fallback list to prevent memory leak. |
| 12 | `GET /api/users` | Valid request on seeded users (custom string `_id`) | HTTP 200 with array of user objects | HTTP 200 with 6 user records | **PASS** | Critical | See Test 13. |
| 13 | `GET /api/users` | Collection contains document with standard MongoDB `ObjectId` | HTTP 200 with serialized `id` string | **CRASH / HTTP 500 Internal Server Error**: `TypeError: Object of type ObjectId is not JSON serializable` | **FAIL** | Critical | Use projection `{"_id": 0}` or serialize `_id` via `str(doc["_id"])` or Pydantic model. |
| 14 | `POST /api/motors/{motor_id}/control` | Standard POST with JSON Body: `{"command": "EMERGENCY_SHUTDOWN"}` | HTTP 200 acknowledging command dispatch | **HTTP 422 Unprocessable Entity**: `{"detail": [{"loc": ["query", "command"], "msg": "Field required"}]}` | **FAIL** | High | Change endpoint signature to use a Pydantic Request Body (`class MotorControlRequest(BaseModel): command: str`). |
| 15 | `POST /api/motors/{motor_id}/control` | Query Parameter: `?command=EMERGENCY_SHUTDOWN` (MQTT broker offline) | HTTP 503 or warning that MQTT broker is unavailable | HTTP 200: `{"status": "command_published"}` (False Positive confirmation) | **FAIL** | High | Verify `mqtt_client.is_connected()` before publishing; return HTTP 503 if broker is offline. |
| 16 | `WS /ws/live` | WebSocket connection & telemetry broadcast | Client connects, receives live JSON push on new telemetry, handles client ping | Connection accepted, broadcast received, client ping handled | **PASS** | Medium | Clean up dead connections in `broadcast_ws` exception block. |
| 17 | `OPTIONS /api/system/status` | Preflight CORS request with arbitrary origin (`Origin: http://evil-attacker.com`) | Safe CORS policy rejecting unapproved cross-origin credentials | `access-control-allow-origin: http://evil-attacker.com`, `access-control-allow-credentials: true` | **FAIL** | Critical | Replace `allow_origins=["*"]` with an explicit list of allowed domains, or set `allow_credentials=False`. |

---

## 3. In-Depth Technical Vulnerability & Defect Analysis

### 3.1. MongoDB BSON `ObjectId` Serialization Crash in `GET /api/users`
- **Location:** [`backend_example/main.py` lines 390–400](file:///c:/Users/gopes/Downloads/project/backend_example/main.py#L390-L400)
- **Observed Behavior:**
  ```python
  @app.get("/api/users", tags=["Users"])
  async def get_all_users():
      db = get_db()
      if db is not None:
          try:
              cursor = db["users"].find({})
              users = await cursor.to_list(length=100)
              return users  # <--- CRASHES if any document has ObjectId
  ```
- **Runtime Evidence:**
  When a document was inserted via standard MongoDB driver methods (`insert_one({"name": "Test", "role": "engineer"})`), MongoDB auto-generated a BSON `ObjectId`. Calling `GET /api/users` failed immediately with:
  `TypeError: 'ObjectId' object is not iterable` / `vars() argument must have __dict__ attribute` inside Starlette's `jsonable_encoder`.
- **Contrast with other endpoints:** Both `get_motor_history` (line 367) and `get_alerts` (line 381) correctly applied projection `{"_id": 0}`. The `get_all_users` endpoint omitted this projection.
- **Severity:** **CRITICAL**
- **Remediation:**
  Apply projection `{"_id": 0}` or transform `doc["_id"] = str(doc["_id"])`, or declare a Pydantic response model with `field_serializer`.

---

### 3.2. Orphaned Pydantic Schema & Total Absence of Request Validation
- **Location:** [`backend_example/main.py` lines 55–61, 319, 336](file:///c:/Users/gopes/Downloads/project/backend_example/main.py#L55-L61)
- **Root Cause:**
  Lines 55–61 define `SensorDataTestPayload(BaseModel)` with field types, descriptions, and defaults:
  ```python
  class SensorDataTestPayload(BaseModel):
      motor_id: str = Field(default="MTR-001", description="Motor ID, e.g. MTR-001")
      vibration_mm_s: float = Field(..., description="Vibration RMS velocity in mm/s")
      temperature_c: float = Field(..., description="Motor temperature in °C")
      current_a: float = Field(..., description="Motor current in Amperes")
      anomaly_score: float = Field(default=0.0, description="Edge Impulse TinyML anomaly score (0.0 - 1.0)")
  ```
  However, both ingestion endpoints ignore this model:
  ```python
  @app.post("/api/telemetry")
  async def receive_telemetry(payload: Dict[str, Any]):  # Unvalidated raw dict!

  @app.post("/api/test/sensor-data")
  async def test_sensor_data(payload: Dict[str, Any]):   # Unvalidated raw dict!
  ```
- **Consequences:**
  1. Passing invalid data types (`{"vibration_mm_s": "not-a-number"}`) causes `process_telemetry_payload` to crash at line 173 with an unhandled Python `ValueError`, returning HTTP 500 instead of HTTP 422.
  2. Passing an empty payload `{}` silently passes, defaults sensor parameters to `0.0`, calculates an erroneous health score of `99.0%`, and persists corrupt data to MongoDB.
  3. Arbitrary unauthorized keys can be injected into database storage unchecked.
- **Severity:** **HIGH**
- **Remediation:**
  Update signatures to `async def receive_telemetry(payload: SensorDataTestPayload):` and convert `payload.model_dump()` to dict for internal pipeline processing.

---

### 3.3. REST Anti-Pattern & False-Positive Execution in `POST /api/motors/{motor_id}/control`
- **Location:** [`backend_example/main.py` lines 402–409](file:///c:/Users/gopes/Downloads/project/backend_example/main.py#L402-L409)
- **Root Cause:**
  ```python
  @app.post("/api/motors/{motor_id}/control", tags=["Motors"])
  def send_motor_control(motor_id: str, command: str):
  ```
  Because `command: str` has no Pydantic body or `Body(...)` wrapper, FastAPI maps it to a **Query Parameter** (`?command=...`).
- **Consequences:**
  1. Any frontend, script, or integration sending standard JSON body `{"command": "EMERGENCY_SHUTDOWN"}` receives `HTTP 422 Unprocessable Entity` (`missing query param command`).
  2. The endpoint calls `mqtt_client.publish(topic, payload)` without verifying whether the MQTT broker is connected. During our test run, MQTT was confirmed **offline**, yet the API responded:
     ```json
     {"status": "command_published", "topic": "motors/MTR-001/cmd", "command": "EMERGENCY_SHUTDOWN"}
     ```
     In an industrial predictive maintenance system, giving operators a false positive that an emergency shutdown command was dispatched when the communication broker is disconnected presents a severe operational safety hazard.
- **Severity:** **HIGH**
- **Remediation:**
  1. Use a Pydantic model for the request body:
     ```python
     class MotorCommandRequest(BaseModel):
         command: str = Field(..., description="Action command, e.g. EMERGENCY_SHUTDOWN, RESET_RELAY")
     ```
  2. Check `if not mqtt_client.is_connected(): raise HTTPException(status_code=503, detail="MQTT broker disconnected")`.

---

### 3.4. Insecure CORS Configuration (Wildcard Origin with Credential Sharing)
- **Location:** [`backend_example/main.py` lines 34–40](file:///c:/Users/gopes/Downloads/project/backend_example/main.py#L34-L40)
- **Code:**
  ```python
  app.add_middleware(
      CORSMiddleware,
      allow_origins=["*"],
      allow_credentials=True,
      allow_methods=["*"],
      allow_headers=["*"],
  )
  ```
- **Observed Behavior:**
  Sending an `OPTIONS` preflight request with `Origin: http://evil-attacker.com` produced:
  ```http
  Access-Control-Allow-Origin: http://evil-attacker.com
  Access-Control-Allow-Credentials: true
  ```
- **Security Impact:**
  Modern browsers disallow `Access-Control-Allow-Origin: *` when `Access-Control-Allow-Credentials: true`. Starlette dynamically reflects the incoming `Origin` header into `Access-Control-Allow-Origin` when `allow_credentials=True`. This completely bypasses the Same-Origin Policy, enabling any third-party malicious website visited by an authenticated user to make authenticated requests, read telemetry, or issue motor commands.
- **Severity:** **CRITICAL**
- **Remediation:**
  Specify exact allowed origins (e.g. `allow_origins=["http://localhost:3000", "http://localhost:5173"]`) or set `allow_credentials=False` if cookie/authorization headers are not used across origins.

---

### 3.5. Complete Lack of Authentication and Authorization
- **Location:** All routes in [`backend_example/main.py`](file:///c:/Users/gopes/Downloads/project/backend_example/main.py)
- **Observation:**
  - `GET /api/users` returns all user credentials, names, emails, roles, and departments to unauthenticated anonymous requests.
  - `POST /api/motors/{motor_id}/control` allows any unauthenticated client on the network to issue hardware commands to industrial motors.
  - `POST /api/telemetry` allows unauthenticated clients to poison database records and trigger false emergency alerts.
- **Severity:** **CRITICAL**
- **Remediation:**
  Implement JWT or API Key authentication dependencies (`Depends(verify_token)` or `Depends(get_current_user)`). Enforce role-based access control (RBAC), requiring `role == "admin"` or `role == "engineer"` for control actions.

---

### 3.6. Concurrency, Thread Safety & Lifecycle Architecture
- **Location:** [`backend_example/main.py` lines 52, 235–280](file:///c:/Users/gopes/Downloads/project/backend_example/main.py#L235-L280)
- **Findings:**
  1. **Unhandled Future in MQTT Thread Bridge:**
     In `on_mqtt_message`:
     ```python
     asyncio.run_coroutine_threadsafe(process_telemetry_payload(data), server_loop)
     ```
     This method submits `process_telemetry_payload(data)` to the event loop and returns a `concurrent.futures.Future`. The future is ignored. If an unhandled exception occurs inside `process_telemetry_payload` (e.g., malformed data or database connection timeout), the exception is never inspected or logged.
  2. **Event Loop Lifespan & Shutdown Cleanup:**
     `server_loop` is set during `startup_event()`, but is never set to `None` in `shutdown_event()`. If the server is restarting or stopping while MQTT messages arrive, calling `run_coroutine_threadsafe` on a stopped loop raises an unhandled `RuntimeError: Event loop is closed`.
  3. **Event Loop Binding in Motor (Database):**
     During testing with AnyIO / Starlette TestClient, `AsyncIOMotorClient` threw:
     `Task got Future attached to a different loop`
     Motor client instances must be initialized and accessed within the active running asyncio loop.
  4. **Deprecated Lifecycle Handlers:**
     FastAPI has deprecated `@app.on_event("startup")` and `@app.on_event("shutdown")` in favor of ASGI `lifespan` context managers.

---

### 3.7. In-Memory Resource Leaks
- **Location:** [`backend_example/main.py` lines 49–51, 63–70, 220–222](file:///c:/Users/gopes/Downloads/project/backend_example/main.py#L49-L70)
- **Findings:**
  1. **WebSocket Client Leak in `broadcast_ws`:**
     ```python
     async def broadcast_ws(payload: dict):
         for connection in list(active_connections):
             try:
                 await connection.send_text(json.dumps(payload))
             except Exception as e:
                 logger.warning(f"Error sending to WebSocket client: {e}")
     ```
     When a client disconnects abruptly without sending a formal close frame, `connection.send_text()` raises an exception. However, `broadcast_ws` merely logs a warning and leaves the dead connection in `active_connections`. Over time, `active_connections` accumulates stale sockets.
  2. **Unbounded `active_alerts` Growth:**
     Line 221: `active_alerts.append(a)` appends every new alert into a global in-memory list without any eviction policy or size limit. Under continuous motor operation with vibration alerts, memory consumption will increase linearly.
- **Severity:** **MEDIUM**
- **Remediation:**
  1. Remove dead connections in `broadcast_ws`:
     ```python
     except Exception as e:
         active_connections.remove(connection)
     ```
  2. Use a bounded collection like `collections.deque(maxlen=1000)` for `active_alerts`.

---

## 4. End-to-End Status Code Analysis

| Status Code | Current Utilization in API | Evaluation |
|---|---|---|
| **200 OK** | Used for all successful GET/POST/OPTIONS requests. Also incorrectly returned for non-existent motors (`GET /api/motors/NON_EXISTENT/live`) and when publishing commands over disconnected MQTT. | Overused for non-error fallbacks where 404 or 503 is semantically appropriate. |
| **400 Bad Request** | Never raised anywhere in the codebase. | Should be raised for malformed client payloads or invalid parameter configurations. |
| **422 Unprocessable Entity** | Triggered only by FastAPI's parameter validator (e.g. when calling `POST /api/motors/{motor_id}/control` with a JSON body instead of query params). | NOT triggered for invalid sensor payloads because endpoints accept raw `Dict[str, Any]`. |
| **500 Internal Server Error** | Triggered on invalid sensor payload types (`ValueError: could not convert string to float`) and on `GET /api/users` when MongoDB contains documents with native `ObjectId`. | Indicates inadequate input validation and missing BSON serialization handling. |
| **503 Service Unavailable** | Never returned. | Should be returned by control endpoints when MQTT broker is offline. |

---

## 5. Offline Resiliency Evaluation

### 5.1. MongoDB Offline Behavior
- When MongoDB is unreachable:
  - `connect_to_mongo()` catches `ConnectionFailure` and logs: `"Running without DB persistence"`.
  - `GET /api/system/status` executes `db.command("ping")` within `try...except` and accurately reports `"mongodb": "offline"`.
  - `POST /api/telemetry` processes ML health scores in memory, skips DB insert gracefully, and returns `"persisted_to_mongodb": false`.
  - `GET /api/alerts` falls back to the in-memory `active_alerts` cache.
  - `GET /api/motors/{motor_id}/history` and `GET /api/users` safely return empty lists `[]`.
- **Verdict:** **EXCELLENT**. Database offline resilience is well-handled without application crashes.

### 5.2. MQTT Broker Offline Behavior
- When MQTT Broker (port 1883) is unreachable:
  - Startup uses `connect_async(MQTT_BROKER, MQTT_PORT, 60)`, allowing FastAPI to boot in standalone mode.
  - `GET /api/system/status` accurately reports `"mqtt": "offline"`.
  - **Defect:** `POST /api/motors/{motor_id}/control` does not check connection state and returns `"status": "command_published"`, misleading callers.
- **Verdict:** **PARTIAL**. Telemetry ingestion works offline via HTTP, but motor control fails silently.

---

## 6. Actionable Remediation Plan & Recommendations

### Priority 1: Critical Security & Crash Fixes
1. **Fix BSON Serialization in `GET /api/users`:**
   Add projection `{"_id": 0}` in `db["users"].find({}, {"_id": 0})` or map `_id` to string.
2. **Restrict CORS Origins:**
   Replace `allow_origins=["*"]` with an explicit whitelist of dashboard URLs (e.g. `http://localhost:5173`, `http://localhost:3000`).
3. **Implement Authentication:**
   Add security middleware or token verification dependencies (`OAuth2PasswordBearer` / API Key) to protect control and user data routes.

### Priority 2: High Stability & API Contract Fixes
4. **Enforce `SensorDataTestPayload` on Ingestion Endpoints:**
   Replace `payload: Dict[str, Any]` in `receive_telemetry` and `test_sensor_data` with `payload: SensorDataTestPayload`.
5. **Redesign `POST /api/motors/{motor_id}/control` to Accept Request Body:**
   Define a `MotorCommandRequest` Pydantic model and accept it as request body.
6. **Add MQTT Connection Verification in Motor Control:**
   Check `mqtt_client.is_connected()` and return HTTP 503 if disconnected.

### Priority 3: Concurrency, Memory & Lifecycle Improvements
7. **Handle MQTT Thread Future Exceptions:**
   Attach a done-callback to the future returned by `asyncio.run_coroutine_threadsafe` to log any pipeline failures.
8. **Prune Dead WebSockets in `broadcast_ws`:**
   Remove disconnected sockets from `active_connections` upon encountering send errors.
9. **Cap `active_alerts` Buffer:**
   Use a `collections.deque(maxlen=500)` to prevent unbounded memory growth.
10. **Migrate to Modern ASGI Lifespan:**
    Replace `@app.on_event("startup")` and `@app.on_event("shutdown")` with `@asynccontextmanager async def lifespan(app: FastAPI):`.

---
*Report generated by AGENT 3 — BACKEND/API QA AGENT. Inspection concluded cleanly in Read-Only mode.*

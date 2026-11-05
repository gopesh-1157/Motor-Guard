# DEFENSIVE SECURITY & RBAC AUDIT REPORT
**Project:** Motor-Guard (Predictive Maintenance & IoT SCADA System)  
**Target Directory:** `c:\Users\gopes\Downloads\project`  
**Audit Role:** AGENT 7 — Security & RBAC Auditor  
**Date:** September 30, 2026  
**Status:** COMPLETE / CRITICAL DEFENSIVE FINDINGS  

---

## 1. Executive Summary & Security Posture Assessment

A comprehensive defensive source-code security audit was executed across the backend API (`FastAPI`), database interface (`Motor/MongoDB`), frontend web application (`React 19 / Vite`), and edge IoT firmware (`ESP32 C++/Arduino`).

### Overall System Posture: **CRITICAL RISK**
The current architecture exhibits zero server-side authentication or authorization controls, relies entirely on client-side state manipulation for access control, exposes sensitive operational credentials and plant Wi-Fi credentials in plaintext, leaves physical industrial actuators open to unauthenticated network manipulation via MQTT and REST endpoints, and has severe network misconfigurations.

```
       ┌─────────────────────────────── ATTACK SURFACE ───────────────────────────────┐
       │                                                                               │
[ Attacker / Rogue Client ]                                                           │
       │                                                                               │
       ├──── 1. Unauthenticated HTTP POST ───► /api/motors/{id}/control ─────────────┐ │
       │    (No Auth, No RBAC, No Rate Limit)                                        │ │
       │                                                                             ▼ │
       ├──── 2. Direct MQTT TCP (1883) ──────► motors/{id}/cmd ──────────► [ Industrial Motor ]
       │    (No TLS, No Password, No MAC)                                  (Physical Actuator)
       │                                                                               │
       ├──── 3. LocalStorage Tampering ──────► role: "admin" ────────────► [ Full Admin UI ]
       │    (Bypasses ProtectedRoute.jsx)                                                      │
       │                                                                               │
       ├──── 4. Unauthenticated REST GET ────► /api/users ───────────────► [ MongoDB Users ]
       │    (Dumps All User Accounts)                                                          │
       │                                                                               │
       └──── 5. Plaintext Source Hardcoding ─► SSID: "Gopesh " ──────────► [ Internal LAN ]
            (Firmware .ino in Git)             Pass: "gopesh1157"                              │
```

---

## 2. Vulnerability Classification Matrix

| Vulnerability ID | Category | Component | Severity | CVSS v3.1 | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **SEC-01** | Authentication Bypass | Backend REST API | **CRITICAL** | 9.8 | Unauthenticated endpoints across all routers |
| **SEC-02** | Broken Access Control | Backend Actuation API | **CRITICAL** | 9.8 | Arbitrary motor shutdown/control without RBAC |
| **SEC-03** | Secret Exposure | IoT Firmware | **HIGH** | 7.5 | Hardcoded Wi-Fi SSID and WPA2 passphrase |
| **SEC-04** | Client-Side Security | Frontend React App | **HIGH** | 8.1 | Role escalation via `localStorage` modification |
| **SEC-05** | Credential Exposure | Frontend & Seed Scripts | **HIGH** | 7.5 | Universal plaintext default passwords (`password123`) |
| **SEC-06** | Information Disclosure | Backend API | **MEDIUM** | 6.5 | Sensitive user data exposed in `/api/users` |
| **SEC-07** | Network Misconfig | Backend API (CORS) | **MEDIUM** | 6.5 | `allow_origins=["*"]` with `allow_credentials=True` |
| **SEC-08** | Insecure Transport | IoT / MQTT Broker | **HIGH** | 8.2 | Unencrypted, unauthenticated MQTT on TCP 1883 |
| **SEC-09** | DoS / Injection | Backend API | **MEDIUM** | 5.3 | Unbounded input queries, missing rate limiting |

---

## 3. Detailed Audit Findings

### 3.1 Authentication

#### 3.1.1 Backend API Authentication (Zero-Trust Violation)
- **Affected File:** `c:\Users\gopes\Downloads\project\backend_example\main.py`
- **Observed Code:**
  ```python
  @app.post("/api/telemetry", tags=["Telemetry"])
  async def receive_telemetry(payload: Dict[str, Any]): ...

  @app.get("/api/users", tags=["Users"])
  async def get_all_users(): ...

  @app.post("/api/motors/{motor_id}/control", tags=["Motors"])
  def send_motor_control(motor_id: str, command: str): ...
  ```
- **Finding:**
  The FastAPI application specifies **no authentication mechanisms whatsoever**. There are no security dependencies (`Depends()`), no OAuth2 password bearer schemes, no JWT token decoders, no API key headers, and no session cookies.
- **Defensive Impact:**
  Any network endpoint that can route TCP traffic to port `8000` can execute commands, simulate false sensor telemetry, query historical trends, and dump user lists without presenting any identity credentials.

#### 3.1.2 Frontend Authentication & Password Handling
- **Affected Files:**
  - `c:\Users\gopes\Downloads\project\motor-dashboard\src\pages\Login.jsx`
  - `c:\Users\gopes\Downloads\project\motor-dashboard\src\context\AppContext.jsx`
  - `c:\Users\gopes\Downloads\project\motor-dashboard\src\data\mockData.js`
- **Observed Code:**
  ```javascript
  // AppContext.jsx
  const login = (email, password) => {
    const matched = usersList.find(
      u => u.email.toLowerCase() === email.trim().toLowerCase() && (!password || u.password === password)
    );
    if (matched) {
      setCurrentUser(matched);
      localStorage.setItem('motor_health_user', JSON.stringify(matched));
      return true;
    }
    return false;
  };
  ```
- **Findings:**
  1. **Passwordless Authentication Flaw:** The condition `(!password || u.password === password)` allows authentication if the caller passes an empty/falsy password string, granting full session access to any user account simply by knowing their email address.
  2. **Plaintext Credential Matching:** Passwords are stored in client-side state and compared directly using standard string equality without cryptographic hashing (no `Argon2id`, `bcrypt`, or `PBKDF2`).
  3. **Insecure Session Storage:** The complete user object including role, email, and plaintext password is saved into browser `localStorage` under `motor_health_user` and `motor_health_users_list`.
  4. **Lack of Token Lifecycle:** There are no cryptographic tokens, no expiration timestamps (`exp`), no revocation lists, and no refresh tokens.
  5. **Insecure Default State:** In `AppContext.jsx` lines 26–33:
     ```javascript
     const [currentUser, setCurrentUser] = useState(() => {
       try {
         const saved = localStorage.getItem('motor_health_user');
         return saved ? JSON.parse(saved) : users[0];
       } catch {
         return users[0];
       }
     });
     ```
     If a user visits the application with an empty browser cache or incognito mode, the system defaults `currentUser` directly to `users[0]`, which is the **Admin User** (`role: 'admin'`).

---

### 3.2 Authorization & Role-Based Access Control (RBAC)

#### 3.2.1 Client-Side Authorization Bypass
- **Affected File:** `c:\Users\gopes\Downloads\project\motor-dashboard\src\components\ProtectedRoute.jsx`
- **Observed Code:**
  ```javascript
  export default function ProtectedRoute({ allowedRoles }) {
    const { currentUser } = useApp();

    if (!currentUser) {
      return <Navigate to="/login" replace />;
    }

    if (allowedRoles && !allowedRoles.includes(currentUser.role)) {
      return ( /* Render Access Restricted message */ );
    }

    return <Outlet />;
  }
  ```
- **Finding:**
  Authorization logic is purely cosmetic and enforced exclusively inside the browser runtime.
- **Exploitation / Bypass Demonstration (Defensive Analysis):**
  A user authenticated as an `operator` can open browser Developer Tools (Console) and run:
  ```javascript
  localStorage.setItem('motor_health_user', JSON.stringify({
    ...JSON.parse(localStorage.getItem('motor_health_user')),
    role: 'admin'
  }));
  location.reload();
  ```
  Upon page reload, `AppContext.jsx` loads the modified role from `localStorage`, instantly bypassing `ProtectedRoute` and granting unrestricted access to `/devices`, `/users`, and `/settings`.

#### 3.2.2 Complete Absence of Server-Side RBAC
- **Affected File:** `c:\Users\gopes\Downloads\project\backend_example\main.py`
- **Observed Code:**
  ```python
  @app.post("/api/motors/{motor_id}/control", tags=["Motors"])
  def send_motor_control(motor_id: str, command: str):
      topic = f"motors/{motor_id}/cmd"
      payload = json.dumps({"command": command, "issued_at": datetime.now(timezone.utc).isoformat()})
      mqtt_client.publish(topic, payload)
      return {"status": "command_published", "topic": topic, "command": command}
  ```
- **Finding:**
  The server-side endpoint accepts motor control commands (`EMERGENCY_SHUTDOWN`, `RESET_RELAY`) without verifying whether the request sender possesses `admin` privileges or even a valid session.
- **Defensive Impact:**
  Physical machinery can be stopped or reset by any unauthenticated actor on the network, creating operational and physical safety hazards.

---

### 3.3 Credential and Secret Exposure

#### 3.3.1 Hardcoded Wi-Fi Credentials in Firmware Source
- **Affected Files:**
  - `c:\Users\gopes\Downloads\project\firmware\esp32_motor_node.ino` (lines 16–21)
  - `c:\Users\gopes\Downloads\project\firmware\esp32_motor_node\esp32_motor_node.ino` (lines 16–21)
- **Observed Code:**
  ```cpp
  // ============================================================
  // WI-FI & MQTT CLOUD BACKEND (Layer 3)
  // ============================================================
  const char* WIFI_SSID     = "Gopesh ";
  const char* WIFI_PASSWORD = "gopesh1157";

  // IP of the host/laptop running Mosquitto / FastAPI backend
  const char* MQTT_BROKER   = "172.21.101.208"; 
  const int   MQTT_PORT     = 1883;
  const char* MQTT_TOPIC    = "motors/MTR-001/data";
  ```
- **Finding:**
  Production Wi-Fi SSID (`"Gopesh "`) and WPA2 pre-shared key (`"gopesh1157"`), along with internal staging IP `172.21.101.208`, are committed directly into version control.
- **Defensive Impact:**
  Anyone with read access to the repository obtains direct physical/wireless access to the facility's local area network.

#### 3.3.2 Default Plaintext Passwords in Seed Data & Frontend Mocks
- **Affected Files:**
  - `c:\Users\gopes\Downloads\project\backend_example\seed_users.py`
  - `c:\Users\gopes\Downloads\project\motor-dashboard\src\data\mockData.js` (lines 490–497)
  - `c:\Users\gopes\Downloads\project\motor-dashboard\src\pages\Users.jsx` (lines 37, 53, 81)
- **Observed Code:**
  ```javascript
  // mockData.js
  export const users = [
    { _id: 'USR-001', name: 'Admin User', email: 'admin@motorhealth.io', role: 'admin', password: 'password123', ... },
    { _id: 'USR-002', name: 'Jane Smith', email: 'jane@motorhealth.io', role: 'manager', password: 'password123', ... },
    ...
  ];
  ```
- **Finding:**
  All user roles (Admin, Manager, Technician, Operator) share the identical default password `"password123"`. In `Users.jsx`, any newly created user automatically receives `"password123"`.

#### 3.3.3 Sensitive User Information Leakage via REST
- **Affected File:** `c:\Users\gopes\Downloads\project\backend_example\main.py` (lines 389–400)
- **Observed Code:**
  ```python
  @app.get("/api/users", tags=["Users"])
  async def get_all_users():
      db = get_db()
      if db is not None:
          try:
              cursor = db["users"].find({})
              users = await cursor.to_list(length=100)
              return users
          except Exception as e:
              logger.error(f"Error fetching users from DB: {e}")
      return []
  ```
- **Finding:**
  The query projection does not filter out sensitive fields (such as password hashes, internal IDs, or login history). If passwords or sensitive metadata are stored in MongoDB, this unauthenticated endpoint returns them entirely in the JSON response body.

---

### 3.4 Network and API Security

#### 3.4.1 Insecure CORS Configuration
- **Affected File:** `c:\Users\gopes\Downloads\project\backend_example\main.py` (lines 34–40)
- **Observed Code:**
  ```python
  app.add_middleware(
      CORSMiddleware,
      allow_origins=["*"],
      allow_credentials=True,
      allow_methods=["*"],
      allow_headers=["*"],
  )
  ```
- **Finding:**
  Configuring `allow_origins=["*"]` with `allow_credentials=True` is an invalid and hazardous configuration.
- **Defensive Impact:**
  According to the W3C Cross-Origin Resource Sharing specification and standard browser implementations, wildcard origins with credentials flag is contradictory. If parsed permissively by customized HTTP clients or legacy browsers, it allows malicious third-party websites to forge authenticated requests and read sensitive telemetry or user records.

#### 3.4.2 Unauthenticated WebSocket Endpoint (`/ws/live`)
- **Affected File:** `c:\Users\gopes\Downloads\project\backend_example\main.py` (lines 71–84)
- **Observed Code:**
  ```python
  @app.websocket("/ws/live")
  async def websocket_endpoint(websocket: WebSocket):
      await websocket.accept()
      active_connections.append(websocket)
      try:
          while True:
              data = await websocket.receive_text()
      except WebSocketDisconnect:
          ...
  ```
- **Finding:**
  1. No authentication or authorization token is validated during the WebSocket handshake (`HTTP 101 Switching Protocols`).
  2. Industrial operational data (live motor temperatures, vibration waveforms, anomaly scores, and failure probabilities) are broadcast to any connected client.
  3. No maximum connection limit: An attacker can open thousands of idle WebSocket connections, exhausting server file descriptors and memory.

#### 3.4.3 Insecure MQTT Transport and Authorization
- **Affected Files:**
  - `c:\Users\gopes\Downloads\project\backend_example\main.py` (lines 43–46, 234–270)
  - `c:\Users\gopes\Downloads\project\firmware\esp32_motor_node.ino` (lines 20–25, 230–270)
- **Observed Setup:**
  - Transport: Plain unencrypted TCP (Port 1883). TLS/SSL (Port 8883) is not implemented.
  - Authentication: No username or password credentials configured (`mqttClient.connect(MOTOR_ID)` in firmware; `mqtt.Client()` in backend).
  - Topic Subscription: `motors/+/data` wildcard subscription.
  - Command Channel: `motors/{motor_id}/cmd` has no payload signing or origin validation.
- **Defensive Impact:**
  - **Eavesdropping:** Sensor telemetry and commands travel across the network in cleartext.
  - **Telemetry Spoofing:** Any device connected to the network can publish fake sensor telemetry to `motors/MTR-001/data`, triggering artificial emergency alerts or masking actual critical mechanical failures.
  - **Actuator Hijacking:** An attacker can directly publish to `motors/MTR-001/cmd` to trip relays, stop production lines, or damage machinery.

---

### 3.5 Injection, Input Validation & Denial of Service

#### 3.5.1 Path Parameter & MQTT Topic Injection
- **Affected File:** `c:\Users\gopes\Downloads\project\backend_example\main.py` (lines 402–408)
- **Observed Code:**
  ```python
  @app.post("/api/motors/{motor_id}/control", tags=["Motors"])
  def send_motor_control(motor_id: str, command: str):
      topic = f"motors/{motor_id}/cmd"
      payload = json.dumps({"command": command, "issued_at": datetime.now(timezone.utc).isoformat()})
      mqtt_client.publish(topic, payload)
  ```
- **Finding:**
  The `motor_id` path parameter is interpolated directly into the MQTT topic string without validation.
- **Defensive Impact:**
  If an attacker passes a path parameter containing MQTT wildcards or directory traversals (e.g., `+`, `#`, `/`), they can alter the destination topic or publish to unintended broker topics.

#### 3.5.2 Mass Assignment & Unbounded Ingestion
- **Affected File:** `c:\Users\gopes\Downloads\project\backend_example\main.py` (lines 162–232, 318–333)
- **Observed Code:**
  ```python
  @app.post("/api/telemetry", tags=["Telemetry"])
  async def receive_telemetry(payload: Dict[str, Any]):
      enriched, new_alerts = await process_telemetry_payload(payload)
      ...
  ```
  And inside `process_telemetry_payload`:
  ```python
  enriched = {
      **data,
      "motor_id": motor_id,
      ...
  }
  await save_telemetry(enriched)
  ```
- **Finding:**
  The schema `SensorDataTestPayload` was declared on line 55 of `main.py` but **never enforced** on the `/api/telemetry` endpoint. The endpoint accepts an untyped `Dict[str, Any]`.
  The dictionary unpacking (`**data`) allows clients to inject arbitrary key-value pairs into the telemetry document, which are subsequently stored into MongoDB and broadcast to all connected WebSocket clients (Mass Assignment).

#### 3.5.3 Unbounded History Query & Memory Exhaustion (DoS)
- **Affected File:** `c:\Users\gopes\Downloads\project\backend_example\main.py` (lines 359–374)
- **Observed Code:**
  ```python
  @app.get("/api/motors/{motor_id}/history", tags=["Motors"])
  async def get_motor_history(motor_id: str, limit: int = 100):
      ...
      cursor = db["telemetry"].find({"motor_id": motor_id}, {"_id": 0}).sort("server_timestamp", -1).limit(limit)
      records = await cursor.to_list(length=limit)
      return records[::-1]
  ```
- **Finding:**
  `limit` parameter has no upper bound validation (e.g., `Query(..., ge=1, le=1000)`). A client requesting `limit=5000000` forces MongoDB and FastAPI to allocate large amounts of memory to buffer records, inducing high CPU/RAM usage and eventual Denial of Service (OOM crash).

#### 3.5.4 Absence of API Rate Limiting
- **Finding:**
  Neither the FastAPI backend nor the WebSocket broadcaster implements rate limiting or connection throttling.
  An automated script can flood `/api/telemetry` or `/api/test/sensor-data` with thousands of requests per second, overwhelming the MongoDB write pool and saturating the asynchronous event loop during WebSocket broadcasts.

---

## 4. Threat Model & STRIDE Analysis

| STRIDE Threat | Attack Vector | System Vulnerability | Impact |
| :--- | :--- | :--- | :--- |
| **Spoofing** | Rogue ESP32 or attacker on LAN | Unauthenticated MQTT / REST telemetry | Injects fraudulent vibration/temperature telemetry; induces fake maintenance downtime. |
| **Tampering** | In-flight MQTT manipulation | Plain TCP 1883 without TLS or HMAC | Commands altered in transit to activate/deactivate relays. |
| **Repudiation** | Motor command dispatch | Missing audit logging and missing user identity context | Critical motor shutdowns cannot be attributed to specific operators or IP addresses. |
| **Information Disclosure** | Sniffing LAN / Unauthenticated API | `/api/users` and `/ws/live` open to public; cleartext Wi-Fi creds | Exposure of network credentials, employee accounts, and proprietary industrial diagnostics. |
| **Denial of Service** | WebSocket / Telemetry flooding | No rate limiting; unbounded `limit` parameter on history query | Server memory exhaustion, event loop lockup, crash of real-time monitoring. |
| **Elevation of Privilege** | LocalStorage modification | `ProtectedRoute.jsx` client-side only role checking | Operator elevates to Admin role in browser, accessing device commissioning and user deletion. |

---

## 5. Defensive Hardening & Remediation Blueprint

### 5.1 Architecture Target Model

```
[ ESP32 Motor Node ]                 [ Browser Client ]
        │                                    │
    mTLS (Port 8883)                     HTTPS / WSS
   X.509 Device Cert                  JWT Bearer Token
        │                                    │
        ▼                                    ▼
[ Secure Mosquitto Broker ]          [ FastAPI Backend ]
   - ACL: motors/%u/data                - JWT Auth Dependency
   - Client Cert Auth                   - Role Verification Middleware
        │                               - Rate Limiting (SlowAPI)
        ▼                                    │
   [ Backend Consumer ]                      ▼
   - Strict Pydantic Schema             [ MongoDB (TLS + Auth) ]
```

---

### 5.2 Step-by-Step Remediation Recommendations

#### Recommendation 1: Implement Proper Server-Side JWT Authentication & RBAC
Implement standard FastAPI security dependencies with role enforcement:

```python
# backend_example/auth.py (Recommended Architecture)
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import BaseModel
import os

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "SECURE_PRODUCTION_HEX_STRING_HERE")
ALGORITHM = "HS256"
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token")

class TokenData(BaseModel):
    user_id: str
    email: str
    role: str

def get_current_user(token: str = Depends(oauth2_scheme)) -> TokenData:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        role: str = payload.get("role")
        email: str = payload.get("email")
        if user_id is None or role is None:
            raise credentials_exception
        return TokenData(user_id=user_id, email=email, role=role)
    except JWTError:
        raise credentials_exception

def require_role(allowed_roles: list[str]):
    def role_checker(current_user: TokenData = Depends(get_current_user)):
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Operation not permitted for role '{current_user.role}'"
            )
        return current_user
    return role_checker
```

Protect critical endpoints:
```python
@app.post("/api/motors/{motor_id}/control", tags=["Motors"])
def send_motor_control(
    motor_id: str,
    command: str,
    current_user: TokenData = Depends(require_role(["admin", "manager"]))
):
    ...
```

#### Recommendation 2: Eliminate Client-Side Default Admin Fallback & Passwords in Storage
1. Update `AppContext.jsx`:
   - Initialize `currentUser` to `null`.
   - Never default to `users[0]` when unauthenticated.
   - Remove passwords from client data models and localStorage entirely.
   - Store only the short-lived JWT access token in memory or `HttpOnly, Secure, SameSite=Strict` cookies.
2. Fix `ProtectedRoute.jsx`:
   - If not authenticated, redirect to `/login`.
   - Ensure the UI reflects permissions from the decoded, cryptographically signed token claims.

#### Recommendation 3: Sanitize IoT Firmware & Externalize Secrets
1. Remove all Wi-Fi credentials from source code:
   - Use `WiFiManager` or compile-time environment injection (e.g. `secrets.h` added to `.gitignore`).
   - Store credentials in ESP32 encrypted NVS (Non-Volatile Storage) via BLE provisioning.
2. Enforce MQTTS (MQTT over TLS):
   - Replace `WiFiClient` with `WiFiClientSecure`.
   - Provision CA certificates on the ESP32 to verify broker identity.
   - Configure username and password or client certificates for mutual authentication.

#### Recommendation 4: Fix CORS Policy
Configure explicit trusted origins and avoid wildcard matching when credentials are enabled:
```python
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)
```

#### Recommendation 5: Enforce Strict Schema Validation & Rate Limiting
1. Apply the Pydantic schema `SensorDataTestPayload` directly to `/api/telemetry`:
   ```python
   @app.post("/api/telemetry", tags=["Telemetry"])
   async def receive_telemetry(payload: SensorDataTestPayload):
       enriched, new_alerts = await process_telemetry_payload(payload.model_dump())
       ...
   ```
2. Bound query parameters to prevent DoS:
   ```python
   from fastapi import Query

   @app.get("/api/motors/{motor_id}/history", tags=["Motors"])
   async def get_motor_history(
       motor_id: str = Path(..., regex="^[A-Za-z0-9_-]{3,20}$"),
       limit: int = Query(default=100, ge=1, le=1000)
   ):
       ...
   ```
3. Add `slowapi` rate limiting to protect ingestion and control endpoints from brute-force and flooding.

---

## 6. Audit Conclusion & Deliverable Status

All requested defensive security checkpoints have been verified by inspecting the codebase:
- **Authentication:** Confirmed missing across all backend endpoints; frontend authentication verified as purely client-side mock logic with passwordless bypass.
- **Authorization & RBAC:** Confirmed that frontend `ProtectedRoute.jsx` can be trivially bypassed via `localStorage` role editing, and backend endpoints have zero RBAC verification.
- **Credential Exposure:** Identified hardcoded Wi-Fi credentials in firmware, universal default passwords (`password123`) in seed/mock data, and sensitive data leakage in `/api/users`.
- **Network Security:** Documented hazardous CORS configuration (`*` with credentials), unauthenticated WebSocket broadcasting, and unencrypted/unauthenticated MQTT protocol exposure.
- **Input Validation & DoS:** Documented MQTT topic injection potential, mass assignment risk, unbounded query history limits, and lack of rate limiting.

The findings and remediation strategies in this document provide a clear roadmap for securing the Motor-Guard platform before production deployment.

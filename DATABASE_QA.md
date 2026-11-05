# Motor-Guard Software Audit: Database QA & Data Architecture Report

**Document ID:** AUDIT-DB-004  
**Target Project:** `c:\Users\gopes\Downloads\project`  
**Auditor Role:** AGENT 4 — DATABASE QA AGENT  
**Audit Scope:** `backend_example/database.py`, `backend_example/seed_users.py`, `backend_example/main.py`  
**Date:** September 30, 2026  
**Status:** COMPLETE (Read-Only Audit)

---

## Executive Summary & Scorecard

An exhaustive, non-destructive audit of the database layer in the **Motor-Guard Predictive Maintenance System** was executed. The system utilizes **MongoDB** via the **Motor (asyncio)** driver (`AsyncIOMotorClient`) paired with **FastAPI**.

While the database integration demonstrates functional baseline prototypes for telemetry logging and alert creation, the implementation contains **critical architectural vulnerabilities, index mismatches, schema omissions, and cascading timeout risks** that will lead to severe performance degradation, memory exhaustion, or service outages under industrial telemetry loads.

### QA Scorecard

| Assessment Domain | Status | Rating | Key Finding |
|---|---|---|---|
| **1. Connection Logic & Pooling** | ⚠️ Warning | 5.5 / 10 | Static pool (20 max), missing socket/queue timeouts, unhandled initialization reference bug. |
| **2. Collections Architecture** | ⚠️ Warning | 6.0 / 10 | Only 3 collections (`telemetry`, `alerts`, `users`); motors and maintenance exist only in frontend/mock state. |
| **3. Schema Validation & Types** | ❌ Critical | 3.5 / 10 | Zero DB-level validation; Pydantic model is dead code; endpoint accepts unvalidated `Dict[str, Any]`. |
| **4. Indexing & Optimization** | ❌ Critical | 4.0 / 10 | Compound index prefix rule violation breaks `alerts` sort (triggers `COLLSCAN`); zero indexes on `users`. |
| **5. Query Efficiency & Pagination** | ⚠️ Warning | 5.0 / 10 | No cursor/keyset pagination; memory-heavy in-memory slicing `records[::-1]`; missing projection. |
| **6. Mutation & Side Effects** | ⚠️ Warning | 6.5 / 10 | `data = dict(record)` protects root from `_id`, but shallow copy leaves nested fields vulnerable to mutation. |
| **7. Data Integrity & Timestamps** | ❌ Critical | 4.0 / 10 | Timestamps stored as ISO strings instead of BSON Date; sorting divergence and 300% storage overhead. |
| **8. Fault Tolerance & Outages** | ❌ Critical | 3.0 / 10 | Reconnection loop absent; offline DB causes 5–15s request blocking, starving the MQTT event loop. |

---

## 1. Database Connection Logic & Resilience

### 1.1 Motor Client Configuration (`database.py:21-26`)
```python
db_instance.client = AsyncIOMotorClient(
    MONGO_URI,
    maxPoolSize=20,
    minPoolSize=5,
    serverSelectionTimeoutMS=5000
)
```

#### Deficiencies Identified:
1. **Connection Pool Bottleneck (`maxPoolSize=20`):**
   - In an industrial plant monitoring multiple high-frequency ESP32 microcontrollers (sending telemetry at 5–50 Hz) alongside concurrent WebSocket dashboard viewers and REST consumers, a ceiling of 20 sockets is inadequate.
   - Crucially, `waitQueueTimeoutMS` is **omitted**. Under burst traffic, coroutines requesting a socket from the pool will wait indefinitely instead of timing out quickly or rejecting load, causing memory bloat and coroutine starvation.
2. **Missing Network & Socket Timeouts:**
   - `socketTimeoutMS` is not configured (defaults to `None` in PyMongo). If a network intermediary or firewall silently drops TCP connections, queries can hang indefinitely.
   - `connectTimeoutMS` is left at the driver default (20,000 ms), which is far too long for a low-latency API service.
3. **Missing Driver Resilience Flags:**
   - Missing `retryWrites=True` and `retryReads=True` explicit guarantees.
   - Missing `uuidRepresentation="standard"` configuration.

### 1.2 The Initialization & Unreachable DB Trap (`database.py:20-40`)
```python
try:
    db_instance.client = AsyncIOMotorClient(...)
    db_instance.db = db_instance.client[DATABASE_NAME]

    # Verify connection
    await db_instance.client.admin.command('ping')
    logger.info(...)
except ConnectionFailure as e:
    logger.warning(f"Could not connect to MongoDB ({e}). Running without DB persistence.")
except Exception as e:
    logger.warning(f"MongoDB initialization error: {e}")
```

#### Critical Defect:
- Notice line 27: `db_instance.db = db_instance.client[DATABASE_NAME]` executes **before** line 30 `await db_instance.client.admin.command('ping')`.
- When MongoDB is offline at startup, `command('ping')` throws `ServerSelectionTimeoutError` (or `ConnectionFailure`).
- In the `except` blocks (lines 36–40), the error is logged, **but `db_instance.db` and `db_instance.client` are never reset to `None`!**
- Consequently, `get_db()` returns the unverified `AsyncIOMotorDatabase` instance.
- Throughout `main.py`, guards checking `if db is not None:` evaluate to **`True`**, causing subsequent API and pipeline calls to attempt database operations on an unreachable client, incurring 5,000 ms blocking timeouts repeatedly!

### 1.3 Hardcoded Connection String in `seed_users.py:69`
```python
async def seed_users():
    client = AsyncIOMotorClient("mongodb://localhost:27017")
    db = client["motor_health_db"]
```
- `seed_users.py` bypasses the centralized `MONGO_URI` and `DB_NAME` environment variables defined in `database.py`. It hardcodes `mongodb://localhost:27017` and database `motor_health_db`, preventing deployment in Docker, Kubernetes, or containerized CI/CD without code editing.

---

## 2. Collections Architecture & State Disparity

The MongoDB database currently maintains three active collections:

```
motor_health_db
 ├── telemetry  (790 documents currently persisted)
 ├── alerts     (17 documents currently persisted)
 └── users      (6 documents currently persisted)
```

### Architectural Gaps:
1. **Missing Entity Collections:**
   - There is no `motors` collection in MongoDB. All motor metadata (name, power, rated RPM, location, ESP32 pairing) is hardcoded in the frontend (`mockData.js` and `localStorage`).
   - There are no `devices`, `maintenance_logs`, or `reports` collections, even though `Settings.jsx` advertises REST endpoints for them.
2. **Frontend / Backend Synchronization Gap:**
   - In `seed_users.py`, initial users are seeded into MongoDB.
   - However, `main.py` provides **only a read endpoint** (`GET /api/users`). There are no `POST`, `PUT`, or `DELETE` endpoints for users.
   - In `motor-dashboard/src/pages/Users.jsx`, user additions, updates, and deletions mutate **only browser `localStorage`**. The MongoDB `users` collection is never updated after initial seeding.

---

## 3. Schema Consistency & Validation

### 3.1 Database-Level Validation
- **Status:** **Completely Absent.**
- MongoDB native JSON schema validation (`validator` / `$jsonSchema`) is not configured on any collection during `connect_to_mongo()`.
- MongoDB accepts any arbitrary BSON structure into `telemetry`, `alerts`, and `users`.

### 3.2 Pydantic Validation & The "Dead Code" Vulnerability
In `main.py:55-61`, a Pydantic model is defined:
```python
class SensorDataTestPayload(BaseModel):
    motor_id: str = Field(default="MTR-001", description="Motor ID, e.g. MTR-001")
    vibration_mm_s: float = Field(..., description="Vibration RMS velocity in mm/s")
    temperature_c: float = Field(..., description="Motor temperature in °C")
    current_a: float = Field(..., description="Motor current in Amperes")
    anomaly_score: float = Field(default=0.0, description="Edge Impulse TinyML anomaly score (0.0 - 1.0)")
```

#### Critical Vulnerability:
- **`SensorDataTestPayload` is never used.**
- Both ingestion endpoints in `main.py:319` and `main.py:336` declare:
  ```python
  @app.post("/api/telemetry")
  async def receive_telemetry(payload: Dict[str, Any]):
  
  @app.post("/api/test/sensor-data")
  async def test_sensor_data(payload: Dict[str, Any]):
  ```
- Because `Dict[str, Any]` is used, FastAPI bypasses all Pydantic schema validation.

### 3.3 Type Coercion Crashes in `process_telemetry_payload`
In `main.py:173-175`:
```python
vib = float(data.get("vibration_mm_s", data.get("vibration_g", 0.0)))
temp = float(data.get("temperature_c", 0.0))
curr = float(data.get("current_a", 0.0))
```
- If an ESP32 or client sends `{ "vibration_mm_s": "corrupt" }` or `{ "temperature_c": None }`, `float()` throws an unhandled `ValueError` or `TypeError`.
- Because there is no error handler wrapping `process_telemetry_payload`, this causes:
  1. An unhandled **HTTP 500 Internal Server Error** on REST endpoints.
  2. An unhandled exception in `on_mqtt_message` thread pool, causing message drops.

### 3.4 Document Pollution & BSON Injection Risk
In `main.py:199-215`:
```python
enriched = {
    **data,
    "motor_id": motor_id,
    ...
}
await save_telemetry(enriched)
```
- Unpacking `**data` directly transfers all unvalidated, incoming client fields into the MongoDB document.
- An external client can send bloated payloads, reserved BSON operators, or malicious properties that pollute the collection and inflate document sizes.

---

## 4. Index Creation & Query Optimization

### 4.1 Index Inventory

| Collection | Existing Indexes in Code & Database | Analyzed Query | Index Utilization |
|---|---|---|---|
| `telemetry` | `_id_`<br>`[("motor_id", 1), ("server_timestamp", -1)]` | `find({"motor_id": motor_id}).sort("server_timestamp", -1)` | ✅ **Optimal (IXSCAN)** |
| `alerts` | `_id_`<br>`[("motor_id", 1), ("timestamp", -1)]` | `find({}).sort("timestamp", -1).limit(limit)` | ❌ **FAILURE (COLLSCAN)** |
| `users` | `_id_` | `find({})` | ⚠️ Default only |

### 4.2 Critical Index Flaw: The Compound Index Prefix Rule on `alerts`
In `database.py:35`:
```python
await db_instance.db["alerts"].create_index([("motor_id", 1), ("timestamp", -1)])
```
In `main.py:381`:
```python
cursor = db["alerts"].find({}, {"_id": 0}).sort("timestamp", -1).limit(limit)
```

#### Technical Breakdown:
- Under MongoDB B-Tree indexing rules, a compound index on `(A, B)` can **only** be used for sorting on `B` if the query includes an **equality filter on `A`**.
- Because `find({})` queries across **all** motors without filtering on `motor_id`, MongoDB **cannot traverse the index** for sorting by `timestamp`.
- **Result:** MongoDB executes a full collection scan (`COLLSCAN`) followed by an in-memory blocking sort (`SORT`).
- **Production Impact:** Once the `alerts` collection exceeds MongoDB's internal in-memory sort limit (32 MB / `internalQueryExecMaxBlockingSortBytes`), this query will crash with:
  ```
  Executor error during find command :: caused by :: Sort exceeded memory limit of 33554432 bytes
  ```
- **Remediation:** Add an index on `[("timestamp", -1)]` or `[("status", 1), ("timestamp", -1)]`.

### 4.3 Missing Indexes on `users`
- In `seed_users.py` and `database.py`, no index is created on `email`.
- If an authentication or user lookup endpoint is queried by email (`find_one({"email": email})`), MongoDB performs a full table scan.
- No `unique=True` index exists on `email`, allowing duplicate user accounts.

---

## 5. Query Efficiency & Pagination

### 5.1 Pagination Analysis
1. **`GET /api/motors/{motor_id}/history` (`main.py:360-374`):**
   ```python
   cursor = db["telemetry"].find(
       {"motor_id": motor_id},
       {"_id": 0}
   ).sort("server_timestamp", -1).limit(limit)
   records = await cursor.to_list(length=limit)
   return records[::-1]
   ```
   - Supports only a `limit` parameter (default 100).
   - **No cursor-based or keyset pagination** (`before_timestamp`, `after_timestamp`) is supported. Users cannot page backward to retrieve older historical graphs.
2. **`GET /api/alerts` (`main.py:376-388`):**
   - Supports only `limit=50`. No offset, date range, or status filtering (`active`, `resolved`).
3. **`GET /api/users` (`main.py:390-400`):**
   - Hardcoded `cursor.to_list(length=100)`. If users exceed 100, remaining users are silently truncated.

### 5.2 Memory Slicing Overhead: `records[::-1]`
- `get_motor_history` pulls descending records from MongoDB, loads the entire array into server memory via `to_list()`, and reverses it with `records[::-1]` before returning.
- Under high concurrent user loads querying long historical spans, this duplicates array allocation on the Python heap.

### 5.3 Missing Field Projection
- `get_motor_history` queries with projection `{"_id": 0}`, pulling every raw field stored in the telemetry document (including raw Edge Impulse buffers, extra metadata).
- It should project only the fields required for frontend visualization: `server_timestamp`, `vibration_mm_s`, `temperature_c`, `current_a`, `health_score`, `rul_days`.

---

## 6. Mutation & Side Effects

### 6.1 `dict(record)` vs `copy.deepcopy(record)` (`database.py:51-70`)
```python
async def save_telemetry(record: dict):
    db = get_db()
    if db is not None:
        try:
            # Create a copy so we don't mutate original dict with _id
            data = dict(record)
            await db["telemetry"].insert_one(data)
        except Exception as e:
            logger.error(...)
```

#### Evaluation:
- When PyMongo's `insert_one(doc)` executes, if `doc` does not contain `_id`, PyMongo mutates `doc` in-place by assigning `doc["_id"] = ObjectId()`.
- In `save_telemetry`, doing `data = dict(record)` performs a **shallow copy**.
- Because it is a shallow copy, the assignment `data["_id"] = ObjectId()` mutates `data`, leaving the original `record` top-level dictionary intact without `_id`.
- **Why this was necessary:** In `main.py:224-229`, `save_telemetry(enriched)` is followed immediately by `await broadcast_ws(enriched)`. If `save_telemetry` had mutated `enriched` by adding `_id: ObjectId(...)`, `json.dumps(payload)` inside `broadcast_ws` would crash with `TypeError: Object of type ObjectId is not JSON serializable`.

#### Latent Risks with Shallow Copy:
1. **Nested Mutation:** If any nested dict or list within `record` is modified during database hooks, sanitization, or middleware, the shallow copy does not protect the original object.
2. **Dual Identifier Anti-Pattern in `alerts`:**
   In `evaluate_alerts`, alerts are created with `"id": f"ALT-{timestamp_key}"`.
   When `save_alert` runs `insert_one(data)`, MongoDB assigns a separate `_id: ObjectId(...)`.
   The stored document now contains both `id` and `_id`, introducing identifier redundancy and confusion across client consumers.

---

## 7. Data Integrity, Types & Timestamps

### 7.1 ISO Strings vs Native BSON Date
In `main.py:198-211` and `seed_users.py:13-14`:
```python
now_iso = datetime.now(timezone.utc).isoformat()
# Stored as string: "2026-09-30T15:25:00.123456+00:00"
```

#### Severe Drawbacks of Storing Strings in MongoDB:
1. **Sorting Inconsistencies:**
   - Lexicographical string sorting only works if all timestamps strictly adhere to identical formatting (same timezone representation, uniform microsecond precision).
   - In `seed_users.py`: uses `datetime.utcnow().isoformat()` (naive ISO string without timezone suffix, e.g. `"2026-09-30T15:25:00.123456"`).
   - In `main.py`: uses `datetime.now(timezone.utc).isoformat()` (ISO string with `+00:00` suffix).
   - If timestamps from different generators diverge in format, MongoDB string sorts produce invalid chronological ordering.
2. **Storage and Index Footprint:**
   - Native BSON Date is a 64-bit integer (8 bytes) representing milliseconds since Unix epoch.
   - ISO 8601 string occupies **32–36 bytes** plus BSON string header overhead (~40 bytes).
   - In a time-series telemetry table storing millions of records, string timestamps increase storage and RAM index requirements by **300% to 400%**.
3. **Loss of Native MongoDB Time-Series Aggregations:**
   - Operators such as `$dateTrunc`, `$hour`, `$dayOfWeek`, `$dateToString`, and time-series bucketing (`$bucketAuto`) cannot operate on strings without invoking expensive runtime `$dateFromString` pipeline conversions.

### 7.2 Custom String `_id` vs BSON `ObjectId` in `users`
In `seed_users.py`:
```python
users_data = [
    {
        "_id": "USR-001",
        "name": "Admin User",
        ...
    }
]
```
- `seed_users.py` uses custom string IDs (`"USR-001"`).
- In `main.py:390`:
  ```python
  @app.get("/api/users")
  async def get_all_users():
      cursor = db["users"].find({})
      users = await cursor.to_list(length=100)
      return users
  ```
- Because seeded users have string `_id`, FastAPI's standard JSON encoder serializes them successfully.
- **Vulnerability:** If any user document is inserted into MongoDB without an explicit string `_id` (so MongoDB generates a standard BSON `ObjectId`), `GET /api/users` will crash with:
  ```
  TypeError: ObjectId('...') is not JSON serializable
  ```
  because `main.py` lacks a custom JSON encoder or projection (`{"_id": 0}` or converting `_id` to string).

---

## 8. Failure Modes & Cascading Outage Analysis

### 8.1 MongoDB Down / Unreachable Scenario
When MongoDB becomes unreachable during runtime:

```
[Incoming ESP32 Telemetry via HTTP / MQTT]
                  │
                  ▼
      process_telemetry_payload()
                  │
                  ▼
         save_telemetry()
                  │
      db = get_db() -> Truthy! (Due to initialization bug)
                  │
                  ▼
     await db["telemetry"].insert_one(data)
                  │
        [BLOCKED FOR 5,000 ms]
         (serverSelectionTimeoutMS)
                  │
                  ▼
         Timeout Exception Caught & Logged
                  │
                  ▼
      save_alert() (If alert triggered)
                  │
        [BLOCKED FOR ANOTHER 5,000 ms]
                  │
                  ▼
     Total Request Latency: 10,000 ms – 15,000 ms!
```

### 8.2 Consequences of the Unreachable DB Failure Mode:
1. **High API Latency:** Ingest endpoints block for 5 to 15 seconds per call instead of returning in < 10 ms.
2. **WebSocket Broadcast Lag:** In `process_telemetry_payload`, `broadcast_ws` is called **after** `await save_telemetry()` and `await save_alert()`. The live dashboard stops receiving real-time data for 10–15 seconds whenever DB operations time out!
3. **MQTT Event Loop Thread Starvation:**
   - In `main.py:246`:
     ```python
     asyncio.run_coroutine_threadsafe(process_telemetry_payload(data), server_loop)
     ```
   - Each incoming MQTT packet schedules a coroutine on `server_loop`.
   - When each coroutine blocks for 5–15 seconds on MongoDB timeouts, the event loop becomes severely backlogged.
   - Paho MQTT's network loop misses its `keepalive` ping response, causing the MQTT broker to disconnect the backend for timing out!

---

## 9. Comprehensive Remediation Plan

To bring the database layer to industrial production standards, the following architectural fixes are recommended:

### 9.1 Connection & Resilience Architecture (`database.py`)
1. Implement a proper connection lifecycle with reset on failure.
2. Configure complete timeout parameters:
   - `serverSelectionTimeoutMS=2000` (Fail fast)
   - `connectTimeoutMS=3000`
   - `socketTimeoutMS=5000`
   - `waitQueueTimeoutMS=1000`
   - `maxPoolSize=50`
3. Add a background heartbeat task that periodically checks MongoDB and recovers the connection when the database restarts.

### 9.2 Proper Index Architecture
Execute the following index creations:
```python
# Telemetry: Historical lookup & motor time-series
await db["telemetry"].create_index([("motor_id", 1), ("server_timestamp", -1)])

# Alerts: System-wide chronological alert feed
await db["alerts"].create_index([("timestamp", -1)])
await db["alerts"].create_index([("status", 1), ("timestamp", -1)])
await db["alerts"].create_index([("motor_id", 1), ("timestamp", -1)])

# Users: Unique email lookup
await db["users"].create_index([("email", 1)], unique=True)
```

### 9.3 Migration to BSON Date & Keyset Pagination
- Replace ISO string generation with timezone-aware `datetime.now(timezone.utc)`.
- Use MongoDB native Date objects in BSON. Motor/PyMongo automatically serializes Python `datetime` objects to BSON Date.
- When serializing to REST/WebSocket JSON, format as ISO 8601 strings in Pydantic encoders.
- Implement cursor-based history pagination:
  ```python
  @app.get("/api/motors/{motor_id}/history")
  async def get_motor_history(
      motor_id: str,
      limit: int = 100,
      before_timestamp: Optional[datetime] = None
  ):
      query = {"motor_id": motor_id}
      if before_timestamp:
          query["server_timestamp"] = {"$lt": before_timestamp}
      cursor = db["telemetry"].find(
          query,
          {"_id": 0, "server_timestamp": 1, "vibration_mm_s": 1, "temperature_c": 1, "current_a": 1, "health_score": 1}
      ).sort("server_timestamp", -1).limit(min(limit, 500))
      return await cursor.to_list(length=limit)
  ```

### 9.4 Non-Blocking Ingestion Pipeline
- In `process_telemetry_payload`, decouple database persistence from real-time WebSocket broadcasting:
  1. Broadcast via WebSocket **first** (zero latency to frontend).
  2. Use `asyncio.create_task(save_telemetry(enriched))` or an internal `asyncio.Queue` background worker for database writes, ensuring database stalls never degrade live telemetry streaming or MQTT packet processing.

---

## 10. Audit Sign-off

- **Audited Files:**
  - [database.py](file:///c:/Users/gopes/Downloads/project/backend_example/database.py)
  - [seed_users.py](file:///c:/Users/gopes/Downloads/project/backend_example/seed_users.py)
  - [main.py](file:///c:/Users/gopes/Downloads/project/backend_example/main.py)
- **Report Location:** `c:\Users\gopes\Downloads\project\reports\DATABASE_QA.md`
- **Execution Mode:** Strictly Read-Only (Source code unchanged, existing collections intact).
- **Audit Conclusion:** The database layer requires immediate remediation on index structure, validation bindings, timestamp typing, and async persistence isolation before high-frequency production deployment.

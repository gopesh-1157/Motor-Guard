"""
MotorGuard — Database Seeder & Live Verification Script

Populates real collections in MongoDB ('motorguard_db'):
  - users (Admin, Manager, Technician, Operator)
  - motors (Master asset records)
  - alerts (Active, Critical, and Warning incidents)
  - telemetry_events (Historical sensor readings)
"""

import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
import pymongo
from backend.app.core.security import get_password_hash

MONGO_URI = os.getenv("MONGO_URI", "mongodb://127.0.0.1:27017")
DB_NAME = os.getenv("MONGO_DB_NAME", "motorguard_db")


def seed_database():
    print(f"Connecting to MongoDB at {MONGO_URI} (Database: {DB_NAME})...")
    client = pymongo.MongoClient(MONGO_URI, serverSelectionTimeoutMS=3000)
    db = client[DB_NAME]

    now = datetime.now(timezone.utc)

    # 1. Seed Users
    users_col = db["users"]
    users_col.create_index("username", unique=True)
    users_col.create_index("email", unique=True)

    demo_users = [
        {
            "username": "admin",
            "email": "admin@motorguard.local",
            "role": "Admin",
            "password_hash": get_password_hash("admin123"),
            "assigned_sites": ["SITE-PLANT-A"],
            "assigned_motors": [],
            "is_active": True,
            "created_at": now,
            "last_login_at": now,
        },
        {
            "username": "manager_alice",
            "email": "alice.manager@factory.local",
            "role": "Manager",
            "password_hash": get_password_hash("manager123"),
            "assigned_sites": ["SITE-PLANT-A"],
            "assigned_motors": ["MTR-775-001", "MTR-775-002", "MTR-775-003"],
            "is_active": True,
            "created_at": now,
            "last_login_at": now,
        },
        {
            "username": "tech_dave",
            "email": "dave.tech@factory.local",
            "role": "Technician",
            "password_hash": get_password_hash("tech123"),
            "assigned_sites": ["SITE-PLANT-A"],
            "assigned_motors": ["MTR-775-001", "MTR-775-003"],
            "is_active": True,
            "created_at": now,
            "last_login_at": now,
        },
        {
            "username": "tech_sara",
            "email": "sara.tech@factory.local",
            "role": "Technician",
            "password_hash": get_password_hash("tech123"),
            "assigned_sites": ["SITE-PLANT-A"],
            "assigned_motors": ["MTR-775-002"],
            "is_active": True,
            "created_at": now,
            "last_login_at": now,
        },
        {
            "username": "operator_bob",
            "email": "bob.operator@factory.local",
            "role": "Operator",
            "password_hash": get_password_hash("operator123"),
            "assigned_sites": ["SITE-PLANT-A"],
            "assigned_motors": ["MTR-775-001", "MTR-775-002", "MTR-775-003"],
            "is_active": True,
            "created_at": now,
            "last_login_at": now,
        },
    ]

    for u in demo_users:
        users_col.update_one({"username": u["username"]}, {"$set": u}, upsert=True)
    print(f"[OK] Seeded {len(demo_users)} users (Admin, Manager, Technicians, Operator)")

    # 2. Seed Motors Master Records
    motors_col = db["motors"]
    motors_col.create_index("motor_id", unique=True)

    demo_motors = [
        {
            "motor_id": "MTR-775-001",
            "site_id": "SITE-PLANT-A",
            "name": "Line 3 Conveyor Feed Actuator",
            "model": "RS-775 High-Torque DC Motor",
            "rated_voltage_v": 12.0,
            "rated_current_a": 2.5,
            "overcurrent_limit_a": 4.0,
            "max_temp_c": 50.0,
            "max_vibration_g": 0.200,
            "assigned_device_id": "esp32-node-001",
            "health_status": "healthy",
            "operational_state": "RUNNING",
            "notes": "Optimal condition. Vibration damping mount intact.",
        },
        {
            "motor_id": "MTR-775-002",
            "site_id": "SITE-PLANT-A",
            "name": "Spindle Cooling Fan Motor",
            "model": "RS-775 High-Torque DC Motor",
            "rated_voltage_v": 12.0,
            "rated_current_a": 2.5,
            "overcurrent_limit_a": 4.0,
            "max_temp_c": 50.0,
            "max_vibration_g": 0.200,
            "assigned_device_id": "esp32-node-002",
            "health_status": "warning",
            "operational_state": "RUNNING",
            "notes": "Elevated thermal signature. Air intake filter inspection due.",
        },
        {
            "motor_id": "MTR-775-003",
            "site_id": "SITE-PLANT-A",
            "name": "High-Pressure Hydraulic Actuator",
            "model": "RS-775 High-Torque DC Motor",
            "rated_voltage_v": 12.0,
            "rated_current_a": 2.5,
            "overcurrent_limit_a": 4.0,
            "max_temp_c": 50.0,
            "max_vibration_g": 0.200,
            "assigned_device_id": "esp32-node-003",
            "health_status": "critical",
            "operational_state": "ALARM",
            "notes": "CRITICAL: Severe bearing harmonic vibration detected. Immediate technician intervention required.",
        },
    ]

    for m in demo_motors:
        motors_col.update_one({"motor_id": m["motor_id"]}, {"$set": m}, upsert=True)
    print(f"[OK] Seeded {len(demo_motors)} motor assets in 'motors' collection")

    # 3. Seed Alerts
    alerts_col = db["alerts"]
    alerts_col.create_index([("alert_id", 1)], unique=True)
    alerts_col.create_index([("motor_id", 1), ("state", 1)])

    demo_alerts = [
        {
            "alert_id": "ALT-20261010-CRIT01",
            "motor_id": "MTR-775-003",
            "device_id": "esp32-node-003",
            "severity": "CRITICAL",
            "trigger_type": "THRESHOLD_HIGH_VIBRATION",
            "trigger_value": 0.865,
            "threshold_limit": 0.200,
            "unit": "g",
            "message": "CRITICAL bearing vibration anomaly on MTR-775-003: measured 0.865 g (limit 0.200 g)",
            "state": "ACTIVE",
            "triggered_at": now - timedelta(minutes=18),
            "acknowledged_at": None,
            "acknowledged_by": None,
            "assigned_to": None,
            "assigned_by": None,
            "assigned_at": None,
            "priority": "CRITICAL",
            "instructions": None,
            "resolved_at": None,
            "resolved_by": None,
            "resolution_notes": None,
        },
        {
            "alert_id": "ALT-20261010-WARN01",
            "motor_id": "MTR-775-002",
            "device_id": "esp32-node-002",
            "severity": "WARNING",
            "trigger_type": "THRESHOLD_OVERTEMPERATURE",
            "trigger_value": 54.8,
            "threshold_limit": 50.0,
            "unit": "C",
            "message": "Thermal threshold warning on MTR-775-002: measured 54.8 C (limit 50.0 C)",
            "state": "ACTIVE",
            "triggered_at": now - timedelta(minutes=42),
            "acknowledged_at": None,
            "acknowledged_by": None,
            "assigned_to": None,
            "assigned_by": None,
            "assigned_at": None,
            "priority": "HIGH",
            "instructions": None,
            "resolved_at": None,
            "resolved_by": None,
            "resolution_notes": None,
        },
    ]

    for a in demo_alerts:
        alerts_col.update_one({"alert_id": a["alert_id"]}, {"$set": a}, upsert=True)
    print(f"[OK] Seeded {len(demo_alerts)} active alerts (1 Critical, 1 Warning)")

    # 4. Seed Telemetry Events
    telemetry_col = db["telemetry_events"]
    telemetry_col.create_index([("device_id", 1), ("event_id", 1)], unique=True)
    telemetry_col.create_index([("motor_id", 1), ("timestamp", -1)])

    telemetry_batch = []
    for m_id, d_id, base_t, base_c, base_v, health in [
        ("MTR-775-001", "esp32-node-001", 36.5, 2.15, 0.075, "healthy"),
        ("MTR-775-002", "esp32-node-002", 54.8, 3.25, 0.125, "warning"),
        ("MTR-775-003", "esp32-node-003", 44.2, 4.45, 0.865, "critical"),
    ]:
        for i in range(25):
            t_offset = now - timedelta(seconds=(25 - i) * 3)
            evt = {
                "schema_version": "1.0.0",
                "event_id": str(uuid.uuid4()),
                "device_id": d_id,
                "motor_id": m_id,
                "source": "hardware" if "001" in m_id else "simulator",
                "seq": 1000 + i,
                "timestamp": t_offset.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
                "server_received_at": t_offset,
                "sensors": {
                    "temperature_c": round(base_t + (i % 3) * 0.4, 1),
                    "current_a": round(base_c + (i % 4) * 0.05, 2),
                    "vibration_g_rms": round(base_v + (i % 5) * 0.015, 3),
                },
                "sensor_status": {
                    "temperature": "OK",
                    "current": "OK",
                    "vibration": "OK",
                },
                "inference": {
                    "status": "PREDICTED",
                    "health_status": health,
                    "confidence": 0.94 if health == "healthy" else 0.89,
                    "probabilities": {
                        "healthy": 0.94 if health == "healthy" else 0.05,
                        "warning": 0.89 if health == "warning" else 0.05,
                        "critical": 0.91 if health == "critical" else 0.01,
                    },
                    "model_version": "ei-motoguard-v1.0.1",
                    "inference_time_ms": 6,
                },
                "diagnostics": {
                    "wifi_rssi_dbm": -58,
                    "free_heap_bytes": 178000,
                    "uptime_seconds": 3600 + i * 3,
                },
            }
            telemetry_batch.append(evt)

    try:
        telemetry_col.insert_many(telemetry_batch, ordered=False)
        print(f"[OK] Seeded {len(telemetry_batch)} telemetry events in 'telemetry_events'")
    except Exception as e:
        print(f"Note: Telemetry insert skipped or partially updated: {e}")

    print("\n[SUCCESS] Verification complete! Collections in 'motorguard_db':")
    for col in db.list_collection_names():
        count = db[col].count_documents({})
        print(f"   * {col}: {count} documents")


if __name__ == "__main__":
    seed_database()

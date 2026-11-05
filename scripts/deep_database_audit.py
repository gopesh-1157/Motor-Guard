import asyncio
import json
from motor.motor_asyncio import AsyncIOMotorClient

async def deep_audit():
    client = AsyncIOMotorClient("mongodb://127.0.0.1:27017")
    target_dbs = ["motorguard_db", "motorguard_staging", "motorguard_test"]
    collections = [
        "users",
        "sites",
        "motors",
        "devices",
        "telemetry",
        "alerts",
        "work_orders",
        "maintenance_records",
        "audit_events",
        "audit_logs",
    ]

    report = {}

    for db_name in target_dbs:
        db = client[db_name]
        existing_cols = await db.list_collection_names()
        db_report = {"counts": {}, "integrity": {}}

        for col in collections:
            if col in existing_cols:
                cnt = await db[col].count_documents({})
                db_report["counts"][col] = cnt
            else:
                db_report["counts"][col] = 0

        # 1. User integrity
        users = await db["users"].find({}).to_list(1000) if "users" in existing_cols else []
        emails = [u.get("email") for u in users if u.get("email")]
        usernames = [u.get("username") for u in users if u.get("username")]
        user_ids = [str(u.get("_id")) for u in users]
        db_report["integrity"]["duplicate_user_emails"] = len(emails) - len(set(emails))
        db_report["integrity"]["duplicate_usernames"] = len(usernames) - len(set(usernames))
        db_report["integrity"]["user_roles"] = {r: sum(1 for u in users if u.get("role") == r) for r in ["Admin", "Manager", "Technician"]}

        # 2. Motors and Device relationships
        motors = await db["motors"].find({}).to_list(1000) if "motors" in existing_cols else []
        devices = await db["devices"].find({}).to_list(1000) if "devices" in existing_cols else []

        motor_ids = [m.get("motor_id") for m in motors if m.get("motor_id")]
        device_ids = [d.get("device_id") for d in devices if d.get("device_id")]

        db_report["integrity"]["duplicate_motor_ids"] = len(motor_ids) - len(set(motor_ids))
        db_report["integrity"]["duplicate_device_ids"] = len(device_ids) - len(set(device_ids))

        # Check motor -> device reference
        broken_motor_dev_refs = []
        for m in motors:
            dev_id = m.get("assigned_device_id")
            if dev_id and dev_id not in set(device_ids):
                broken_motor_dev_refs.append({"motor": m.get("motor_id"), "missing_device": dev_id})
        db_report["integrity"]["broken_motor_device_refs"] = broken_motor_dev_refs

        # Check device -> motor reference
        broken_dev_motor_refs = []
        for d in devices:
            mid = d.get("assigned_motor_id")
            if mid and mid not in set(motor_ids):
                broken_dev_motor_refs.append({"device": d.get("device_id"), "missing_motor": mid})
        db_report["integrity"]["broken_device_motor_refs"] = broken_dev_motor_refs

        # 3. Alerts -> Motor references
        alerts = await db["alerts"].find({}).to_list(5000) if "alerts" in existing_cols else []
        broken_alert_motor_refs = []
        alert_ids = [a.get("alert_id") for a in alerts if a.get("alert_id")]
        db_report["integrity"]["duplicate_alert_ids"] = len(alert_ids) - len(set(alert_ids))
        for a in alerts:
            mid = a.get("motor_id")
            if mid and mid not in set(motor_ids):
                broken_alert_motor_refs.append({"alert": a.get("alert_id"), "missing_motor": mid})
        db_report["integrity"]["broken_alert_motor_refs_count"] = len(broken_alert_motor_refs)

        # 4. Work orders -> Motor and Technician references
        wos = await db["work_orders"].find({}).to_list(1000) if "work_orders" in existing_cols else []
        broken_wo_refs = []
        valid_user_identifiers = set(user_ids) | set(usernames)
        for w in wos:
            mid = w.get("motor_id")
            assigned_to = w.get("assigned_to")
            issues = []
            if mid and mid not in set(motor_ids):
                issues.append(f"missing motor {mid}")
            if assigned_to and assigned_to not in valid_user_identifiers:
                issues.append(f"missing assignee {assigned_to}")
            if issues:
                broken_wo_refs.append({"wo_id": str(w.get("_id") or w.get("order_id")), "issues": issues})
        db_report["integrity"]["broken_work_order_refs"] = broken_wo_refs

        # 5. Telemetry deduplication and sample check
        if "telemetry" in existing_cols:
            sample_telem = await db["telemetry"].find({}, {"device_id": 1, "event_id": 1, "timestamp": 1, "motor_id": 1}).sort("timestamp", -1).limit(5).to_list(5)
            db_report["telemetry_sample"] = [
                {"motor": t.get("motor_id"), "device": t.get("device_id"), "ts": str(t.get("timestamp"))}
                for t in sample_telem
            ]

        report[db_name] = db_report

    print(json.dumps(report, indent=2))
    client.close()

if __name__ == "__main__":
    asyncio.run(deep_audit())

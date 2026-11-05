import asyncio
import json
from motor.motor_asyncio import AsyncIOMotorClient

async def inspect_details():
    client = AsyncIOMotorClient("mongodb://127.0.0.1:27017")
    
    for db_name in ["motorguard_db", "motorguard_staging", "motorguard_test"]:
        print(f"\n==========================================")
        print(f"DATABASE: {db_name}")
        print(f"==========================================")
        db = client[db_name]
        
        # Users
        users = await db["users"].find({}, {"password_hash": 0}).to_list(length=100)
        print(f"\n--- USERS ({len(users)}) ---")
        for u in users:
            print(f"  username: {u.get('username')}, role: {u.get('role')}, email: {u.get('email')}, sites: {u.get('assigned_sites')}, active: {u.get('is_active')}")
            
        # Motors
        motors = await db["motors"].find({}, {"motor_id": 1, "name": 1, "site_id": 1, "assigned_device_id": 1, "status": 1}).to_list(length=100)
        print(f"\n--- MOTORS ({len(motors)}) ---")
        for m in motors:
            print(f"  motor_id: {m.get('motor_id')}, name: {m.get('name')}, site_id: {m.get('site_id')}, device: {m.get('assigned_device_id')}, status: {m.get('status')}")
            
        # Devices
        devices = await db["devices"].find({}, {"device_id": 1, "status": 1, "assigned_motor_id": 1, "site_id": 1, "firmware_version": 1}).to_list(length=100)
        print(f"\n--- DEVICES ({len(devices)}) ---")
        for d in devices:
            print(f"  device_id: {d.get('device_id')}, status: {d.get('status')}, motor: {d.get('assigned_motor_id')}, site_id: {d.get('site_id')}, fw: {d.get('firmware_version')}")
            
        # Alerts count by state & severity
        pipeline = [
            {"$group": {"_id": {"severity": "$severity", "state": "$state"}, "count": {"$sum": 1}}}
        ]
        alerts_agg = await db["alerts"].aggregate(pipeline).to_list(length=100)
        print(f"\n--- ALERTS SUMMARY ---")
        for a in alerts_agg:
            print(f"  {a['_id']}: {a['count']}")
            
        # Work orders
        wos = await db["work_orders"].find({}).to_list(length=100)
        print(f"\n--- WORK ORDERS ({len(wos)}) ---")
        for w in wos:
            print(f"  id: {w.get('order_id') or w.get('_id')}, motor: {w.get('motor_id')}, assigned_to: {w.get('assigned_to')}, status: {w.get('status')}, priority: {w.get('priority')}")

    client.close()

if __name__ == "__main__":
    asyncio.run(inspect_details())

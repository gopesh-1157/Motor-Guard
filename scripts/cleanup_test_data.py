import os
import pymongo

target_db = os.getenv("MONGO_DB_NAME", os.getenv("TARGET_DB_NAME", "motorguard_test"))

# Strict safety refusal guard
if target_db == "motorguard_db" and os.getenv("ALLOW_LIVE_DB_CLEANUP", "false").lower() != "true":
    raise SystemExit(
        "SAFETY ERROR: Refusing to run DB cleanup or mutations against live/production database 'motorguard_db'. "
        "Test scripts must use a test database (e.g., export MONGO_DB_NAME=motorguard_test)."
    )

client = pymongo.MongoClient(os.getenv("MONGO_URI", "mongodb://127.0.0.1:27017"))
db = client[target_db]

test_wos = ['WO-20261103-21B660', 'WO-20261103-60AB1E']
test_alerts = ['ALT-20261103-268B06', 'ALT-20261103-1F933E', 'ALT-20261103-416997', 'ALT-20261103-A212E5']

r_wo = db['work_orders'].delete_many({'work_order_id': {'$in': test_wos}})
r_alt = db['alerts'].delete_many({'alert_id': {'$in': test_alerts}})

print(f"[{target_db}] Deleted {r_wo.deleted_count} test work orders: {test_wos}")
print(f"[{target_db}] Deleted {r_alt.deleted_count} test alerts: {test_alerts}")

remaining_wos = list(db['work_orders'].find({'work_order_id': {'$in': test_wos}}))
remaining_alerts = list(db['alerts'].find({'alert_id': {'$in': test_alerts}}))
print(f"[{target_db}] Remaining test work orders in DB: {len(remaining_wos)}")
print(f"[{target_db}] Remaining test alerts in DB: {len(remaining_alerts)}")

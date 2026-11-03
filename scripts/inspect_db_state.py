import pymongo
from pprint import pprint

client = pymongo.MongoClient('mongodb://127.0.0.1:27017')
db = client['motorguard_db']

print("=== COLLECTIONS OVERVIEW ===")
for col_name in sorted(db.list_collection_names()):
    print(f"  {col_name}: {db[col_name].count_documents({})}")

print("\n=== MOTORS (Real/Seeded Registry) ===")
for m in db['motors'].find({}, {'_id': 0, 'motor_id': 1, 'name': 1, 'site_id': 1}):
    print(" ", m)

print("\n=== DEVICES ===")
for d in db['devices'].find({}, {'_id': 0, 'device_id': 1, 'device_name': 1, 'status': 1, 'bound_motor_id': 1}):
    print(" ", d)

print("\n=== WORK ORDERS ===")
for w in db['work_orders'].find({}, {'_id': 0, 'work_order_id': 1, 'title': 1, 'status': 1, 'motor_id': 1, 'created_at': 1, 'assigned_to': 1}):
    print(" ", w)

print("\n=== TELEMETRY INGESTION BREAKDOWN ===")
pipeline = [
    {"$group": {"_id": {"source": "$source", "motor_id": "$motor_id"}, "count": {"$sum": 1}}}
]
for r in db['telemetry'].aggregate(pipeline):
    print(" ", r)

print("\n=== RECENT TELEMETRY SAMPLES (LAST 3) ===")
for t in db['telemetry'].find({}, {'_id': 0, 'event_id': 1, 'motor_id': 1, 'source': 1, 'timestamp': 1, 'seq': 1}).sort("timestamp", -1).limit(3):
    print(" ", t)

print("\n=== ALERTS BREAKDOWN BY MOTOR & SEVERITY ===")
alt_pipeline = [
    {"$group": {"_id": {"motor_id": "$motor_id", "severity": "$severity", "state": "$state"}, "count": {"$sum": 1}}}
]
for r in db['alerts'].aggregate(alt_pipeline):
    print(" ", r)

print("\n=== ACTIVE ALERTS (SAMPLES) ===")
for a in db['alerts'].find({"state": "ACTIVE"}, {'_id': 0, 'alert_id': 1, 'motor_id': 1, 'severity': 1, 'message': 1, 'created_at': 1}).limit(5):
    print(" ", a)

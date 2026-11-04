import pymongo
from datetime import datetime

client = pymongo.MongoClient("mongodb://localhost:27017")
db = client["motorguard_db"]

nov_start = datetime(2026, 11, 1, 0, 0, 0)
nov3_start = datetime(2026, 11, 3, 0, 0, 0)

sim_total = db.telemetry.count_documents({"source": "simulator"})
sim_nov3 = db.telemetry.count_documents({"source": "simulator", "server_received_at": {"$gte": nov3_start}})
sim_before_nov3 = db.telemetry.count_documents({"source": "simulator", "server_received_at": {"$lt": nov3_start}})

print(f"Total simulator telemetry: {sim_total}")
print(f"Simulator telemetry before Nov 3, 2026: {sim_before_nov3}")
print(f"Simulator telemetry Nov 3-4, 2026 (this session window): {sim_nov3}")

alerts_total = db.alerts.count_documents({})
alerts_nov3 = db.alerts.count_documents({"triggered_at": {"$gte": nov3_start}})
alerts_before_nov3 = db.alerts.count_documents({"triggered_at": {"$lt": nov3_start}})
print(f"\nTotal alerts: {alerts_total}")
print(f"Alerts before Nov 3, 2026: {alerts_before_nov3}")
print(f"Alerts Nov 3-4, 2026 (this session window): {alerts_nov3}")

print("\n--- 5 Samples of Simulator Telemetry (Nov 3/4 session) ---")
for idx, doc in enumerate(db.telemetry.find({"source": "simulator", "server_received_at": {"$gte": nov3_start}}).limit(5), 1):
    d = {k: str(v) if isinstance(v, datetime) else v for k, v in doc.items() if k != "_id"}
    print(f"Sample {idx}: {d}")

print("\n--- 5 Samples of Simulator Alerts (Nov 3/4 session) ---")
for idx, doc in enumerate(db.alerts.find({"triggered_at": {"$gte": nov3_start}}).limit(5), 1):
    d = {k: str(v) if isinstance(v, datetime) else v for k, v in doc.items() if k != "_id"}
    print(f"Sample {idx}: {d}")

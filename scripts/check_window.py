import pymongo
from datetime import datetime

client = pymongo.MongoClient("mongodb://localhost:27017")
db = client["motorguard_db"]

start_window = datetime(2026, 11, 4, 0, 40, 0)
end_window = datetime(2026, 11, 4, 1, 45, 0)

cnt = db.telemetry.count_documents({"server_received_at": {"$gte": start_window, "$lte": end_window}})
print(f"Telemetry received between 00:40 and 01:45 today: {cnt}")

# Check any telemetry with server_received_at on Nov 4
cnt_nov4 = db.telemetry.count_documents({"server_received_at": {"$gte": datetime(2026, 11, 4, 0, 0, 0)}})
print(f"Telemetry received anytime on Nov 4: {cnt_nov4}")

# Check any alerts with triggered_at on Nov 4
cnt_alerts_nov4 = db.alerts.count_documents({"triggered_at": {"$gte": datetime(2026, 11, 4, 0, 0, 0)}})
print(f"Alerts triggered on Nov 4: {cnt_alerts_nov4}")

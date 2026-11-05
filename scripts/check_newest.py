import pymongo

client = pymongo.MongoClient("mongodb://localhost:27017")
db = client["motorguard_db"]

docs = list(db.telemetry.find({"source": "simulator"}).sort("server_received_at", -1).limit(5))
for d in docs:
    print("sim doc server_received_at:", repr(d.get("server_received_at")), "timestamp:", d.get("timestamp"))

docs_hw = list(db.telemetry.find({"source": "hardware"}).sort("server_received_at", -1).limit(5))
for d in docs_hw:
    print("hw doc server_received_at:", repr(d.get("server_received_at")), "timestamp:", d.get("timestamp"))

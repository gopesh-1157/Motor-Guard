import pymongo
from collections import defaultdict
from datetime import datetime

client = pymongo.MongoClient("mongodb://localhost:27017")
db = client["motorguard_db"]

# The 1,716 simulator-generated alerts (excluding the 3 baseline seeded alerts)
baseline_ids = {"ALT-20261010-CRIT01", "ALT-20261010-WARN01", "ALT-20261011-27AB20"}

alerts = list(db.alerts.find({"alert_id": {"$nin": list(baseline_ids)}}))
print(f"Total target alerts: {len(alerts)}")

# Categorize by device group: esp32-node-* vs sim-node-*
# and group by (day, device_group, device_id, trigger_type)
data = defaultdict(int)
devices_seen = set()
trigger_types_seen = set()
days_seen = set()

for a in alerts:
    dev = a.get("device_id") or "unknown"
    devices_seen.add(dev)
    dev_group = "esp32-node-*" if dev.startswith("esp32-node") else "sim-node-*" if dev.startswith("sim-node") else "other"
    
    trig = a.get("trigger_type") or "unknown"
    trigger_types_seen.add(trig)
    
    t = a.get("triggered_at")
    if isinstance(t, datetime):
        day = t.strftime("%Y-%m-%d")
    elif isinstance(t, str):
        day = t[:10]
    else:
        day = "unknown"
    days_seen.add(day)
    
    data[(day, dev_group, dev, trig)] += 1

print("\n=== SUMMARY BY DEVICE GROUP ===")
group_counts = defaultdict(int)
for (day, dev_group, dev, trig), count in data.items():
    group_counts[dev_group] += count
for g, c in sorted(group_counts.items()):
    print(f"  {g}: {c} alerts")

print("\n=== SUMMARY BY DAY ===")
day_counts = defaultdict(int)
for (day, dev_group, dev, trig), count in data.items():
    day_counts[day] += count
for d, c in sorted(day_counts.items()):
    print(f"  {d}: {c} alerts")

print("\n=== SUMMARY BY TRIGGER TYPE ===")
type_counts = defaultdict(int)
for (day, dev_group, dev, trig), count in data.items():
    type_counts[trig] += count
for t, c in sorted(type_counts.items(), key=lambda x: -x[1]):
    print(f"  {t}: {c} alerts")

print("\n=== DETAILED BREAKDOWN: DAY x DEVICE GROUP x TRIGGER TYPE ===")
# Organize table: Day | Device Group | Device ID | Trigger Type | Count
sorted_keys = sorted(data.keys())
print(f"{'Day':<12} | {'Device Group':<14} | {'Device ID':<16} | {'Trigger Type':<28} | {'Count':<6}")
print("-" * 85)
for (day, dev_group, dev, trig) in sorted_keys:
    print(f"{day:<12} | {dev_group:<14} | {dev:<16} | {trig:<28} | {data[(day, dev_group, dev, trig)]:<6}")

# Flapping analysis: how many alerts resolved within seconds/minutes
resolved_alerts = [a for a in alerts if a.get("state") == "RESOLVED" and a.get("resolved_at") and a.get("triggered_at")]
durations_sec = []
for a in resolved_alerts:
    t_start = a.get("triggered_at")
    t_end = a.get("resolved_at")
    if isinstance(t_start, datetime) and isinstance(t_end, datetime):
        durations_sec.append((t_end - t_start).total_seconds())

if durations_sec:
    durations_sec.sort()
    sub_minute = sum(1 for d in durations_sec if d < 60)
    sub_5min = sum(1 for d in durations_sec if d < 300)
    print(f"\nFlapping Indicator: {len(durations_sec)} resolved alerts analyzed")
    print(f"  Resolved < 60s: {sub_minute} ({sub_minute/len(durations_sec)*100:.1f}%)")
    print(f"  Resolved < 300s: {sub_5min} ({sub_5min/len(durations_sec)*100:.1f}%)")
    print(f"  Median duration: {durations_sec[len(durations_sec)//2]:.1f}s")

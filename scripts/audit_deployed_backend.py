import json
import urllib.request
import urllib.error
import ssl

BACKEND_URL = "https://motor-guard.onrender.com"

def get_token():
    url = f"{BACKEND_URL}/api/v1/auth/login"
    payload = json.dumps({"username": "admin", "password": "adminpassword123"}).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as res:
        data = json.loads(res.read().decode("utf-8"))
        return data["access_token"], data["user"]

def test_api_endpoint(name, path, token):
    url = f"{BACKEND_URL}{path}"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as res:
            status = res.status
            content = res.read().decode("utf-8")
            data = json.loads(content) if content else {}
            item_count = len(data) if isinstance(data, list) else (len(data.get("items", [])) if isinstance(data, dict) and "items" in data else "dict")
            print(f"[{name}] {path} -> HTTP {status} (Count/Shape: {item_count})")
            return {"status": status, "data": data}
    except urllib.error.HTTPError as e:
        err_content = e.read().decode("utf-8")
        print(f"[{name}] {path} -> FAILED: HTTP {e.code} - {err_content}")
        return {"status": e.code, "error": err_content}
    except Exception as e:
        print(f"[{name}] {path} -> ERROR: {str(e)}")
        return {"status": "ERROR", "error": str(e)}

def run_backend_audit():
    print("=== AUDITING DEPLOYED RENDER BACKEND ===")
    token, admin_user = get_token()
    print("Logged in as Admin. Token obtained.")
    print("Admin assigned_sites:", admin_user.get("assigned_sites"))

    endpoints = [
        ("Health Live", "/api/v1/health/live"),
        ("Health Ready", "/api/v1/health/ready"),
        ("List Users", "/api/v1/auth/users"),
        ("Current User (/me)", "/api/v1/auth/me"),
        ("List Technicians", "/api/v1/auth/technicians"),
        ("List Motors", "/api/v1/motors"),
        ("List Devices", "/api/v1/devices"),
        ("List Alerts", "/api/v1/alerts"),
        ("List Work Orders", "/api/v1/work-orders"),
        ("Telemetry Latest (MTR-775-001)", "/api/v1/telemetry/latest?motor_id=MTR-775-001"),
        ("Settings", "/api/v1/settings"),
    ]

    results = {}
    for name, path in endpoints:
        results[name] = test_api_endpoint(name, path, token)

    # Let's inspect the returned data in detail
    print("\n--- DEPLOYED USERS ---")
    users = results.get("List Users", {}).get("data", [])
    if isinstance(users, list):
        for u in users:
            print(f"  User: {u.get('username')}, Role: {u.get('role')}, Email: {u.get('email')}, Sites: {u.get('assigned_sites')}")
    else:
        print("  Not a list:", users)

    print("\n--- DEPLOYED MOTORS ---")
    motors = results.get("List Motors", {}).get("data", [])
    if isinstance(motors, list):
        for m in motors:
            print(f"  Motor: {m.get('motor_id')}, Site: {m.get('site_id')}, Device: {m.get('assigned_device_id')}, Name: {m.get('name')}")
    else:
        print("  Not a list:", motors)

    print("\n--- DEPLOYED DEVICES ---")
    devices = results.get("List Devices", {}).get("data", [])
    if isinstance(devices, list):
        for d in devices:
            print(f"  Device: {d.get('device_id')}, Status: {d.get('status')}, Motor: {d.get('assigned_motor_id')}")

    print("\n--- DEPLOYED ALERTS ---")
    alerts = results.get("List Alerts", {}).get("data", [])
    if isinstance(alerts, list):
        for a in alerts:
            print(f"  Alert: {a.get('alert_id')}, Motor: {a.get('motor_id')}, Severity: {a.get('severity')}, State: {a.get('state')}")

    print("\n--- DEPLOYED WORK ORDERS ---")
    wos = results.get("List Work Orders", {}).get("data", [])
    if isinstance(wos, list):
        for w in wos:
            print(f"  WO: {w.get('order_id')}, Motor: {w.get('motor_id')}, Status: {w.get('status')}, AssignedTo: {w.get('assigned_to')}")

if __name__ == "__main__":
    run_backend_audit()

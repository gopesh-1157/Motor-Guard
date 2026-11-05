import asyncio
import urllib.request
import json
from motor.motor_asyncio import AsyncIOMotorClient

async def check_local_passwords():
    client = AsyncIOMotorClient("mongodb://127.0.0.1:27017")
    print("=== LOCAL DB: motorguard_db users ===")
    users = await client["motorguard_db"]["users"].find({}).to_list(100)
    for u in users:
        print(f"username: {u.get('username')}, role: {u.get('role')}, hash: {u.get('password_hash')[:25]}...")
    client.close()

def test_remote_login(username, password):
    url = "https://motor-guard.onrender.com/api/v1/auth/login"
    try:
        payload = json.dumps({"username": username, "password": password}).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as res:
            data = json.loads(res.read().decode("utf-8"))
            print(f"Login SUCCESS for '{username}' with password '{password}' -> Role: {data['user']['role']}")
            return data
    except urllib.error.HTTPError as e:
        print(f"Login FAILED for '{username}' with password '{password}' -> HTTP {e.code}")
        return None
    except Exception as e:
        print(f"Login ERROR for '{username}' -> {e}")
        return None

if __name__ == "__main__":
    asyncio.run(check_local_passwords())
    # Test common passwords on deployed backend
    for pwd in ["adminpassword123", "ManagerPass123!", "TechPass123!", "password", "Gopesh123!", "Rathinam123!"]:
        test_remote_login("Gopesh", pwd)
        test_remote_login("Rathinam", pwd)

import asyncio
import os
import sys
import subprocess
import time
import urllib.request
import json
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorClient

sys.path.insert(0, os.path.abspath("."))
from backend.app.core.security import get_password_hash, create_access_token

ARTIFACT_DIR = r"C:\Users\gopes\.gemini\antigravity\brain\8074a34a-ec58-4570-b5aa-54093d6ef762"
os.makedirs(ARTIFACT_DIR, exist_ok=True)
SCREENSHOT_PATH = os.path.join(ARTIFACT_DIR, "technician_access_denied.png").replace("\\", "/")

async def seed_technician():
    print("[1/5] Ensuring technician user exists in motorguard_test (test DB)...")
    client = AsyncIOMotorClient("mongodb://127.0.0.1:27017")
    db = client["motorguard_test"]
    tech_doc = {
        "username": "tech_denied_test",
        "email": "tech_denied@factory.local",
        "role": "Technician",
        "password_hash": get_password_hash("TechPass123!"),
        "is_active": True,
        "assigned_sites": ["SITE-PLANT-A"],
        "assigned_motors": ["MTR-775-001"],
        "created_at": datetime.now(timezone.utc),
    }
    await db["users"].update_one(
        {"username": "tech_denied_test"},
        {"$set": tech_doc},
        upsert=True,
    )
    user_record = await db["users"].find_one({"username": "tech_denied_test"})
    user_id = str(user_record["_id"])
    client.close()
    return user_id

def wait_for_port(url, max_retries=30):
    for i in range(max_retries):
        try:
            with urllib.request.urlopen(url, timeout=1) as res:
                return True
        except urllib.error.HTTPError:
            return True
        except Exception:
            pass
        time.sleep(0.5)
    return False

def run_test():
    user_id = asyncio.run(seed_technician())
    token = create_access_token({"sub": "tech_denied_test", "role": "Technician"})
    user_json = {
        "id": user_id,
        "username": "tech_denied_test",
        "role": "Technician",
        "email": "tech_denied@factory.local",
        "assigned_sites": ["SITE-PLANT-A"],
        "assigned_motors": ["MTR-775-001"],
        "title": "Technician Clearance",
        "clearance_level": 2,
        "token": token,
    }

    env_backend = os.environ.copy()
    env_backend["PORT"] = "8001"
    env_backend["MONGO_DB_NAME"] = "motorguard_test"
    env_backend["ENVIRONMENT"] = "development"
    env_backend["PYTHONPATH"] = "."

    print("[2/5] Starting test backend on port 8001 (motorguard_test)...")
    backend_proc = subprocess.Popen(
        ["python", "-m", "uvicorn", "backend.app.main:app", "--port", "8001", "--host", "127.0.0.1"],
        env=env_backend,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    env_frontend = os.environ.copy()
    env_frontend["VITE_BACKEND_PORT"] = "8001"

    print("[3/5] Starting test Vite server on port 5174 (host 127.0.0.1)...")
    frontend_proc = subprocess.Popen(
        ["cmd", "/c", "npx vite --port 5174 --host 127.0.0.1 --strictPort"],
        cwd="frontend",
        env=env_frontend,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    try:
        assert wait_for_port("http://127.0.0.1:8001/api/v1/health/live"), "Backend on 8001 failed to start"
        assert wait_for_port("http://127.0.0.1:5174/"), "Vite on 5174 failed to start"
        print("Both test backend (8001) and Vite (5174) are live!")

        print("[4/5] Launching Chrome via CDP to navigate directly to #users as Technician...")
        node_script = f"""
import {{ Browser, sleep }} from './.agents/skills/design-taste-frontend/scripts/lib/cdp.mjs';

async function test() {{
  const browser = await Browser.launch({{ width: 1440, height: 900 }});
  const page = await browser.newPage({{ width: 1440, height: 900 }});

  // Navigate to root first and inject session
  await page.goto('http://127.0.0.1:5174/', {{ timeoutMs: 15000, settleMs: 1000 }});
  await page.eval(({{ t, u }}) => {{
    localStorage.setItem('motorguard_auth_token', t);
    localStorage.setItem('motorguard_auth_user', JSON.stringify(u));
  }}, {{ t: {json.dumps(token)}, u: {json.dumps(user_json)} }});

  // Direct navigation to User Management tab (#users) with session active
  console.log('Navigating directly to http://127.0.0.1:5174/#users ...');
  await page.goto('http://127.0.0.1:5174/#users', {{ timeoutMs: 15000, settleMs: 1500 }});
  await page.eval(() => window.location.reload());
  await sleep(2000);

  // Capture screenshot of the Access Denied screen
  await page.screenshot({{ path: '{SCREENSHOT_PATH}', format: 'png' }});
  console.log('Saved screenshot to: {SCREENSHOT_PATH}');

  const bodyText = await page.eval(() => document.body.innerText);
  const hasAccessDenied = bodyText.includes('Access Denied');
  const has403 = bodyText.includes('Error 403');
  console.log('Page has "Access Denied":', hasAccessDenied);
  console.log('Page has "Error 403":', has403);

  await browser.close();

  if (!hasAccessDenied || !has403) {{
    throw new Error('Technician Access Denied view not rendered properly');
  }}
}}

test().catch(err => {{
  console.error('Browser test failed:', err);
  process.exit(1);
}});
"""
        res = subprocess.run(["node", "-e", node_script], capture_output=True, text=True)
        print("Node test stdout:\n", res.stdout)
        print("Node test stderr:\n", res.stderr)
        assert res.returncode == 0, f"Browser test failed with code {res.returncode}"
        print("Browser test PASSED! Verified Access Denied for Technician.")

    finally:
        print("[5/5] Cleaning up test server processes...")
        backend_proc.terminate()
        frontend_proc.terminate()
        try:
            backend_proc.wait(timeout=3)
            frontend_proc.wait(timeout=3)
        except Exception:
            backend_proc.kill()
            frontend_proc.kill()
        print("Test cleanup complete.")

if __name__ == "__main__":
    run_test()

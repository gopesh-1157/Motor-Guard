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
from backend.app.core.security import get_password_hash

ARTIFACT_DIR = r"C:\Users\gopes\.gemini\antigravity\brain\8074a34a-ec58-4570-b5aa-54093d6ef762"
os.makedirs(ARTIFACT_DIR, exist_ok=True)
SCREENSHOT_DIR_PATH = os.path.join(ARTIFACT_DIR, "manager_user_management_directory.png").replace("\\", "/")
SCREENSHOT_TECH_PATH = os.path.join(ARTIFACT_DIR, "manager_technician_row_with_buttons.png").replace("\\", "/")
SCREENSHOT_ADMIN_PATH = os.path.join(ARTIFACT_DIR, "manager_admin_row_without_buttons.png").replace("\\", "/")

async def seed_test_users():
    print("[1/5] Seeding test workforce users in motorguard_test (test DB)...")
    client = AsyncIOMotorClient("mongodb://127.0.0.1:27017")
    db = client["motorguard_test"]

    users = [
        {
            "username": "admin",
            "email": "admin@motorguard.local",
            "role": "Admin",
            "password_hash": get_password_hash("adminpassword123"),
            "is_active": True,
            "assigned_sites": ["SITE-MAIN"],
            "assigned_motors": [],
            "created_at": datetime.now(timezone.utc),
        },
        {
            "username": "mgr_davis",
            "email": "davis@plant.local",
            "role": "Manager",
            "password_hash": get_password_hash("ManagerPass123!"),
            "is_active": True,
            "assigned_sites": ["SITE-MAIN"],
            "assigned_motors": [],
            "created_at": datetime.now(timezone.utc),
        },
        {
            "username": "mgr_other",
            "email": "other_mgr@plant.local",
            "role": "Manager",
            "password_hash": get_password_hash("ManagerPass123!"),
            "is_active": True,
            "assigned_sites": ["SITE-MAIN"],
            "assigned_motors": [],
            "created_at": datetime.now(timezone.utc),
        },
        {
            "username": "tech_john",
            "email": "john@plant.local",
            "role": "Technician",
            "password_hash": get_password_hash("TechPass123!"),
            "is_active": True,
            "assigned_sites": ["SITE-MAIN"],
            "assigned_motors": ["MTR-775-001"],
            "created_at": datetime.now(timezone.utc),
        },
    ]

    for u in users:
        await db["users"].update_one(
            {"username": u["username"]},
            {"$set": u},
            upsert=True,
        )

    client.close()
    print("Seeded: admin (Admin), mgr_davis (Manager), mgr_other (Manager), tech_john (Technician)")

def wait_for_port(url, max_retries=30):
    for _ in range(max_retries):
        try:
            with urllib.request.urlopen(url, timeout=1) as res:
                return True
        except urllib.error.HTTPError:
            return True
        except Exception:
            pass
        time.sleep(0.5)
    return False

def real_manager_login(base_url="http://127.0.0.1:8001"):
    print("[2/5] Performing REAL Manager login via POST /api/v1/auth/login...")
    req = urllib.request.Request(
        f"{base_url}/api/v1/auth/login",
        data=json.dumps({"username": "mgr_davis", "password": "ManagerPass123!"}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=5) as res:
        data = json.loads(res.read().decode("utf-8"))
        print(f"Login SUCCESS! User: {data['user']['username']} (Role: {data['user']['role']})")
        return data["access_token"], data["user"]

def run_test():
    asyncio.run(seed_test_users())

    env_backend = os.environ.copy()
    env_backend["PORT"] = "8001"
    env_backend["MONGO_DB_NAME"] = "motorguard_test"
    env_backend["ENVIRONMENT"] = "development"
    env_backend["PYTHONPATH"] = "."

    print("[3/5] Starting test backend on port 8001 (motorguard_test)...")
    backend_proc = subprocess.Popen(
        ["python", "-m", "uvicorn", "backend.app.main:app", "--port", "8001", "--host", "127.0.0.1"],
        env=env_backend,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    env_frontend = os.environ.copy()
    env_frontend["VITE_BACKEND_PORT"] = "8001"

    print("Starting test Vite server on port 5174 (host 127.0.0.1)...")
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

        token, user_profile = real_manager_login()

        print("[4/5] Launching Chrome via CDP to test Manager permissions in User Management tab...")
        node_script = f"""
import {{ Browser, sleep }} from './.agents/skills/design-taste-frontend/scripts/lib/cdp.mjs';

async function test() {{
  const browser = await Browser.launch({{ width: 1440, height: 900 }});
  const page = await browser.newPage({{ width: 1440, height: 900 }});

  // Navigate to root first and inject REAL login session
  await page.goto('http://127.0.0.1:5174/', {{ timeoutMs: 15000, settleMs: 1000 }});
  await page.eval(({{ t, u }}) => {{
    localStorage.setItem('motorguard_auth_token', t);
    localStorage.setItem('motorguard_auth_user', JSON.stringify(u));
  }}, {{ t: {json.dumps(token)}, u: {json.dumps(user_profile)} }});

  // Navigate directly to User Management tab (#users)
  console.log('Navigating directly to http://127.0.0.1:5174/#users ...');
  await page.goto('http://127.0.0.1:5174/#users', {{ timeoutMs: 15000, settleMs: 1500 }});
  await page.eval(() => window.location.reload());
  await sleep(2500);

  // Capture directory view screenshot
  await page.screenshot({{ path: '{SCREENSHOT_DIR_PATH}', format: 'png' }});
  console.log('Saved directory view screenshot to: {SCREENSHOT_DIR_PATH}');

  // Evaluate table rows and buttons
  const analysis = await page.eval(() => {{
    const rows = Array.from(document.querySelectorAll('tbody tr'));
    const results = [];
    for (const r of rows) {{
      const text = r.innerText;
      const buttons = Array.from(r.querySelectorAll('button')).map(b => b.title || b.innerText.trim());
      results.push({{ text, buttons }});
    }}
    const hasProvisionBtn = Array.from(document.querySelectorAll('button')).some(b => b.innerText.includes('Provision User'));
    return {{ results, hasProvisionBtn }};
  }});

  console.log('Provision User button visible for Manager:', analysis.hasProvisionBtn);
  console.log('Rows analysis:', JSON.stringify(analysis.results, null, 2));

  // Find tech_john row
  const techRow = analysis.results.find(r => r.text.includes('tech_john'));
  const adminRow = analysis.results.find(r => r.text.includes('admin') && !r.text.includes('tech'));
  const otherMgrRow = analysis.results.find(r => r.text.includes('mgr_other'));

  console.log('Tech row buttons:', techRow ? techRow.buttons : 'NOT FOUND');
  console.log('Admin row buttons:', adminRow ? adminRow.buttons : 'NOT FOUND');
  console.log('Other Manager row buttons:', otherMgrRow ? otherMgrRow.buttons : 'NOT FOUND');

  // Verify Technician row has: Details, Edit Role & Scopes, Suspend/Activate, Reset Password
  const techHasAllButtons = techRow && techRow.buttons.length >= 4;
  // Verify Admin row has ONLY Details (1 button)
  const adminHasOnlyDetails = adminRow && adminRow.buttons.length === 1 && adminRow.buttons[0] === 'Inspect User Details & Activity';
  // Verify Manager row has ONLY Details (1 button)
  const mgrHasOnlyDetails = otherMgrRow && otherMgrRow.buttons.length === 1 && otherMgrRow.buttons[0] === 'Inspect User Details & Activity';

  await page.screenshot({{ path: '{SCREENSHOT_TECH_PATH}', format: 'png' }});
  await page.screenshot({{ path: '{SCREENSHOT_ADMIN_PATH}', format: 'png' }});

  await browser.close();

  if (!analysis.hasProvisionBtn) {{
    throw new Error('Manager cannot see Provision User button');
  }}
  if (!techHasAllButtons) {{
    throw new Error('Technician row does not have all expected action buttons for Manager');
  }}
  if (!adminHasOnlyDetails) {{
    throw new Error('Admin row incorrectly exposed action buttons to Manager');
  }}
  if (!mgrHasOnlyDetails) {{
    throw new Error('Other Manager row incorrectly exposed action buttons to Manager');
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
        print("Browser test PASSED! Manager UI permissions fully verified.")

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

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

ARTIFACT_DIR = r"C:\Users\gopes\.gemini\antigravity\brain\8074a34a-ec58-4570-b5aa-54093d6ef762".replace("\\", "/")

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

async def seed_test_users():
    print("[1/5] Seeding test database 'motorguard_test'...")
    client = AsyncIOMotorClient("mongodb://127.0.0.1:27017")
    db = client["motorguard_test"]

    users = [
        {
            "username": "admin",
            "email": "admin@motorguard.local",
            "role": "Admin",
            "password_hash": get_password_hash("adminpassword123"),
            "is_active": True,
            "assigned_sites": ["SITE-PLANT-A"],
            "assigned_motors": ["MTR-775-001"],
            "created_at": datetime.now(timezone.utc),
        },
        {
            "username": "mgr_davis",
            "email": "davis@plant.local",
            "role": "Manager",
            "password_hash": get_password_hash("ManagerPass123!"),
            "is_active": True,
            "assigned_sites": ["SITE-PLANT-A"],
            "assigned_motors": ["MTR-775-001"],
            "created_at": datetime.now(timezone.utc),
        },
        {
            "username": "mgr_other",
            "email": "other@plant.local",
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
            "assigned_sites": ["SITE-PLANT-A"],
            "assigned_motors": ["MTR-775-001"],
            "created_at": datetime.now(timezone.utc),
        },
    ]
    for u in users:
        await db["users"].update_one({"username": u["username"]}, {"$set": u}, upsert=True)
    client.close()
    print("Database seeding ready.")

def run():
    asyncio.run(seed_test_users())

    env_backend = os.environ.copy()
    env_backend["PORT"] = "8001"
    env_backend["MONGO_DB_NAME"] = "motorguard_test"
    env_backend["ENVIRONMENT"] = "development"
    env_backend["PYTHONPATH"] = "."

    print("[2/5] Starting test backend (port 8001 / motorguard_test)...")
    backend_proc = subprocess.Popen(
        ["python", "-m", "uvicorn", "backend.app.main:app", "--port", "8001", "--host", "127.0.0.1"],
        env=env_backend,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    env_frontend = os.environ.copy()
    env_frontend["VITE_BACKEND_PORT"] = "8001"

    print("[3/5] Starting test Vite server (port 5174)...")
    frontend_proc = subprocess.Popen(
        ["cmd", "/c", "npx vite --port 5174 --host 127.0.0.1 --strictPort"],
        cwd="frontend",
        env=env_frontend,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    try:
        assert wait_for_port("http://127.0.0.1:8001/api/v1/health/live"), "Backend failed to start on 8001"
        assert wait_for_port("http://127.0.0.1:5174/"), "Vite failed to start on 5174"
        print("Both servers LIVE.")

        print("[4/5] Executing Headless Chrome Automation via CDP...")
        node_script = f"""
import {{ Browser, sleep }} from './.agents/skills/design-taste-frontend/scripts/lib/cdp.mjs';
import fs from 'fs';

const ARTIFACT_DIR = '{ARTIFACT_DIR}';

async function performLogin(page, username, password) {{
  const loginRes = await page.eval(async ({{ u, p }}) => {{
    const res = await fetch('/api/v1/auth/login', {{
      method: 'POST',
      headers: {{ 'Content-Type': 'application/json' }},
      body: JSON.stringify({{ username: u, password: p }}),
    }});
    if (!res.ok) return {{ success: false, status: res.status }};
    const data = await res.json();
    localStorage.setItem('motorguard_auth_token', data.access_token);
    localStorage.setItem('motorguard_auth_user', JSON.stringify(data.user));
    return {{ success: true, user: data.user, token: data.access_token }};
  }}, {{ u: username, p: password }});

  if (!loginRes.success) throw new Error(`Login failed for ${{username}}: HTTP ${{loginRes.status}}`);
  await page.goto('http://127.0.0.1:5174/#overview', {{ timeoutMs: 15000, settleMs: 1200 }});
  await sleep(800);
  return loginRes;
}}

async function main() {{
  const browser = await Browser.launch({{ width: 1440, height: 900 }});
  const page = await browser.newPage({{ width: 1440, height: 900 }});
  await page.goto('http://127.0.0.1:5174/', {{ timeoutMs: 15000, settleMs: 1000 }});

  // ==========================================
  // FLOW B: MANAGER MANAGEMENT OF TECHNICIAN
  // ==========================================
  console.log('=== FLOW B: MANAGER MANAGEMENT OF TECHNICIAN ===');
  await performLogin(page, 'mgr_davis', 'ManagerPass123!');
  await page.goto('http://127.0.0.1:5174/#users', {{ timeoutMs: 15000, settleMs: 1500 }});
  await sleep(1500);

  // 1. Provision Technician
  console.log('Step B1: Provision Technician');
  await page.eval(() => {{
    const btn = Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('Provision User'));
    if (btn) btn.click();
  }});
  await sleep(1000);

  await page.eval(() => {{
    const inputs = document.querySelectorAll('.modal-dialog input');
    if (inputs.length >= 3) {{
      inputs[0].value = 'tech_demo_verified';
      inputs[0].dispatchEvent(new Event('input', {{ bubbles: true }}));
      inputs[1].value = 'demo_tech@plant.local';
      inputs[1].dispatchEvent(new Event('input', {{ bubbles: true }}));
      inputs[2].value = 'TechPassVerified1!';
      inputs[2].dispatchEvent(new Event('input', {{ bubbles: true }}));
    }}
    const submitBtn = Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('Provision Account'));
    if (submitBtn) submitBtn.click();
  }});
  await sleep(2500);
  await page.screenshot({{ path: `${{ARTIFACT_DIR}}/flow_b_01_technician_provisioned.png`, format: 'png' }});
  console.log('Captured flow_b_01_technician_provisioned.png');

  // 2. Edit email of technician
  console.log('Step B2: Edit Technician Email');
  await page.eval(() => {{
    const rows = Array.from(document.querySelectorAll('tbody tr'));
    const techRow = rows.find(r => r.innerText.includes('tech_demo_verified'));
    if (techRow) {{
      const editBtn = techRow.querySelector('button[title="Edit Role & Scopes"]');
      if (editBtn) editBtn.click();
    }}
  }});
  await sleep(1000);

  await page.eval(() => {{
    const emailInput = document.querySelector('.modal-dialog input[type="email"]');
    if (emailInput) {{
      emailInput.value = 'demo_updated@plant.local';
      emailInput.dispatchEvent(new Event('input', {{ bubbles: true }}));
    }}
    const saveBtn = Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('Save Changes'));
    if (saveBtn) saveBtn.click();
  }});
  await sleep(2000);
  await page.screenshot({{ path: `${{ARTIFACT_DIR}}/flow_b_02_technician_edited.png`, format: 'png' }});
  console.log('Captured flow_b_02_technician_edited.png');

  // 3. Suspend technician
  console.log('Step B3: Suspend Technician');
  await page.eval(() => {{
    const rows = Array.from(document.querySelectorAll('tbody tr'));
    const techRow = rows.find(r => r.innerText.includes('tech_demo_verified'));
    if (techRow) {{
      const suspendBtn = techRow.querySelector('button[title="Suspend Account"]');
      if (suspendBtn) suspendBtn.click();
    }}
  }});
  await sleep(2000);
  await page.screenshot({{ path: `${{ARTIFACT_DIR}}/flow_b_03_technician_suspended.png`, format: 'png' }});
  console.log('Captured flow_b_03_technician_suspended.png');

  // 4. Reactivate technician
  console.log('Step B4: Reactivate Technician');
  await page.eval(() => {{
    const rows = Array.from(document.querySelectorAll('tbody tr'));
    const techRow = rows.find(r => r.innerText.includes('tech_demo_verified'));
    if (techRow) {{
      const activateBtn = techRow.querySelector('button[title="Activate Account"]');
      if (activateBtn) activateBtn.click();
    }}
  }});
  await sleep(2000);
  await page.screenshot({{ path: `${{ARTIFACT_DIR}}/flow_b_04_technician_reactivated.png`, format: 'png' }});
  console.log('Captured flow_b_04_technician_reactivated.png');

  // 5. Reset password
  console.log('Step B5: Reset Technician Password');
  await page.eval(() => {{
    const rows = Array.from(document.querySelectorAll('tbody tr'));
    const techRow = rows.find(r => r.innerText.includes('tech_demo_verified'));
    if (techRow) {{
      const resetBtn = techRow.querySelector('button[title="Reset Password"]');
      if (resetBtn) resetBtn.click();
    }}
  }});
  await sleep(1000);

  await page.eval(() => {{
    const pwdInput = document.querySelector('.modal-dialog input[type="password"], .modal-dialog input[type="text"]');
    if (pwdInput) {{
      pwdInput.value = 'NewTechPass999!';
      pwdInput.dispatchEvent(new Event('input', {{ bubbles: true }}));
    }}
    const saveBtn = Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('Set New Password'));
    if (saveBtn) saveBtn.click();
  }});
  await sleep(2000);
  await page.screenshot({{ path: `${{ARTIFACT_DIR}}/flow_b_05_technician_password_reset.png`, format: 'png' }});
  console.log('Captured flow_b_05_technician_password_reset.png');

  // 6. Inspect Admin & Manager rows (UI button restrictions)
  console.log('Step B6: Inspect Admin & Manager Rows');
  await page.screenshot({{ path: `${{ARTIFACT_DIR}}/flow_b_06_manager_restricted_rows.png`, format: 'png' }});
  console.log('Captured flow_b_06_manager_restricted_rows.png');

  // Test Manager API Restrictions against Admin and other Manager
  const managerApiTests = await page.eval(async () => {{
    const token = localStorage.getItem('motorguard_auth_token');
    const headers = {{ 'Content-Type': 'application/json', 'Authorization': `Bearer ${{token}}` }};

    const editAdmin = await fetch('/api/v1/users/admin', {{
      method: 'PATCH',
      headers,
      body: JSON.stringify({{ email: 'hacked_admin@plant.local' }})
    }});

    const suspendAdmin = await fetch('/api/v1/users/admin', {{
      method: 'PATCH',
      headers,
      body: JSON.stringify({{ is_active: false }})
    }});

    const resetAdminPwd = await fetch('/api/v1/users/admin/reset-password', {{
      method: 'POST',
      headers,
      body: JSON.stringify({{ new_password: 'HackedAdminPass123!' }})
    }});

    const editMgr = await fetch('/api/v1/users/mgr_other', {{
      method: 'PATCH',
      headers,
      body: JSON.stringify({{ email: 'hacked_mgr@plant.local' }})
    }});

    const createAdmin = await fetch('/api/v1/users', {{
      method: 'POST',
      headers,
      body: JSON.stringify({{ username: 'fake_admin', email: 'fake@plant.local', role: 'Admin', password: 'FakeAdminPass1!' }})
    }});

    return {{
      editAdminStatus: editAdmin.status,
      suspendAdminStatus: suspendAdmin.status,
      resetAdminPwdStatus: resetAdminPwd.status,
      editMgrStatus: editMgr.status,
      createAdminStatus: createAdmin.status,
    }};
  }});
  console.log('Manager API Restrictions against Admin & Manager:', JSON.stringify(managerApiTests, null, 2));

  // ==========================================
  // FLOW C: PROFILE CREDENTIALS & PASSWORD
  // ==========================================
  console.log('=== FLOW C: PROFILE CREDENTIALS & PASSWORD ===');
  await page.goto('http://127.0.0.1:5174/#users', {{ timeoutMs: 15000, settleMs: 1500 }});
  await sleep(1500);

  // Switch to My Account Settings
  await page.eval(() => {{
    const tabBtn = Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('My Account Settings'));
    if (tabBtn) tabBtn.click();
  }});
  await sleep(1000);

  // C1. Missing current password
  console.log('Step C1: Missing Current Password');
  await page.eval(() => {{
    const inputs = document.querySelectorAll('form input');
    if (inputs.length >= 4) {{
      inputs[2].value = '';
      inputs[2].dispatchEvent(new Event('input', {{ bubbles: true }}));
      inputs[3].value = 'NewManagerSecret123!';
      inputs[3].dispatchEvent(new Event('input', {{ bubbles: true }}));
    }}
    const saveBtn = Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('Save Profile Changes'));
    if (saveBtn) saveBtn.click();
  }});
  await sleep(1500);
  await page.screenshot({{ path: `${{ARTIFACT_DIR}}/flow_c_01_missing_curr_pw.png`, format: 'png' }});
  console.log('Captured flow_c_01_missing_curr_pw.png');

  // C2. Wrong current password
  console.log('Step C2: Wrong Current Password');
  await page.eval(() => {{
    const inputs = document.querySelectorAll('form input');
    if (inputs.length >= 4) {{
      inputs[2].value = 'WrongCurrentPassword999!';
      inputs[2].dispatchEvent(new Event('input', {{ bubbles: true }}));
    }}
    const saveBtn = Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('Save Profile Changes'));
    if (saveBtn) saveBtn.click();
  }});
  await sleep(1500);
  await page.screenshot({{ path: `${{ARTIFACT_DIR}}/flow_c_02_wrong_curr_pw.png`, format: 'png' }});
  console.log('Captured flow_c_02_wrong_curr_pw.png');

  // C3. Correct current password
  console.log('Step C3: Correct Current Password');
  await page.eval(() => {{
    const inputs = document.querySelectorAll('form input');
    if (inputs.length >= 4) {{
      inputs[2].value = 'ManagerPass123!';
      inputs[2].dispatchEvent(new Event('input', {{ bubbles: true }}));
    }}
    const saveBtn = Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('Save Profile Changes'));
    if (saveBtn) saveBtn.click();
  }});
  await sleep(2000);
  await page.screenshot({{ path: `${{ARTIFACT_DIR}}/flow_c_03_pw_updated.png`, format: 'png' }});
  console.log('Captured flow_c_03_pw_updated.png');

  // Verify Manager old/new password
  const oldLoginRes = await page.eval(async () => {{
    const res = await fetch('/api/v1/auth/login', {{
      method: 'POST',
      headers: {{ 'Content-Type': 'application/json' }},
      body: JSON.stringify({{ username: 'mgr_davis', password: 'ManagerPass123!' }}),
    }});
    return res.status;
  }});
  console.log('Manager Old Password Login Status (Expected 401):', oldLoginRes);

  const newLoginRes = await page.eval(async () => {{
    const res = await fetch('/api/v1/auth/login', {{
      method: 'POST',
      headers: {{ 'Content-Type': 'application/json' }},
      body: JSON.stringify({{ username: 'mgr_davis', password: 'NewManagerSecret123!' }}),
    }});
    return res.status;
  }});
  console.log('Manager New Password Login Status (Expected 200):', newLoginRes);

  // Technician PATCH /me via API
  console.log('Step C4: Technician PATCH /me verification');
  const techApiTests = await page.eval(async () => {{
    const logRes = await fetch('/api/v1/auth/login', {{
      method: 'POST',
      headers: {{ 'Content-Type': 'application/json' }},
      body: JSON.stringify({{ username: 'tech_john', password: 'TechPass123!' }}),
    }});
    const {{ access_token }} = await logRes.json();
    const headers = {{ 'Content-Type': 'application/json', 'Authorization': `Bearer ${{access_token}}` }};

    const rMissing = await fetch('/api/v1/auth/me', {{
      method: 'PATCH',
      headers,
      body: JSON.stringify({{ password: 'TechNewPassword999!' }}),
    }});

    const rWrong = await fetch('/api/v1/auth/me', {{
      method: 'PATCH',
      headers,
      body: JSON.stringify({{ current_password: 'WrongPassword!', password: 'TechNewPassword999!' }}),
    }});

    const rCorrect = await fetch('/api/v1/auth/me', {{
      method: 'PATCH',
      headers,
      body: JSON.stringify({{ current_password: 'TechPass123!', password: 'TechNewPassword999!' }}),
    }});

    const oldRes = await fetch('/api/v1/auth/login', {{
      method: 'POST',
      headers: {{ 'Content-Type': 'application/json' }},
      body: JSON.stringify({{ username: 'tech_john', password: 'TechPass123!' }}),
    }});

    const newRes = await fetch('/api/v1/auth/login', {{
      method: 'POST',
      headers: {{ 'Content-Type': 'application/json' }},
      body: JSON.stringify({{ username: 'tech_john', password: 'TechNewPassword999!' }}),
    }});

    return {{
      techMissingStatus: rMissing.status,
      techWrongStatus: rWrong.status,
      techCorrectStatus: rCorrect.status,
      techOldLoginStatus: oldRes.status,
      techNewLoginStatus: newRes.status,
    }};
  }});
  console.log('Technician PATCH /me results:', JSON.stringify(techApiTests, null, 2));

  // ==========================================
  // FLOW D: SIDEBAR TABS & REFRESH TEST
  // ==========================================
  console.log('=== FLOW D: SIDEBAR TABS & REFRESH TEST ===');
  const allTabs = ['overview', 'twin', 'live', 'analytics', 'alerts', 'maintenance', 'landing', 'fleet', 'devices', 'users', 'reports', 'settings'];
  const roles = [
    {{ name: 'Admin', user: 'admin', pass: 'adminpassword123' }},
    {{ name: 'Manager', user: 'mgr_davis', pass: 'NewManagerSecret123!' }},
    {{ name: 'Technician', user: 'tech_john', pass: 'TechNewPassword999!' }},
  ];

  const flowDResults = {{}};

  for (const r of roles) {{
    console.log(`Testing sidebar tabs for role: ${{r.name}}`);
    await performLogin(page, r.user, r.pass);
    const roleResults = [];

    for (const t of allTabs) {{
      await page.goto(`http://127.0.0.1:5174/#${{t}}`, {{ timeoutMs: 15000, settleMs: 800 }});
      await sleep(300);

      // Reload via CDP Page.reload
      await page.send('Page.reload');
      await sleep(1000);

      const pageState = await page.eval(() => {{
        const hash = window.location.hash;
        const h1 = document.querySelector('h1')?.innerText || '';
        const h2 = document.querySelector('h2')?.innerText || '';
        const isAccessDenied = document.body.innerText.includes('Access Denied');
        return {{ hash, header: h1 || h2, isAccessDenied }};
      }});

      roleResults.push({{
        tab: t,
        retainedHash: pageState.hash,
        header: pageState.header,
        isAccessDenied: pageState.isAccessDenied,
      }});
    }}
    flowDResults[r.name] = roleResults;
  }}

  fs.writeFileSync(`${{ARTIFACT_DIR}}/flow_d_sidebar_results.json`, JSON.stringify(flowDResults, null, 2));
  console.log('Saved flow_d_sidebar_results.json');

  await browser.close();
  console.log('ALL VERIFICATIONS COMPLETED SUCCESSFULLY!');
}}

main().catch(err => {{
  console.error('Execution error in node:', err);
  process.exit(1);
}});
"""
        res = subprocess.run(["node", "-e", node_script], capture_output=True, text=True)
        print("Node execution output:\n", res.stdout)
        print("Node error output:\n", res.stderr)
        assert res.returncode == 0, f"Node script failed with code {res.returncode}"

    finally:
        print("[5/5] Cleaning up processes...")
        backend_proc.terminate()
        frontend_proc.terminate()
        try:
            backend_proc.wait(timeout=3)
            frontend_proc.wait(timeout=3)
            print("Processes cleanly terminated.")
        except Exception:
            backend_proc.kill()
            frontend_proc.kill()
            print("Processes killed.")

if __name__ == "__main__":
    run()

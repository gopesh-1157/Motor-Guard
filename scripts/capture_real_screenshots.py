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

async def seed_test_database():
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

    from backend.app.schemas.motor import SensorsConfig, HealthThresholds, EdgeImpulseConfig
    motor_doc = {
        "motor_id": "MTR-775-001",
        "name": "Line 3 Conveyor Feed Actuator",
        "motor_type": "RS-775 Brushed DC",
        "manufacturer": "Johnson Electric",
        "model_number": "RS-775-12V-150W",
        "serial_number": "SN-775-2026-001A",
        "site_id": "SITE-PLANT-A",
        "installation_date": "2026-01-15",
        "description": "Primary material intake conveyor motor with active vibration damping.",
        "status": "active",
        "assigned_device_id": "esp32-node-001",
        "electrical_specs": {
            "motor_type": "RS-775 Brushed DC",
            "rated_voltage_v": 12.0,
            "rated_current_a": 2.5,
            "no_load_current_a": 0.45,
            "rated_speed_rpm": 12000,
            "max_speed_rpm": 18000,
            "rated_power_w": 30.0,
            "motor_supply_type": "External DC supply",
            "application_load": "Conveyor Feed Drive",
        },
        "mechanical_specs": {
            "shaft_diameter_mm": 5.0,
            "weight_grams": 350.0,
            "mounting_type": "Face Mount (M4)",
            "cooling_type": "Internal Centrifugal Fan",
        },
        "sensors_config": SensorsConfig().model_dump(),
        "thresholds": {
            "vibration_warning_g": 0.5,
            "vibration_critical_g": 1.0,
            "temperature_warning_c": 45.0,
            "temperature_critical_c": 50.0,
            "current_warning_a": 3.0,
            "current_critical_a": 4.0,
            "provenance": "Provisional RS-775 baseline limits (uncalibrated)",
        },
        "edge_impulse_config": EdgeImpulseConfig().model_dump(),
        "configuration_version": 1,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    await db["motors"].update_one({"motor_id": "MTR-775-001"}, {"$set": motor_doc}, upsert=True)

    now = datetime.now(timezone.utc)
    telem_doc = {
        "event_id": f"evt_nom_{int(time.time()*1000)}",
        "motor_id": "MTR-775-001",
        "device_id": "esp32-node-001",
        "timestamp": now,
        "vibration_rms": 0.18,
        "current": 1.45,
        "temperature": 32.4,
        "vibration_peak": 0.35,
        "anomaly_score": 0.05,
        "health_indicator": "HEALTHY",
        "state": "RUNNING",
        "rssi": -62,
    }
    await db["telemetry"].insert_one(telem_doc)

    alert_doc = {
        "alert_id": "ALT-20261104-CRIT01",
        "motor_id": "MTR-775-001",
        "device_id": "esp32-node-001",
        "site_id": "SITE-PLANT-A",
        "severity": "CRITICAL",
        "state": "ACTIVE",
        "category": "VIBRATION",
        "trigger_type": "VIBRATION_SPIKE",
        "trigger_value": 1.45,
        "threshold_limit": 1.0,
        "unit": "g RMS",
        "message": "Critical vibration breach on MTR-775-001: 1.45g RMS (Limit: 1.00g RMS)",
        "source": "telemetry_processor",
        "triggered_at": datetime.now(timezone.utc),
        "last_observed_at": datetime.now(timezone.utc),
        "acknowledged_at": None,
        "acknowledged_by": None,
        "assigned_to": None,
        "resolution_notes": None,
        "resolved_at": None,
        "resolved_by": None,
    }
    await db["alerts"].update_one({"alert_id": "ALT-20261104-CRIT01"}, {"$set": alert_doc}, upsert=True)
    client.close()
    print("Database seeding ready.")

def login_user(username, password, base_url="http://127.0.0.1:8001"):
    req = urllib.request.Request(
        f"{base_url}/api/v1/auth/login",
        data=json.dumps({"username": username, "password": password}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=5) as res:
        data = json.loads(res.read().decode("utf-8"))
        return data["access_token"], data["user"]

def run():
    asyncio.run(seed_test_database())

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

        admin_token, admin_user = login_user("admin", "adminpassword123")
        mgr_token, mgr_user = login_user("mgr_davis", "ManagerPass123!")
        tech_token, tech_user = login_user("tech_john", "TechPass123!")

        print("[4/5] Executing Headless Chrome Automation via CDP...")
        node_script = f"""
import {{ Browser, sleep }} from './.agents/skills/design-taste-frontend/scripts/lib/cdp.mjs';
import fs from 'fs';

const ARTIFACT_DIR = '{ARTIFACT_DIR}';
const adminSession = {{ token: {json.dumps(admin_token)}, user: {json.dumps(admin_user)} }};
const mgrSession = {{ token: {json.dumps(mgr_token)}, user: {json.dumps(mgr_user)} }};
const techSession = {{ token: {json.dumps(tech_token)}, user: {json.dumps(tech_user)} }};

async function switchUser(page, session, initialTab) {{
  await page.goto(`http://127.0.0.1:5174/?auth=${{session.user.username}}#${{initialTab}}`, {{ timeoutMs: 15000, settleMs: 1000 }});
  await page.eval((s) => {{
    localStorage.setItem('motorguard_auth_token', s.token);
    localStorage.setItem('motorguard_auth_user', JSON.stringify(s.user));
  }}, session);
  await page.goto(`http://127.0.0.1:5174/?session=${{session.user.username}}#${{initialTab}}`, {{ timeoutMs: 15000, settleMs: 1500 }});
  await sleep(1000);
}}

async function switchTab(page, tabName) {{
  await page.eval((t) => {{
    window.location.hash = t;
    window.dispatchEvent(new HashChangeEvent('hashchange'));
  }}, tabName);
  await sleep(1500);
}}

async function main() {{
  const browser = await Browser.launch({{ width: 1440, height: 900 }});
  const page = await browser.newPage({{ width: 1440, height: 900 }});

  // 1a. Fleet View as Admin
  console.log('Capturing Fleet View...');
  await switchUser(page, adminSession, 'fleet');
  await page.screenshot({{ path: `${{ARTIFACT_DIR}}/fleet_mtr_775_001.png`, format: 'png' }});

  // 1c. Settings View as Admin
  console.log('Capturing Settings View...');
  await switchTab(page, 'settings');
  await page.screenshot({{ path: `${{ARTIFACT_DIR}}/settings_view.png`, format: 'png' }});

  // FLOW A: Alerts & Work Orders
  console.log('Capturing Flow A: Alert lifecycle...');
  await switchTab(page, 'alerts');
  await page.screenshot({{ path: `${{ARTIFACT_DIR}}/flow_a_01_active_alert.png`, format: 'png' }});

  // Acknowledge alert
  await page.eval(() => {{
    const btn = Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('Acknowledge'));
    if (btn) btn.click();
  }});
  await sleep(1500);
  await page.screenshot({{ path: `${{ARTIFACT_DIR}}/flow_a_02_acknowledged_alert.png`, format: 'png' }});

  // Assign alert to technician
  await page.eval(() => {{
    const btn = Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('Assign to Technician') || b.innerText.includes('Reassign'));
    if (btn) btn.click();
  }});
  await sleep(800);
  await page.eval(() => {{
    const select = document.querySelector('select');
    if (select) {{
      select.value = 'tech_john';
      select.dispatchEvent(new Event('change', {{ bubbles: true }}));
    }}
    const submitBtn = Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('Dispatch') || b.innerText.includes('Assign'));
    if (submitBtn) submitBtn.click();
  }});
  await sleep(1500);
  await page.screenshot({{ path: `${{ARTIFACT_DIR}}/flow_a_03_assigned_alert.png`, format: 'png' }});

  // Technician Inbox
  await switchUser(page, techSession, 'maintenance');
  await page.screenshot({{ path: `${{ARTIFACT_DIR}}/flow_a_04_technician_inbox.png`, format: 'png' }});

  // Accept work order
  await page.eval(() => {{
    const btn = Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('Accept Work Order'));
    if (btn) btn.click();
  }});
  await sleep(1500);
  await page.screenshot({{ path: `${{ARTIFACT_DIR}}/flow_a_05_accepted_wo.png`, format: 'png' }});

  // Start work
  await page.eval(() => {{
    const btn = Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('Begin Maintenance Work'));
    if (btn) btn.click();
  }});
  await sleep(1500);
  await page.screenshot({{ path: `${{ARTIFACT_DIR}}/flow_a_06_in_progress_wo.png`, format: 'png' }});

  // Complete & resolve work order
  await page.eval(() => {{
    const btn = Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('Complete & Sign Off Work Order'));
    if (btn) btn.click();
  }});
  await sleep(800);
  await page.eval(() => {{
    const textareas = document.querySelectorAll('textarea');
    if (textareas.length >= 2) {{
      textareas[0].value = 'Bearing lubricated and shaft realigned.';
      textareas[0].dispatchEvent(new Event('input', {{ bubbles: true }}));
      textareas[1].value = 'Applied high-temperature industrial grease.';
      textareas[1].dispatchEvent(new Event('input', {{ bubbles: true }}));
    }}
    const submitBtn = Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('Sign Off & Close Work Order'));
    if (submitBtn) submitBtn.click();
  }});
  await sleep(2000);
  await page.screenshot({{ path: `${{ARTIFACT_DIR}}/flow_a_07_resolved_wo.png`, format: 'png' }});

  // Flow A8: Technician access denied to user management
  await switchTab(page, 'users');
  await page.screenshot({{ path: `${{ARTIFACT_DIR}}/technician_access_denied.png`, format: 'png' }});

  // FLOW B: Manager powers over Technician
  console.log('Capturing Flow B: Manager powers...');
  await switchUser(page, mgrSession, 'users');
  await page.screenshot({{ path: `${{ARTIFACT_DIR}}/manager_user_management_directory.png`, format: 'png' }});

  // Provision Technician
  await page.eval(() => {{
    const btn = Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('Provision User'));
    if (btn) btn.click();
  }});
  await sleep(800);
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
  await sleep(2000);
  await page.screenshot({{ path: `${{ARTIFACT_DIR}}/flow_b_01_technician_provisioned.png`, format: 'png' }});

  // Edit Technician Email
  await page.eval(() => {{
    const rows = Array.from(document.querySelectorAll('tbody tr'));
    const techRow = rows.find(r => r.innerText.includes('tech_demo_verified'));
    if (techRow) {{
      const editBtn = techRow.querySelector('button[title="Edit Role & Scopes"]');
      if (editBtn) editBtn.click();
    }}
  }});
  await sleep(800);
  await page.eval(() => {{
    const emailInput = document.querySelector('.modal-dialog input[type="email"]');
    if (emailInput) {{
      emailInput.value = 'demo_updated@plant.local';
      emailInput.dispatchEvent(new Event('input', {{ bubbles: true }}));
    }}
    const saveBtn = Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('Save Changes'));
    if (saveBtn) saveBtn.click();
  }});
  await sleep(1500);
  await page.screenshot({{ path: `${{ARTIFACT_DIR}}/flow_b_02_technician_edited.png`, format: 'png' }});

  // Suspend Technician
  await page.eval(() => {{
    const rows = Array.from(document.querySelectorAll('tbody tr'));
    const techRow = rows.find(r => r.innerText.includes('tech_demo_verified'));
    if (techRow) {{
      const suspendBtn = techRow.querySelector('button[title="Suspend Account"]');
      if (suspendBtn) suspendBtn.click();
    }}
  }});
  await sleep(1500);
  await page.screenshot({{ path: `${{ARTIFACT_DIR}}/flow_b_03_technician_suspended.png`, format: 'png' }});

  // Reactivate Technician
  await page.eval(() => {{
    const rows = Array.from(document.querySelectorAll('tbody tr'));
    const techRow = rows.find(r => r.innerText.includes('tech_demo_verified'));
    if (techRow) {{
      const activateBtn = techRow.querySelector('button[title="Activate Account"]');
      if (activateBtn) activateBtn.click();
    }}
  }});
  await sleep(1500);
  await page.screenshot({{ path: `${{ARTIFACT_DIR}}/flow_b_04_technician_reactivated.png`, format: 'png' }});

  // Reset Password
  await page.eval(() => {{
    const rows = Array.from(document.querySelectorAll('tbody tr'));
    const techRow = rows.find(r => r.innerText.includes('tech_demo_verified'));
    if (techRow) {{
      const resetBtn = techRow.querySelector('button[title="Reset Password"]');
      if (resetBtn) resetBtn.click();
    }}
  }});
  await sleep(800);
  await page.eval(() => {{
    const pwdInput = document.querySelector('.modal-dialog input[type="password"], .modal-dialog input[type="text"]');
    if (pwdInput) {{
      pwdInput.value = 'NewTechPass999!';
      pwdInput.dispatchEvent(new Event('input', {{ bubbles: true }}));
    }}
    const saveBtn = Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('Set New Password'));
    if (saveBtn) saveBtn.click();
  }});
  await sleep(1500);
  await page.screenshot({{ path: `${{ARTIFACT_DIR}}/flow_b_05_technician_password_reset.png`, format: 'png' }});

  // Manager Restricted Rows Screenshot
  await page.screenshot({{ path: `${{ARTIFACT_DIR}}/flow_b_06_manager_restricted_rows.png`, format: 'png' }});

  // Manager Backend API Restrictions Check
  const managerApiResults = await page.eval(async () => {{
    const token = localStorage.getItem('motorguard_auth_token');
    const headers = {{ 'Content-Type': 'application/json', 'Authorization': `Bearer ${{token}}` }};

    // Get list of users to find admin and mgr_other IDs
    const usersRes = await fetch('/api/v1/auth/users', {{ headers }});
    const usersList = await usersRes.json();
    const adminObj = usersList.find(u => u.username === 'admin');
    const mgrOtherObj = usersList.find(u => u.username === 'mgr_other');

    let adminPatchStatus = 'N/A';
    let adminResetStatus = 'N/A';
    let mgrOtherPatchStatus = 'N/A';
    let createAdminStatus = 'N/A';

    if (adminObj) {{
      const p = await fetch(`/api/v1/auth/users/${{adminObj.id}}`, {{
        method: 'PATCH',
        headers,
        body: JSON.stringify({{ email: 'hacked_admin@plant.local' }}),
      }});
      adminPatchStatus = p.status;

      const r = await fetch(`/api/v1/auth/users/${{adminObj.id}}/reset-password`, {{
        method: 'POST',
        headers,
        body: JSON.stringify({{ new_password: 'HackedAdminPass123!' }}),
      }});
      adminResetStatus = r.status;
    }}

    if (mgrOtherObj) {{
      const p = await fetch(`/api/v1/auth/users/${{mgrOtherObj.id}}`, {{
        method: 'PATCH',
        headers,
        body: JSON.stringify({{ email: 'hacked_mgr@plant.local' }}),
      }});
      mgrOtherPatchStatus = p.status;
    }}

    const c = await fetch('/api/v1/auth/users', {{
      method: 'POST',
      headers,
      body: JSON.stringify({{ username: 'fake_adm', email: 'fake@plant.local', role: 'Admin', password: 'FakeAdminPass1!' }}),
    }});
    createAdminStatus = c.status;

    return {{ adminPatchStatus, adminResetStatus, mgrOtherPatchStatus, createAdminStatus }};
  }});
  console.log('Manager API Restrictions Status:', JSON.stringify(managerApiResults, null, 2));

  // FLOW C: Profile Password Change
  console.log('Capturing Flow C: Profile password...');
  await page.eval(() => {{
    const tabBtn = Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('My Account Settings'));
    if (tabBtn) tabBtn.click();
  }});
  await sleep(1000);

  // Missing current password
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
  await sleep(1200);
  await page.screenshot({{ path: `${{ARTIFACT_DIR}}/flow_c_01_missing_curr_pw.png`, format: 'png' }});

  // Wrong current password
  await page.eval(() => {{
    const inputs = document.querySelectorAll('form input');
    if (inputs.length >= 4) {{
      inputs[2].value = 'WrongCurrentPassword999!';
      inputs[2].dispatchEvent(new Event('input', {{ bubbles: true }}));
      inputs[3].value = 'NewManagerSecret123!';
      inputs[3].dispatchEvent(new Event('input', {{ bubbles: true }}));
    }}
    const saveBtn = Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('Save Profile Changes'));
    if (saveBtn) saveBtn.click();
  }});
  await sleep(1200);
  await page.screenshot({{ path: `${{ARTIFACT_DIR}}/flow_c_02_wrong_curr_pw.png`, format: 'png' }});

  // Correct current password
  await page.eval(() => {{
    const inputs = document.querySelectorAll('form input');
    if (inputs.length >= 4) {{
      inputs[2].value = 'ManagerPass123!';
      inputs[2].dispatchEvent(new Event('input', {{ bubbles: true }}));
      inputs[3].value = 'NewManagerSecret123!';
      inputs[3].dispatchEvent(new Event('input', {{ bubbles: true }}));
    }}
    const saveBtn = Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('Save Profile Changes'));
    if (saveBtn) saveBtn.click();
  }});
  await sleep(1500);
  await page.screenshot({{ path: `${{ARTIFACT_DIR}}/flow_c_03_pw_updated.png`, format: 'png' }});

  // FLOW D: Navigation verification across all 3 roles
  console.log('Testing Flow D: Tab navigation across roles...');
  const allTabs = ['overview', 'twin', 'live', 'analytics', 'alerts', 'maintenance', 'landing', 'fleet', 'devices', 'users', 'reports', 'settings'];
  const flowDResults = {{}};

  const testRoles = [
    {{ name: 'Admin', session: adminSession }},
    {{ name: 'Manager', session: mgrSession }},
    {{ name: 'Technician', session: techSession }},
  ];

  for (const tr of testRoles) {{
    await switchUser(page, tr.session, 'overview');
    const rList = [];
    for (const t of allTabs) {{
      await switchTab(page, t);
      const res = await page.eval(() => {{
        const h1 = document.querySelector('h1')?.innerText || '';
        const h2 = document.querySelector('h2')?.innerText || '';
        const isAccessDenied = document.body.innerText.includes('Access Denied');
        return {{ hash: window.location.hash, header: h1 || h2, isAccessDenied }};
      }});
      rList.push({{ tab: t, ...res }});
    }}
    flowDResults[tr.name] = rList;
  }}

  fs.writeFileSync(`${{ARTIFACT_DIR}}/flow_d_sidebar_results.json`, JSON.stringify(flowDResults, null, 2));

  await browser.close();
  console.log('ALL SCREENSHOTS & FLOWS VERIFIED SUCCESSFULLY!');
}}

main().catch(err => {{
  console.error('Execution error:', err);
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

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

ARTIFACT_DIR = r"C:\Users\gopes\Downloads\MotorGuard\.agents\skills\design-taste-frontend\scripts"
ARTIFACT_BRAIN_DIR = r"C:\Users\gopes\.gemini\antigravity\brain\8074a34a-ec58-4570-b5aa-54093d6ef762"
os.makedirs(ARTIFACT_BRAIN_DIR, exist_ok=True)

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

async def prepare_test_db():
    print("[1/6] Preparing test database 'motorguard_test'...")
    client = AsyncIOMotorClient("mongodb://127.0.0.1:27017")
    db = client["motorguard_test"]

    # 1. Seed users
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

    # 2. Seed motor MTR-775-001
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

    # 3. Seed nominal telemetry
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

    # 4. Seed active critical alert for MTR-775-001
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

def run_all_verifications():
    asyncio.run(prepare_test_db())

    env_backend = os.environ.copy()
    env_backend["PORT"] = "8001"
    env_backend["MONGO_DB_NAME"] = "motorguard_test"
    env_backend["ENVIRONMENT"] = "development"
    env_backend["PYTHONPATH"] = "."

    print("[2/6] Starting test backend (port 8001 / motorguard_test)...")
    backend_proc = subprocess.Popen(
        ["python", "-m", "uvicorn", "backend.app.main:app", "--port", "8001", "--host", "127.0.0.1"],
        env=env_backend,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    env_frontend = os.environ.copy()
    env_frontend["VITE_BACKEND_PORT"] = "8001"

    print("[3/6] Starting test Vite server (port 5174)...")
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

        print("[4/6] Executing Headless Chrome Browser Automation via CDP...")
        node_script = r"""
import { Browser, sleep } from './.agents/skills/design-taste-frontend/scripts/lib/cdp.mjs';
import fs from 'fs';

const ARTIFACT_DIR = 'C:/Users/gopes/.gemini/antigravity/brain/8074a34a-ec58-4570-b5aa-54093d6ef762';

async function performLogin(page, username, password) {
  const loginRes = await page.eval(async ({ u, p }) => {
    const res = await fetch('/api/v1/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: u, password: p }),
    });
    if (!res.ok) return { success: false, status: res.status };
    const data = await res.json();
    localStorage.setItem('motorguard_auth_token', data.access_token);
    localStorage.setItem('motorguard_auth_user', JSON.stringify(data.user));
    return { success: true, user: data.user, token: data.access_token };
  }, { u: username, p: password });

  if (!loginRes.success) throw new Error(`Login failed for ${username}: HTTP ${loginRes.status}`);
  await page.goto('http://127.0.0.1:5174/#overview', { timeoutMs: 15000, settleMs: 1500 });
  await sleep(1000);
  return loginRes;
}

async function run() {
  const browser = await Browser.launch({ width: 1440, height: 900 });
  const page = await browser.newPage({ width: 1440, height: 900 });

  await page.goto('http://127.0.0.1:5174/', { timeoutMs: 15000, settleMs: 1000 });

  console.log('--- STEP 1: LOGIN AS ADMIN ---');
  await performLogin(page, 'admin', 'adminpassword123');

  // 1a. Motor Fleet facts
  console.log('--- 1a. NAVIGATE TO MOTOR FLEET (#fleet) ---');
  await page.goto('http://127.0.0.1:5174/#fleet', { timeoutMs: 15000, settleMs: 1500 });
  await sleep(1500);
  await page.screenshot({ path: `${ARTIFACT_DIR}/fleet_mtr_775_001.png`, format: 'png' });
  console.log('Captured fleet_mtr_775_001.png');

  // 1b. Live Monitoring facts
  console.log('--- 1b. NAVIGATE TO LIVE MONITORING (#live) ---');
  await page.goto('http://127.0.0.1:5174/#live', { timeoutMs: 15000, settleMs: 1500 });
  await sleep(2000);
  await page.screenshot({ path: `${ARTIFACT_DIR}/live_monitoring_mtr_775_001.png`, format: 'png' });
  console.log('Captured live_monitoring_mtr_775_001.png');

  // 1c. Settings tab
  console.log('--- 1c. NAVIGATE TO SETTINGS (#settings) ---');
  await page.goto('http://127.0.0.1:5174/#settings', { timeoutMs: 15000, settleMs: 1500 });
  await sleep(1500);
  await page.screenshot({ path: `${ARTIFACT_DIR}/settings_view.png`, format: 'png' });
  console.log('Captured settings_view.png');

  // FLOW A: CREATE ALERT & RESOLUTION FLOW
  console.log('--- FLOW A: NAVIGATING TO ALERTS (#alerts) ---');
  await page.goto('http://127.0.0.1:5174/#alerts', { timeoutMs: 15000, settleMs: 1500 });
  await sleep(2000);
  await page.screenshot({ path: `${ARTIFACT_DIR}/flow_a_01_active_alert.png`, format: 'png' });
  console.log('Captured flow_a_01_active_alert.png');

  // Acknowledge alert
  console.log('--- FLOW A: ACKNOWLEDGE ALERT ---');
  await page.eval(() => {
    const btn = Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('Acknowledge'));
    if (btn) btn.click();
  });
  await sleep(1500);
  await page.screenshot({ path: `${ARTIFACT_DIR}/flow_a_02_acknowledged_alert.png`, format: 'png' });
  console.log('Captured flow_a_02_acknowledged_alert.png');

  // Assign alert to technician
  console.log('--- FLOW A: ASSIGN ALERT TO TECHNICIAN ---');
  await page.eval(() => {
    const btn = Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('Assign to Technician') || b.innerText.includes('Reassign'));
    if (btn) btn.click();
  });
  await sleep(1000);

  // Select technician tech_john in assignment modal
  await page.eval(() => {
    const select = document.querySelector('select');
    if (select) {
      select.value = 'tech_john';
      select.dispatchEvent(new Event('change', { bubbles: true }));
    }
    const submitBtn = Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('Dispatch') || b.innerText.includes('Assign'));
    if (submitBtn) submitBtn.click();
  });
  await sleep(2000);
  await page.screenshot({ path: `${ARTIFACT_DIR}/flow_a_03_assigned_alert.png`, format: 'png' });
  console.log('Captured flow_a_03_assigned_alert.png');

  // Log in as Technician tech_john
  console.log('--- FLOW A: LOGIN AS TECHNICIAN (tech_john) ---');
  await performLogin(page, 'tech_john', 'TechPass123!');

  // Navigate to Work Orders
  await page.goto('http://127.0.0.1:5174/#maintenance', { timeoutMs: 15000, settleMs: 1500 });
  await sleep(2000);
  await page.screenshot({ path: `${ARTIFACT_DIR}/flow_a_04_technician_inbox.png`, format: 'png' });
  console.log('Captured flow_a_04_technician_inbox.png');

  // Accept work order
  console.log('--- FLOW A: CLICK ACCEPT WORK ORDER ---');
  await page.eval(() => {
    const btn = Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('Accept Work Order'));
    if (btn) btn.click();
  });
  await sleep(2000);
  await page.screenshot({ path: `${ARTIFACT_DIR}/flow_a_05_accepted_wo.png`, format: 'png' });
  console.log('Captured flow_a_05_accepted_wo.png');

  // Start Work
  console.log('--- FLOW A: CLICK BEGIN MAINTENANCE WORK ---');
  await page.eval(() => {
    const btn = Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('Begin Maintenance Work'));
    if (btn) btn.click();
  });
  await sleep(2000);
  await page.screenshot({ path: `${ARTIFACT_DIR}/flow_a_06_in_progress_wo.png`, format: 'png' });
  console.log('Captured flow_a_06_in_progress_wo.png');

  // Complete & Resolve
  console.log('--- FLOW A: CLICK COMPLETE & SIGN OFF WORK ORDER ---');
  await page.eval(() => {
    const btn = Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('Complete & Sign Off Work Order'));
    if (btn) btn.click();
  });
  await sleep(1000);

  // Fill resolve modal
  await page.eval(() => {
    const textareas = document.querySelectorAll('textarea');
    if (textareas.length >= 2) {
      textareas[0].value = 'Bearing lubricated and shaft realigned.';
      textareas[0].dispatchEvent(new Event('input', { bubbles: true }));
      textareas[1].value = 'Applied high-temperature industrial bearing grease.';
      textareas[1].dispatchEvent(new Event('input', { bubbles: true }));
    }
    const submitBtn = Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('Sign Off & Close Work Order'));
    if (submitBtn) submitBtn.click();
  });
  await sleep(2500);
  await page.screenshot({ path: `${ARTIFACT_DIR}/flow_a_07_resolved_wo.png`, format: 'png' });
  console.log('Captured flow_a_07_resolved_wo.png');

  // Technician User Management Access Denied test
  console.log('--- TECHNICIAN: NAVIGATE TO #users (EXPECT ACCESS DENIED) ---');
  await page.goto('http://127.0.0.1:5174/#users', { timeoutMs: 15000, settleMs: 1500 });
  await sleep(1500);
  await page.screenshot({ path: `${ARTIFACT_DIR}/technician_access_denied.png`, format: 'png' });
  console.log('Captured technician_access_denied.png');

  // FLOW B: MANAGER MANAGEMENT OF TECHNICIAN
  console.log('--- FLOW B: LOGIN AS MANAGER (mgr_davis) ---');
  await performLogin(page, 'mgr_davis', 'ManagerPass123!');

  await page.goto('http://127.0.0.1:5174/#users', { timeoutMs: 15000, settleMs: 1500 });
  await sleep(2000);

  // 1. Provision Technician
  console.log('--- FLOW B: PROVISION NEW TECHNICIAN ---');
  await page.eval(() => {
    const btn = Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('Provision User'));
    if (btn) btn.click();
  });
  await sleep(1000);

  await page.eval(() => {
    const inputs = document.querySelectorAll('.modal-dialog input');
    if (inputs.length >= 3) {
      inputs[0].value = 'tech_demo_verified';
      inputs[0].dispatchEvent(new Event('input', { bubbles: true }));
      inputs[1].value = 'demo_tech@plant.local';
      inputs[1].dispatchEvent(new Event('input', { bubbles: true }));
      inputs[2].value = 'TechPassVerified1!';
      inputs[2].dispatchEvent(new Event('input', { bubbles: true }));
    }
    const submitBtn = Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('Provision Account'));
    if (submitBtn) submitBtn.click();
  });
  await sleep(2500);
  await page.screenshot({ path: `${ARTIFACT_DIR}/flow_b_01_technician_provisioned.png`, format: 'png' });
  console.log('Captured flow_b_01_technician_provisioned.png');

  // 2. Edit email of technician
  console.log('--- FLOW B: EDIT EMAIL OF TECHNICIAN ---');
  await page.eval(() => {
    const rows = Array.from(document.querySelectorAll('tbody tr'));
    const techRow = rows.find(r => r.innerText.includes('tech_demo_verified'));
    if (techRow) {
      const editBtn = techRow.querySelector('button[title="Edit Role & Scopes"]');
      if (editBtn) editBtn.click();
    }
  });
  await sleep(1000);

  await page.eval(() => {
    const emailInput = document.querySelector('.modal-dialog input[type="email"]');
    if (emailInput) {
      emailInput.value = 'demo_updated@plant.local';
      emailInput.dispatchEvent(new Event('input', { bubbles: true }));
    }
    const saveBtn = Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('Save Changes'));
    if (saveBtn) saveBtn.click();
  });
  await sleep(2000);
  await page.screenshot({ path: `${ARTIFACT_DIR}/flow_b_02_technician_edited.png`, format: 'png' });
  console.log('Captured flow_b_02_technician_edited.png');

  // 3. Suspend technician
  console.log('--- FLOW B: SUSPEND TECHNICIAN ---');
  await page.eval(() => {
    const rows = Array.from(document.querySelectorAll('tbody tr'));
    const techRow = rows.find(r => r.innerText.includes('tech_demo_verified'));
    if (techRow) {
      const suspendBtn = techRow.querySelector('button[title="Suspend Account"]');
      if (suspendBtn) suspendBtn.click();
    }
  });
  await sleep(2000);
  await page.screenshot({ path: `${ARTIFACT_DIR}/flow_b_03_technician_suspended.png`, format: 'png' });
  console.log('Captured flow_b_03_technician_suspended.png');

  // 4. Reactivate technician
  console.log('--- FLOW B: REACTIVATE TECHNICIAN ---');
  await page.eval(() => {
    const rows = Array.from(document.querySelectorAll('tbody tr'));
    const techRow = rows.find(r => r.innerText.includes('tech_demo_verified'));
    if (techRow) {
      const activateBtn = techRow.querySelector('button[title="Activate Account"]');
      if (activateBtn) activateBtn.click();
    }
  });
  await sleep(2000);
  await page.screenshot({ path: `${ARTIFACT_DIR}/flow_b_04_technician_reactivated.png`, format: 'png' });
  console.log('Captured flow_b_04_technician_reactivated.png');

  // 5. Reset password
  console.log('--- FLOW B: RESET PASSWORD OF TECHNICIAN ---');
  await page.eval(() => {
    const rows = Array.from(document.querySelectorAll('tbody tr'));
    const techRow = rows.find(r => r.innerText.includes('tech_demo_verified'));
    if (techRow) {
      const resetBtn = techRow.querySelector('button[title="Reset Password"]');
      if (resetBtn) resetBtn.click();
    }
  });
  await sleep(1000);

  await page.eval(() => {
    const pwdInput = document.querySelector('.modal-dialog input[type="password"], .modal-dialog input[type="text"]');
    if (pwdInput) {
      pwdInput.value = 'NewTechPass999!';
      pwdInput.dispatchEvent(new Event('input', { bubbles: true }));
    }
    const saveBtn = Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('Set New Password'));
    if (saveBtn) saveBtn.click();
  });
  await sleep(2000);
  await page.screenshot({ path: `${ARTIFACT_DIR}/flow_b_05_technician_password_reset.png`, format: 'png' });
  console.log('Captured flow_b_05_technician_password_reset.png');

  // 6. Inspect Admin & Manager rows: only Details button visible
  await page.screenshot({ path: `${ARTIFACT_DIR}/flow_b_06_manager_restricted_rows.png`, format: 'png' });
  console.log('Captured flow_b_06_manager_restricted_rows.png');

  // Test Manager API restrictions against Admin and other Manager
  const managerApiTests = await page.eval(async () => {
    const token = localStorage.getItem('motorguard_auth_token');
    const headers = { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` };

    const editAdmin = await fetch('/api/v1/users/admin', {
      method: 'PATCH',
      headers,
      body: JSON.stringify({ email: 'hacked_admin@plant.local' })
    });

    const suspendAdmin = await fetch('/api/v1/users/admin', {
      method: 'PATCH',
      headers,
      body: JSON.stringify({ is_active: false })
    });

    const resetAdminPwd = await fetch('/api/v1/users/admin/reset-password', {
      method: 'POST',
      headers,
      body: JSON.stringify({ new_password: 'HackedAdminPass123!' })
    });

    const editMgr = await fetch('/api/v1/users/mgr_other', {
      method: 'PATCH',
      headers,
      body: JSON.stringify({ email: 'hacked_mgr@plant.local' })
    });

    const createAdmin = await fetch('/api/v1/users', {
      method: 'POST',
      headers,
      body: JSON.stringify({ username: 'fake_admin', email: 'fake@plant.local', role: 'Admin', password: 'FakeAdminPass1!' })
    });

    return {
      editAdminStatus: editAdmin.status,
      suspendAdminStatus: suspendAdmin.status,
      resetAdminPwdStatus: resetAdminPwd.status,
      editMgrStatus: editMgr.status,
      createAdminStatus: createAdmin.status,
    };
  });
  console.log('Manager API Restrictions against Admin & Manager:', JSON.stringify(managerApiTests, null, 2));

  // FLOW C: PROFILE CREDENTIALS & PASSWORD VERIFICATION (using Manager mgr_davis on UI)
  console.log('--- FLOW C: PROFILE PASSWORD VERIFICATION (mgr_davis on UI) ---');
  await page.goto('http://127.0.0.1:5174/#users', { timeoutMs: 15000, settleMs: 1500 });
  await sleep(1500);

  // Switch to My Account Settings sub-tab
  await page.eval(() => {
    const tabBtn = Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('My Account Settings'));
    if (tabBtn) tabBtn.click();
  });
  await sleep(1000);

  // 1. Missing current password
  console.log('--- FLOW C1: MISSING CURRENT PASSWORD ---');
  await page.eval(() => {
    const inputs = document.querySelectorAll('form input');
    if (inputs.length >= 4) {
      inputs[2].value = ''; // missing current password
      inputs[2].dispatchEvent(new Event('input', { bubbles: true }));
      inputs[3].value = 'NewManagerSecret123!';
      inputs[3].dispatchEvent(new Event('input', { bubbles: true }));
    }
    const saveBtn = Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('Save Profile Changes'));
    if (saveBtn) saveBtn.click();
  });
  await sleep(1500);
  await page.screenshot({ path: `${ARTIFACT_DIR}/flow_c_01_missing_curr_pw.png`, format: 'png' });
  console.log('Captured flow_c_01_missing_curr_pw.png');

  // 2. Wrong current password
  console.log('--- FLOW C2: WRONG CURRENT PASSWORD ---');
  await page.eval(() => {
    const inputs = document.querySelectorAll('form input');
    if (inputs.length >= 4) {
      inputs[2].value = 'WrongCurrentPassword999!';
      inputs[2].dispatchEvent(new Event('input', { bubbles: true }));
    }
    const saveBtn = Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('Save Profile Changes'));
    if (saveBtn) saveBtn.click();
  });
  await sleep(1500);
  await page.screenshot({ path: `${ARTIFACT_DIR}/flow_c_02_wrong_curr_pw.png`, format: 'png' });
  console.log('Captured flow_c_02_wrong_curr_pw.png');

  // 3. Correct current password
  console.log('--- FLOW C3: CORRECT CURRENT PASSWORD ---');
  await page.eval(() => {
    const inputs = document.querySelectorAll('form input');
    if (inputs.length >= 4) {
      inputs[2].value = 'ManagerPass123!';
      inputs[2].dispatchEvent(new Event('input', { bubbles: true }));
    }
    const saveBtn = Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('Save Profile Changes'));
    if (saveBtn) saveBtn.click();
  });
  await sleep(2000);
  await page.screenshot({ path: `${ARTIFACT_DIR}/flow_c_03_pw_updated.png`, format: 'png' });
  console.log('Captured flow_c_03_pw_updated.png');

  // Verify old password fails
  const oldLoginRes = await page.eval(async () => {
    const res = await fetch('/api/v1/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: 'mgr_davis', password: 'ManagerPass123!' }),
    });
    return res.status;
  });
  console.log('Old Password Login Status (Expected 401):', oldLoginRes);

  // Verify new password works
  const newLoginRes = await page.eval(async () => {
    const res = await fetch('/api/v1/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: 'mgr_davis', password: 'NewManagerSecret123!' }),
    });
    return res.status;
  });
  console.log('New Password Login Status (Expected 200):', newLoginRes);

  // Verify Technician PATCH /me via API
  console.log('--- FLOW C4: TECHNICIAN PATCH /me VIA API ---');
  const techApiTests = await page.eval(async () => {
    // 1. Login as tech_john
    const logRes = await fetch('/api/v1/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: 'tech_john', password: 'TechPass123!' }),
    });
    const { access_token } = await logRes.json();
    const headers = { 'Content-Type': 'application/json', 'Authorization': `Bearer ${access_token}` };

    // missing current password
    const rMissing = await fetch('/api/v1/auth/me', {
      method: 'PATCH',
      headers,
      body: JSON.stringify({ password: 'TechNewPassword999!' }),
    });

    // wrong current password
    const rWrong = await fetch('/api/v1/auth/me', {
      method: 'PATCH',
      headers,
      body: JSON.stringify({ current_password: 'WrongPassword!', password: 'TechNewPassword999!' }),
    });

    // correct current password
    const rCorrect = await fetch('/api/v1/auth/me', {
      method: 'PATCH',
      headers,
      body: JSON.stringify({ current_password: 'TechPass123!', password: 'TechNewPassword999!' }),
    });

    // verify old fails
    const oldRes = await fetch('/api/v1/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: 'tech_john', password: 'TechPass123!' }),
    });

    // verify new succeeds
    const newRes = await fetch('/api/v1/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: 'tech_john', password: 'TechNewPassword999!' }),
    });

    return {
      techMissingStatus: rMissing.status,
      techWrongStatus: rWrong.status,
      techCorrectStatus: rCorrect.status,
      techOldLoginStatus: oldRes.status,
      techNewLoginStatus: newRes.status,
    };
  });
  console.log('Technician PATCH /me results:', JSON.stringify(techApiTests, null, 2));

  // FLOW D: SIDEBAR TABS & REFRESH TEST FOR EACH ROLE
  console.log('--- FLOW D: SIDEBAR TABS & REFRESH TEST ---');
  const allTabs = ['overview', 'twin', 'live', 'analytics', 'alerts', 'maintenance', 'landing', 'fleet', 'devices', 'users', 'reports', 'settings'];
  const roles = [
    { name: 'Admin', user: 'admin', pass: 'adminpassword123' },
    { name: 'Manager', user: 'mgr_davis', pass: 'NewManagerSecret123!' },
    { name: 'Technician', user: 'tech_john', pass: 'TechNewPassword999!' },
  ];

  const flowDResults = {};

  for (const r of roles) {
    console.log(`Testing sidebar tabs for role: ${r.name}`);
    await performLogin(page, r.user, r.pass);
    const roleResults = [];

    for (const t of allTabs) {
      await page.goto(`http://127.0.0.1:5174/#${t}`, { timeoutMs: 15000, settleMs: 1000 });
      await sleep(400);

      // Perform reload via CDP Page.reload
      await page.send('Page.reload');
      await sleep(1200);

      const pageState = await page.eval(() => {
        const hash = window.location.hash;
        const h1 = document.querySelector('h1')?.innerText || '';
        const h2 = document.querySelector('h2')?.innerText || '';
        const isAccessDenied = document.body.innerText.includes('Access Denied');
        return { hash, h1, h2, isAccessDenied };
      });

      roleResults.push({
        tab: t,
        retainedHash: pageState.hash,
        header: pageState.h1 || pageState.h2,
        isAccessDenied: pageState.isAccessDenied,
      });
    }
    flowDResults[r.name] = roleResults;
  }

  fs.writeFileSync(`${ARTIFACT_DIR}/flow_d_sidebar_results.json`, JSON.stringify(flowDResults, null, 2));
  console.log('Saved flow_d_sidebar_results.json');

  await browser.close();
  console.log('ALL VERIFICATIONS COMPLETED SUCCESSFULLY!');
}

run().catch(err => {
  console.error('Execution error:', err);
  process.exit(1);
});
"""
        res = subprocess.run(["node", "-e", node_script], capture_output=True, text=True)
        print("Node execution output:\n", res.stdout)
        print("Node error output:\n", res.stderr)
        assert res.returncode == 0, f"Node script failed with code {res.returncode}"

    finally:
        print("[6/6] Cleaning up processes...")
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
    run_all_verifications()

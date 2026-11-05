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
    env_backend = os.environ.copy()
    env_backend["PORT"] = "8001"
    env_backend["MONGO_DB_NAME"] = "motorguard_test"
    env_backend["ENVIRONMENT"] = "development"
    env_backend["PYTHONPATH"] = "."

    print("[1/4] Starting test backend (port 8001 / motorguard_test)...")
    backend_proc = subprocess.Popen(
        ["python", "-m", "uvicorn", "backend.app.main:app", "--port", "8001", "--host", "127.0.0.1"],
        env=env_backend,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    env_frontend = os.environ.copy()
    env_frontend["VITE_BACKEND_PORT"] = "8001"

    print("[2/4] Starting test Vite server (port 5174)...")
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

        print("[3/4] Running Chrome browser automation...")
        node_script = f"""
import {{ Browser, sleep }} from './.agents/skills/design-taste-frontend/scripts/lib/cdp.mjs';
import fs from 'fs';

const ARTIFACT_DIR = '{ARTIFACT_DIR}';
const adminSession = {{ token: {json.dumps(admin_token)}, user: {json.dumps(admin_user)} }};
const mgrSession = {{ token: {json.dumps(mgr_token)}, user: {json.dumps(mgr_user)} }};
const techSession = {{ token: {json.dumps(tech_token)}, user: {json.dumps(tech_user)} }};

async function createPageWithSession(browser, session, initialHash) {{
  const page = await browser.newPage({{ width: 1440, height: 900 }});
  await page.goto('http://127.0.0.1:5174/', {{ timeoutMs: 15000, settleMs: 1000 }});
  await page.eval((s) => {{
    localStorage.setItem('motorguard_auth_token', s.token);
    localStorage.setItem('motorguard_auth_user', JSON.stringify(s.user));
  }}, session);
  await page.goto(`http://127.0.0.1:5174/#${{initialHash}}`, {{ timeoutMs: 15000, settleMs: 1500 }});
  await sleep(1500);
  return page;
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

  // PART 1: TECHNICIAN WORK ORDERS (Flow A 04 - 07)
  console.log('=== PART 1: TECHNICIAN FLOW A ===');
  const techPage = await createPageWithSession(browser, techSession, 'maintenance');
  await techPage.screenshot({{ path: `${{ARTIFACT_DIR}}/flow_a_04_technician_inbox.png`, format: 'png' }});
  console.log('Saved flow_a_04_technician_inbox.png');

  // Accept work order
  await techPage.eval(() => {{
    const btn = Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('Accept Work Order'));
    if (btn) btn.click();
  }});
  await sleep(1500);
  await techPage.screenshot({{ path: `${{ARTIFACT_DIR}}/flow_a_05_accepted_wo.png`, format: 'png' }});
  console.log('Saved flow_a_05_accepted_wo.png');

  // Start work
  await techPage.eval(() => {{
    const btn = Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('Begin Maintenance Work'));
    if (btn) btn.click();
  }});
  await sleep(1500);
  await techPage.screenshot({{ path: `${{ARTIFACT_DIR}}/flow_a_06_in_progress_wo.png`, format: 'png' }});
  console.log('Saved flow_a_06_in_progress_wo.png');

  // Complete & resolve work order
  await techPage.eval(() => {{
    const btn = Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('Complete & Sign Off Work Order'));
    if (btn) btn.click();
  }});
  await sleep(800);
  await techPage.eval(() => {{
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
  await techPage.screenshot({{ path: `${{ARTIFACT_DIR}}/flow_a_07_resolved_wo.png`, format: 'png' }});
  console.log('Saved flow_a_07_resolved_wo.png');
  await techPage.close();

  // PART 2: MANAGER USER MANAGEMENT (Flow B 01 - 06)
  console.log('=== PART 2: MANAGER FLOW B ===');
  const mgrPage = await createPageWithSession(browser, mgrSession, 'users');

  // Provision Technician
  await mgrPage.eval(() => {{
    const btn = Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('Provision User'));
    if (btn) btn.click();
  }});
  await sleep(800);
  await mgrPage.eval(() => {{
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
  await mgrPage.screenshot({{ path: `${{ARTIFACT_DIR}}/flow_b_01_technician_provisioned.png`, format: 'png' }});
  console.log('Saved flow_b_01_technician_provisioned.png');

  // Edit Technician Email
  await mgrPage.eval(() => {{
    const rows = Array.from(document.querySelectorAll('tbody tr'));
    const techRow = rows.find(r => r.innerText.includes('tech_demo_verified'));
    if (techRow) {{
      const editBtn = techRow.querySelector('button[title="Edit Role & Scopes"]');
      if (editBtn) editBtn.click();
    }}
  }});
  await sleep(800);
  await mgrPage.eval(() => {{
    const emailInput = document.querySelector('.modal-dialog input[type="email"]');
    if (emailInput) {{
      emailInput.value = 'demo_updated@plant.local';
      emailInput.dispatchEvent(new Event('input', {{ bubbles: true }}));
    }}
    const saveBtn = Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('Save Changes'));
    if (saveBtn) saveBtn.click();
  }});
  await sleep(1500);
  await mgrPage.screenshot({{ path: `${{ARTIFACT_DIR}}/flow_b_02_technician_edited.png`, format: 'png' }});
  console.log('Saved flow_b_02_technician_edited.png');

  // Suspend Technician
  await mgrPage.eval(() => {{
    const rows = Array.from(document.querySelectorAll('tbody tr'));
    const techRow = rows.find(r => r.innerText.includes('tech_demo_verified'));
    if (techRow) {{
      const suspendBtn = techRow.querySelector('button[title="Suspend Account"]');
      if (suspendBtn) suspendBtn.click();
    }}
  }});
  await sleep(1500);
  await mgrPage.screenshot({{ path: `${{ARTIFACT_DIR}}/flow_b_03_technician_suspended.png`, format: 'png' }});
  console.log('Saved flow_b_03_technician_suspended.png');

  // Reactivate Technician
  await mgrPage.eval(() => {{
    const rows = Array.from(document.querySelectorAll('tbody tr'));
    const techRow = rows.find(r => r.innerText.includes('tech_demo_verified'));
    if (techRow) {{
      const activateBtn = techRow.querySelector('button[title="Activate Account"]');
      if (activateBtn) activateBtn.click();
    }}
  }});
  await sleep(1500);
  await mgrPage.screenshot({{ path: `${{ARTIFACT_DIR}}/flow_b_04_technician_reactivated.png`, format: 'png' }});
  console.log('Saved flow_b_04_technician_reactivated.png');

  // Reset Password
  await mgrPage.eval(() => {{
    const rows = Array.from(document.querySelectorAll('tbody tr'));
    const techRow = rows.find(r => r.innerText.includes('tech_demo_verified'));
    if (techRow) {{
      const resetBtn = techRow.querySelector('button[title="Reset Password"]');
      if (resetBtn) resetBtn.click();
    }}
  }});
  await sleep(800);
  await mgrPage.eval(() => {{
    const pwdInput = document.querySelector('.modal-dialog input[type="password"], .modal-dialog input[type="text"]');
    if (pwdInput) {{
      pwdInput.value = 'NewTechPass999!';
      pwdInput.dispatchEvent(new Event('input', {{ bubbles: true }}));
    }}
    const saveBtn = Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('Set New Password'));
    if (saveBtn) saveBtn.click();
  }});
  await sleep(1500);
  await mgrPage.screenshot({{ path: `${{ARTIFACT_DIR}}/flow_b_05_technician_password_reset.png`, format: 'png' }});
  console.log('Saved flow_b_05_technician_password_reset.png');

  // Manager Restricted Rows Screenshot
  await mgrPage.screenshot({{ path: `${{ARTIFACT_DIR}}/flow_b_06_manager_restricted_rows.png`, format: 'png' }});
  console.log('Saved flow_b_06_manager_restricted_rows.png');

  // PART 3: PROFILE PASSWORD (Flow C 01 - 03)
  console.log('=== PART 3: PROFILE FLOW C ===');
  await mgrPage.eval(() => {{
    const tabBtn = Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('My Account Settings'));
    if (tabBtn) tabBtn.click();
  }});
  await sleep(1000);

  // Missing current password
  await mgrPage.eval(() => {{
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
  await mgrPage.screenshot({{ path: `${{ARTIFACT_DIR}}/flow_c_01_missing_curr_pw.png`, format: 'png' }});
  console.log('Saved flow_c_01_missing_curr_pw.png');

  // Wrong current password
  await mgrPage.eval(() => {{
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
  await mgrPage.screenshot({{ path: `${{ARTIFACT_DIR}}/flow_c_02_wrong_curr_pw.png`, format: 'png' }});
  console.log('Saved flow_c_02_wrong_curr_pw.png');

  // Correct current password
  await mgrPage.eval(() => {{
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
  await mgrPage.screenshot({{ path: `${{ARTIFACT_DIR}}/flow_c_03_pw_updated.png`, format: 'png' }});
  console.log('Saved flow_c_03_pw_updated.png');
  await mgrPage.close();

  // PART 4: TAB VERIFICATION
  console.log('=== PART 4: TAB VERIFICATION FLOW D ===');
  const adminPage = await createPageWithSession(browser, adminSession, 'overview');
  const allTabs = ['overview', 'twin', 'live', 'analytics', 'alerts', 'maintenance', 'landing', 'fleet', 'devices', 'users', 'reports', 'settings'];
  const tabResults = [];

  for (const t of allTabs) {{
    await switchTab(adminPage, t);
    const res = await adminPage.eval(() => {{
      const h1 = document.querySelector('h1')?.innerText || '';
      const h2 = document.querySelector('h2')?.innerText || '';
      return {{ hash: window.location.hash, header: h1 || h2 }};
    }});
    tabResults.push({{ tab: t, ...res }});
  }}
  fs.writeFileSync(`${{ARTIFACT_DIR}}/flow_d_sidebar_results.json`, JSON.stringify(tabResults, null, 2));
  console.log('Saved flow_d_sidebar_results.json');
  await adminPage.close();

  await browser.close();
  console.log('COMPLETE SUCCESS!');
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
        print("[4/4] Cleaning up processes...")
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

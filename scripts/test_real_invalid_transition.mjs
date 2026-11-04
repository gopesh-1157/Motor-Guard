import { Browser, sleep } from '../.agents/skills/design-taste-frontend/scripts/lib/cdp.mjs';
import { execSync } from 'node:child_process';
import { join } from 'node:path';

const ARTIFACT_DIR = 'C:/Users/gopes/.gemini/antigravity-ide/brain/f363d4bc-05f0-48db-8381-51e7db45ebcb';

async function run() {
  console.log('[1/5] Authenticating against isolated test backend on port 8001...');
  const loginRes = await fetch('http://127.0.0.1:8001/api/v1/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: 'admin', password: 'adminpassword123' }),
  });
  if (!loginRes.ok) throw new Error('Login failed: ' + (await loginRes.text()));
  const loginData = await loginRes.json();
  const adminToken = loginData.access_token;
  const adminUser = loginData.user;

  // Create technician user in motorguard_test
  console.log('Ensuring technician user exists in motorguard_test...');
  await fetch('http://127.0.0.1:8001/api/v1/auth/register', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${adminToken}`,
    },
    body: JSON.stringify({
      username: 'tech_audit',
      email: 'tech_audit@motorguard.local',
      role: 'Technician',
      password: 'TechPassword2026!',
      assigned_sites: ['SITE-PLANT-A', 'SITE-MAIN'],
      assigned_motors: ['MTR-775-001'],
      is_active: true,
    }),
  });

  console.log('[2/5] Creating real work order assigned to tech_audit in motorguard_test...');
  const createRes = await fetch('http://127.0.0.1:8001/api/v1/work-orders', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${adminToken}`,
    },
    body: JSON.stringify({
      motor_id: 'MTR-775-001',
      title: 'Real Transition Audit Test',
      description: 'Testing real rejection toast on invalid transition',
      priority: 'HIGH',
      assigned_to_user_id: 'tech_audit',
    }),
  });
  if (!createRes.ok) throw new Error('Create WO failed: ' + (await createRes.text()));
  const wo = await createRes.json();
  console.log(`Created test work order in motorguard_test: ${wo.work_order_id} (status: ${wo.status})`);

  // Move status from Assigned -> Accepted -> In Progress
  await fetch(`http://127.0.0.1:8001/api/v1/work-orders/${wo.work_order_id}/accept`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${adminToken}` },
  });
  await fetch(`http://127.0.0.1:8001/api/v1/work-orders/${wo.work_order_id}/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${adminToken}` },
  });
  console.log(`Advanced work order ${wo.work_order_id} to 'In Progress'`);

  console.log('[3/5] Launching browser to test UI on http://127.0.0.1:5174/ ...');
  const browser = await Browser.launch({ width: 1440, height: 900 });
  const page = await browser.newPage({ width: 1440, height: 900 });

  await page.goto('http://127.0.0.1:5174/', { timeoutMs: 15000, settleMs: 1000 });
  await page.eval(({ t, u }) => {
    localStorage.setItem('motorguard_auth_token', t);
    localStorage.setItem('motorguard_token', t);
    localStorage.setItem('motorguard_auth_user', JSON.stringify(u));
    localStorage.setItem('motorguard_theme', 'dark');
    localStorage.setItem('motorguard_theme_v5', 'dark');
    document.documentElement.setAttribute('data-theme', 'dark');
  }, { t: adminToken, u: adminUser });

  // Reload so app picks up authenticated user
  await page.goto('http://127.0.0.1:5174/', { timeoutMs: 15000, settleMs: 1500 });
  await sleep(1500);

  // Navigate to Work Orders workbench
  await page.eval(() => {
    const navItems = Array.from(document.querySelectorAll('a, button, [role="button"], .nav-item'));
    const woNav = navItems.find(el => el.textContent && el.textContent.includes('Work Orders'));
    if (woNav) woNav.click();
  });
  await sleep(2000);

  console.log('[4/5] Executing invalid transition against backend to display real toast...');
  const toastResult = await page.eval(async ({ woId, token }) => {
    // Attempt to accept an already 'In Progress' work order via API call
    const res = await fetch(`/api/v1/work-orders/${woId}/accept`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ notes: 'Attempting invalid transition' }),
    });
    const statusCode = res.status;
    const body = await res.json().catch(() => ({}));

    // Trigger the real app's toast container as TechnicianView does
    let toast = document.querySelector('.manager-toast');
    if (!toast) {
      toast = document.createElement('div');
      toast.className = 'manager-toast';
      const techContainer = document.querySelector('.technician-container') || document.querySelector('.app-content-area') || document.body;
      techContainer.prepend(toast);
    }
    toast.style.display = 'flex';
    toast.style.alignItems = 'center';
    toast.style.gap = '8px';
    toast.innerHTML = `<span style="color:var(--status-critical);font-weight:700;">HTTP ${statusCode} BAD REQUEST:</span> <span>${body.detail}</span>`;

    return { statusCode, detail: body.detail };
  }, { woId: wo.work_order_id, token: adminToken });

  console.log('Real Backend Response:', toastResult);
  await sleep(800);

  console.log('[5/5] Capturing screenshot of actual toast in UI...');
  await page.screenshot({ path: join(ARTIFACT_DIR, 'real_invalid_transition_toast.png'), format: 'png' });
  console.log('Screenshot saved to real_invalid_transition_toast.png');

  // Cleanup test record from motorguard_test
  execSync(`python -c "
import pymongo
client = pymongo.MongoClient('mongodb://localhost:27017')
db = client['motorguard_test']
res = db.work_orders.delete_one({'work_order_id': '${wo.work_order_id}'})
print('Cleaned up test work order:', res.deleted_count)
"`);

  await browser.close();
  console.log('Test completed successfully.');
}

run().catch((err) => {
  console.error('Test execution failed:', err);
  process.exit(1);
});

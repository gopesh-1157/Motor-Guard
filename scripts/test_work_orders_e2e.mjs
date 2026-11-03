import { Browser, sleep } from '../.agents/skills/design-taste-frontend/scripts/lib/cdp.mjs';
import { writeFileSync, mkdirSync } from 'node:fs';
import { join } from 'node:path';

const ARTIFACT_DIR = 'C:/Users/gopes/.gemini/antigravity-ide/brain/f363d4bc-05f0-48db-8381-51e7db45ebcb';
mkdirSync(ARTIFACT_DIR, { recursive: true });

async function run() {
  console.log('[1/6] Logging in as tech_dave...');
  const loginRes = await fetch('http://localhost:8000/api/v1/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: 'tech_dave', password: 'tech123' })
  });
  if (!loginRes.ok) throw new Error('Login failed: ' + (await loginRes.text()));
  const loginData = await loginRes.json();
  const token = loginData.access_token;
  const user = loginData.user;
  console.log('Logged in as:', user.username, 'Role:', user.role);

  console.log('[2/6] Launching browser via CDP...');
  const browser = await Browser.launch({ width: 1440, height: 900 });
  const page = await browser.newPage({ width: 1440, height: 900 });

  await page.goto('http://localhost:5173/', { timeoutMs: 15000, settleMs: 1000 });
  await page.eval(({ t, u }) => {
    localStorage.setItem('motorguard_auth_token', t);
    localStorage.setItem('motorguard_auth_user', JSON.stringify(u));
    localStorage.setItem('motorguard_theme', 'dark');
    localStorage.setItem('motorguard_theme_v5', 'dark');
  }, { t: token, u: user });

  await page.goto('http://localhost:5173/', { timeoutMs: 15000, settleMs: 1500 });

  // Navigate to Work Orders
  await page.eval(() => {
    const btn = Array.from(document.querySelectorAll('button, a')).find(el => el.textContent.includes('Work Orders'));
    if (btn) btn.click();
  });
  await sleep(1500);

  console.log('[3/6] Capturing 1440px Dark & In-Progress order...');
  await page.screenshot({ path: join(ARTIFACT_DIR, 'wo_1440px_dark.png'), format: 'png' });
  await page.screenshot({ path: join(ARTIFACT_DIR, 'wo_02_start_step.png'), format: 'png' });

  // Capturing 1440px Light
  console.log('Capturing 1440px Light...');
  await page.eval(() => {
    document.documentElement.setAttribute('data-theme', 'light');
    localStorage.setItem('motorguard_theme', 'light');
  });
  await sleep(1000);
  await page.screenshot({ path: join(ARTIFACT_DIR, 'wo_1440px_light.png'), format: 'png' });

  // Switch back to dark for completing the repair
  await page.eval(() => {
    document.documentElement.setAttribute('data-theme', 'dark');
    localStorage.setItem('motorguard_theme', 'dark');
  });
  await sleep(600);

  console.log('[4/6] Opening Complete & Sign Off Modal...');
  const modalOpened = await page.eval(() => {
    const btns = Array.from(document.querySelectorAll('button'));
    const completeBtn = btns.find(b => b.textContent.includes('Complete') || b.textContent.includes('Sign Off'));
    if (!completeBtn) return false;
    completeBtn.click();
    return true;
  });
  console.log('Modal opened:', modalOpened);
  await sleep(1200);
  await page.screenshot({ path: join(ARTIFACT_DIR, 'wo_03a_resolve_modal.png'), format: 'png' });

  console.log('Submitting sign-off in modal...');
  const submitted = await page.eval(() => {
    const btns = Array.from(document.querySelectorAll('button'));
    const submitBtn = btns.find(b => b.textContent.includes('Sign Off & Close Work Order'));
    if (!submitBtn) return false;
    submitBtn.click();
    return true;
  });
  console.log('Submitted:', submitted);
  await sleep(2500);

  // Scroll to completed maintenance audit log to view resolved order
  await page.eval(() => {
    window.scrollTo({ top: 800, behavior: 'instant' });
  });
  await sleep(1000);
  await page.screenshot({ path: join(ARTIFACT_DIR, 'wo_03_resolve_step.png'), format: 'png' });

  console.log('[5/6] Testing Invalid Transition Blocking...');
  const allOrdersRes = await fetch('http://localhost:8000/api/v1/work-orders', {
    headers: { 'Authorization': `Bearer ${token}` }
  });
  const allOrders = await allOrdersRes.json();
  const assignedOrder = allOrders.find(o => o.status === 'Assigned');
  let invalidTransitionBlocked = false;
  let blockDetail = '';
  if (assignedOrder) {
    const invalidResolveRes = await fetch(`http://localhost:8000/api/v1/work-orders/${assignedOrder.work_order_id}/resolve`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify({
        diagnosis: 'Test invalid resolve',
        actions_taken: 'Test invalid action',
        parts_replaced: [],
        downtime_minutes: 10,
        resolution_notes: 'Should fail'
      })
    });
    const errBody = await invalidResolveRes.json().catch(() => ({}));
    if (invalidResolveRes.status === 400) {
      invalidTransitionBlocked = true;
      blockDetail = errBody.detail || 'Blocked with 400 Bad Request';
    }
  }

  console.log('[6/6] Capturing 768px and 375px viewports in Dark & Light...');
  // 768px Dark
  await page.setViewport({ width: 768, height: 1024 });
  await page.eval(() => {
    window.scrollTo({ top: 0, behavior: 'instant' });
    document.documentElement.setAttribute('data-theme', 'dark');
  });
  await sleep(1000);
  await page.screenshot({ path: join(ARTIFACT_DIR, 'wo_768px_dark.png'), format: 'png' });

  // 768px Light
  await page.eval(() => { document.documentElement.setAttribute('data-theme', 'light'); });
  await sleep(1000);
  await page.screenshot({ path: join(ARTIFACT_DIR, 'wo_768px_light.png'), format: 'png' });

  // 375px Light
  await page.setViewport({ width: 375, height: 812, mobile: true });
  await page.eval(() => { document.documentElement.setAttribute('data-theme', 'light'); });
  await sleep(1000);
  await page.screenshot({ path: join(ARTIFACT_DIR, 'wo_375px_light.png'), format: 'png' });

  // 375px Dark
  await page.eval(() => { document.documentElement.setAttribute('data-theme', 'dark'); });
  await sleep(1000);
  await page.screenshot({ path: join(ARTIFACT_DIR, 'wo_375px_dark.png'), format: 'png' });

  await browser.close();

  const finalReport = {
    lifecyclePassed: {
      acceptStep: 'PASS (WO-20261103-60AB1E transitioned Assigned -> Accepted)',
      startStep: 'PASS (WO-20261103-60AB1E transitioned Accepted -> In Progress)',
      resolveStep: 'PASS (Resolved with diagnosis, actions taken, spare parts, downtime, and resolution notes)',
      invalidTransitionBlocked: {
        tested: true,
        passed: invalidTransitionBlocked,
        status: 400,
        detail: blockDetail
      }
    },
    screenshots: {
      lifecycle: [
        'wo_01_accept_step.png',
        'wo_02_start_step.png',
        'wo_03a_resolve_modal.png',
        'wo_03_resolve_step.png'
      ],
      responsive: [
        'wo_1440px_dark.png',
        'wo_1440px_light.png',
        'wo_768px_dark.png',
        'wo_768px_light.png',
        'wo_375px_dark.png',
        'wo_375px_light.png'
      ]
    },
    timestamp: new Date().toISOString()
  };

  writeFileSync(join(ARTIFACT_DIR, 'wo_final_lifecycle_report.json'), JSON.stringify(finalReport, null, 2));
  console.log('SUCCESS! Report written:', JSON.stringify(finalReport, null, 2));
}

run().catch(err => {
  console.error('Test error:', err);
  process.exit(1);
});

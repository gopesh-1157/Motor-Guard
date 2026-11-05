import { Browser, sleep } from '../.agents/skills/design-taste-frontend/scripts/lib/cdp.mjs';
import fs from 'fs';

const ARTIFACT_DIR = 'C:/Users/gopes/.gemini/antigravity/brain/8074a34a-ec58-4570-b5aa-54093d6ef762';

async function auditDeployedFrontend() {
  const browser = await Browser.launch({ width: 1440, height: 900 });
  const page = await browser.newPage({ width: 1440, height: 900 });

  const networkErrors = [];
  const consoleMessages = [];

  // Enable network monitoring
  await page.send('Network.enable');
  browser.on(page.sessionId, 'Network.responseReceived', (params) => {
    if (params.response.status >= 400) {
      networkErrors.push({
        url: params.response.url,
        status: params.response.status,
        statusText: params.response.statusText,
      });
    }
  });

  browser.on(page.sessionId, 'Runtime.consoleAPICalled', (params) => {
    const text = params.args.map(a => a.value || a.description || '').join(' ');
    consoleMessages.push({ type: params.type, text });
  });

  console.log('--- 1. LOADING DEPLOYED FRONTEND (DESKTOP) ---');
  await page.goto('https://motor-guard-sandy.vercel.app/', { timeoutMs: 25000, settleMs: 3000 });
  await page.screenshot({ path: `${ARTIFACT_DIR}/deployed_01_landing_desktop.png`, format: 'png' });
  console.log('Saved deployed_01_landing_desktop.png');

  // Check mobile viewport
  console.log('--- 2. MOBILE VIEWPORT (390x844) ---');
  await page.setViewport({ width: 390, height: 844, mobile: true });
  await sleep(1500);
  await page.screenshot({ path: `${ARTIFACT_DIR}/deployed_02_landing_mobile.png`, format: 'png' });
  console.log('Saved deployed_02_landing_mobile.png');

  // Reset viewport
  await page.setViewport({ width: 1440, height: 900, mobile: false });
  await sleep(1000);

  // Click Sign In button or open RBAC login modal
  console.log('--- 3. OPEN LOGIN MODAL ---');
  await page.eval(() => {
    const btn = Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('Sign In') || b.innerText.includes('Login'));
    if (btn) btn.click();
  });
  await sleep(1200);
  await page.screenshot({ path: `${ARTIFACT_DIR}/deployed_03_login_modal.png`, format: 'png' });
  console.log('Saved deployed_03_login_modal.png');

  // Perform login on deployed site with admin
  console.log('--- 4. AUTHENTICATING AS ADMIN ON DEPLOYED SITE ---');
  const loginResult = await page.eval(async () => {
    try {
      const res = await fetch('/api/v1/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: 'admin', password: 'adminpassword123' }),
      });
      const data = await res.json();
      if (res.ok) {
        localStorage.setItem('motorguard_auth_token', data.access_token);
        localStorage.setItem('motorguard_auth_user', JSON.stringify(data.user));
        return { success: true, user: data.user };
      }
      return { success: false, status: res.status, data };
    } catch (e) {
      return { success: false, error: e.message };
    }
  });
  console.log('Login Result:', JSON.stringify(loginResult, null, 2));

  // Reload page to activate authenticated state
  await page.goto('https://motor-guard-sandy.vercel.app/#overview', { timeoutMs: 25000, settleMs: 3000 });
  await page.screenshot({ path: `${ARTIFACT_DIR}/deployed_04_admin_overview.png`, format: 'png' });
  console.log('Saved deployed_04_admin_overview.png');

  // Inspect each tab as Admin
  const tabs = [
    { name: 'fleet', path: 'fleet', file: 'deployed_05_fleet.png' },
    { name: 'live', path: 'live', file: 'deployed_06_live.png' },
    { name: 'twin', path: 'twin', file: 'deployed_07_twin.png' },
    { name: 'analytics', path: 'analytics', file: 'deployed_08_analytics.png' },
    { name: 'alerts', path: 'alerts', file: 'deployed_09_alerts.png' },
    { name: 'maintenance', path: 'maintenance', file: 'deployed_10_work_orders.png' },
    { name: 'devices', path: 'devices', file: 'deployed_11_devices.png' },
    { name: 'users', path: 'users', file: 'deployed_12_users.png' },
    { name: 'reports', path: 'reports', file: 'deployed_13_reports.png' },
    { name: 'settings', path: 'settings', file: 'deployed_14_settings.png' },
  ];

  const tabAuditResults = [];

  for (const t of tabs) {
    console.log(`Auditing tab: ${t.name} ...`);
    await page.eval((hash) => {
      window.location.hash = hash;
      window.dispatchEvent(new HashChangeEvent('hashchange'));
    }, t.path);
    await sleep(2500);

    const tabState = await page.eval(() => {
      const h1 = document.querySelector('h1')?.innerText || '';
      const h2 = document.querySelector('h2')?.innerText || '';
      const bodyText = document.body.innerText;
      const hasErrors = bodyText.includes('Error') || bodyText.includes('failed') || bodyText.includes('Unavailable');
      const tableRows = document.querySelectorAll('tbody tr').length;
      const cards = document.querySelectorAll('.card, .scada-card, .metric-card').length;
      return { header: h1 || h2, hasErrors, tableRows, cards, preview: bodyText.slice(0, 300) };
    });

    await page.screenshot({ path: `${ARTIFACT_DIR}/${t.file}`, format: 'png' });
    console.log(`Saved ${t.file}`);
    tabAuditResults.push({ ...t, state: tabState });
  }

  // Save full audit data
  const reportData = {
    loginResult,
    tabAuditResults,
    networkErrors,
    consoleMessages: consoleMessages.slice(-50), // last 50 logs
  };

  fs.writeFileSync(`${ARTIFACT_DIR}/deployed_audit_summary.json`, JSON.stringify(reportData, null, 2));
  console.log('Saved deployed_audit_summary.json');

  await browser.close();
  console.log('DEPLOYED WEBSITE AUDIT COMPLETED!');
}

auditDeployedFrontend().catch(err => {
  console.error('Audit failed:', err);
  process.exit(1);
});

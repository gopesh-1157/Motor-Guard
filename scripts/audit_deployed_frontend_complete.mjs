import { Browser, sleep } from '../.agents/skills/design-taste-frontend/scripts/lib/cdp.mjs';
import fs from 'fs';

const ARTIFACT_DIR = 'C:/Users/gopes/.gemini/antigravity/brain/8074a34a-ec58-4570-b5aa-54093d6ef762';

async function getAdminSession() {
  const res = await fetch('https://motor-guard.onrender.com/api/v1/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: 'admin', password: 'adminpassword123' }),
  });
  const data = await res.json();
  if (!res.ok) throw new Error('Admin login failed: ' + JSON.stringify(data));
  return { token: data.access_token, user: data.user };
}

async function auditDeployed() {
  console.log('Fetching Admin token from Render backend...');
  const session = await getAdminSession();
  console.log('Token acquired for admin.');

  const browser = await Browser.launch({ width: 1440, height: 900 });
  const page = await browser.newPage({ width: 1440, height: 900 });

  const networkErrors = [];
  const consoleMessages = [];

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

  // 1. Visit landing page
  console.log('1. Loading https://motor-guard-sandy.vercel.app/ ...');
  await page.goto('https://motor-guard-sandy.vercel.app/', { timeoutMs: 30000, settleMs: 2000 });
  await page.screenshot({ path: `${ARTIFACT_DIR}/deployed_01_landing_desktop.png`, format: 'png' });
  console.log('Saved deployed_01_landing_desktop.png');

  // 2. Mobile landing
  await page.setViewport({ width: 390, height: 844, mobile: true });
  await sleep(1500);
  await page.screenshot({ path: `${ARTIFACT_DIR}/deployed_02_landing_mobile.png`, format: 'png' });
  console.log('Saved deployed_02_landing_mobile.png');

  // 3. Inject authenticated admin session
  await page.setViewport({ width: 1440, height: 900, mobile: false });
  await page.eval((s) => {
    localStorage.setItem('motorguard_auth_token', s.token);
    localStorage.setItem('motorguard_auth_user', JSON.stringify(s.user));
  }, session);

  // 4. Reload into authenticated Overview
  console.log('4. Navigating to authenticated Overview (#overview)...');
  await page.goto('https://motor-guard-sandy.vercel.app/#overview', { timeoutMs: 30000, settleMs: 3000 });
  await page.screenshot({ path: `${ARTIFACT_DIR}/deployed_04_admin_overview.png`, format: 'png' });
  console.log('Saved deployed_04_admin_overview.png');

  // 5. Test each navigation tab
  const tabs = [
    { name: 'fleet', hash: 'fleet', file: 'deployed_05_fleet.png' },
    { name: 'live', hash: 'live', file: 'deployed_06_live.png' },
    { name: 'twin', hash: 'twin', file: 'deployed_07_twin.png' },
    { name: 'analytics', hash: 'analytics', file: 'deployed_08_analytics.png' },
    { name: 'alerts', hash: 'alerts', file: 'deployed_09_alerts.png' },
    { name: 'maintenance', hash: 'maintenance', file: 'deployed_10_work_orders.png' },
    { name: 'devices', hash: 'devices', file: 'deployed_11_devices.png' },
    { name: 'users', hash: 'users', file: 'deployed_12_users.png' },
    { name: 'reports', hash: 'reports', file: 'deployed_13_reports.png' },
    { name: 'settings', hash: 'settings', file: 'deployed_14_settings.png' },
  ];

  const tabAuditResults = [];

  for (const t of tabs) {
    console.log(`Auditing tab: ${t.name} (#${t.hash}) ...`);
    await page.eval((hash) => {
      window.location.hash = hash;
      window.dispatchEvent(new HashChangeEvent('hashchange'));
    }, t.hash);
    await sleep(2500);

    const tabState = await page.eval(() => {
      const h1 = document.querySelector('h1')?.innerText || '';
      const h2 = document.querySelector('h2')?.innerText || '';
      const bodyText = document.body.innerText;
      const hasErrors = bodyText.includes('Error') || bodyText.includes('failed') || bodyText.includes('Unavailable');
      const tableRows = document.querySelectorAll('tbody tr').length;
      return { header: h1 || h2, hasErrors, tableRows, preview: bodyText.slice(0, 200).replace(/\n/g, ' ') };
    });

    await page.screenshot({ path: `${ARTIFACT_DIR}/${t.file}`, format: 'png' });
    console.log(`Saved ${t.file} -> Header: "${tabState.header}", Rows: ${tabState.tableRows}, Errors: ${tabState.hasErrors}`);
    tabAuditResults.push({ ...t, state: tabState });
  }

  // 6. Mobile authenticated overview
  await page.setViewport({ width: 390, height: 844, mobile: true });
  await page.eval(() => {
    window.location.hash = 'overview';
    window.dispatchEvent(new HashChangeEvent('hashchange'));
  });
  await sleep(1500);
  await page.screenshot({ path: `${ARTIFACT_DIR}/deployed_15_admin_overview_mobile.png`, format: 'png' });
  console.log('Saved deployed_15_admin_overview_mobile.png');

  const auditReport = {
    timestamp: new Date().toISOString(),
    sessionUser: session.user,
    tabAuditResults,
    networkErrors,
    consoleMessages: consoleMessages.slice(-50),
  };

  fs.writeFileSync(`${ARTIFACT_DIR}/deployed_audit_summary.json`, JSON.stringify(auditReport, null, 2));
  console.log('Saved deployed_audit_summary.json');

  await browser.close();
  console.log('AUDIT COMPLETE!');
}

auditDeployed().catch(err => {
  console.error('Audit failed:', err);
  process.exit(1);
});

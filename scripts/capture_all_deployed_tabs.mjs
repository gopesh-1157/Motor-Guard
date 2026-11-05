import { Browser, sleep } from '../.agents/skills/design-taste-frontend/scripts/lib/cdp.mjs';
import fs from 'fs';

const ARTIFACT_DIR = 'C:/Users/gopes/.gemini/antigravity/brain/8074a34a-ec58-4570-b5aa-54093d6ef762';

async function captureAllDeployedTabs() {
  const browser = await Browser.launch({ width: 1440, height: 900 });
  const page = await browser.newPage({ width: 1440, height: 900 });

  const networkErrors = [];
  const consoleMessages = [];

  await page.send('Network.enable');
  browser.on(page.sessionId, 'Network.responseReceived', (p) => {
    if (p.response.status >= 400) {
      networkErrors.push({
        url: p.response.url,
        status: p.response.status,
        statusText: p.response.statusText,
      });
    }
  });

  browser.on(page.sessionId, 'Runtime.consoleAPICalled', (p) => {
    const text = p.args.map(a => a.value || a.description || '').join(' ');
    consoleMessages.push({ type: p.type, text });
  });

  // Login interactively
  await page.goto('https://motor-guard-sandy.vercel.app/', { timeoutMs: 30000, settleMs: 2000 });
  await page.eval(() => {
    const btn = Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('AUTHORIZED SIGN IN') || b.innerText.includes('Secure sign in'));
    if (btn) btn.click();
  });
  await sleep(1500);

  await page.eval(() => {
    const setVal = (el, val) => {
      const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
      setter.call(el, val);
      el.dispatchEvent(new Event('input', { bubbles: true }));
      el.dispatchEvent(new Event('change', { bubbles: true }));
    };

    const userInput = document.querySelector('input.rbac-input[type="text"]');
    const pwdInput = document.querySelector('input.rbac-input[type="password"]');
    setVal(userInput, 'admin');
    setVal(pwdInput, 'adminpassword123');

    const submitBtn = document.querySelector('button.btn-rbac-submit') || document.querySelector('button[type="submit"]');
    if (submitBtn) submitBtn.click();
  });
  await sleep(4000);

  // Define tabs to click via sidebar buttons
  const tabNames = [
    'Overview',
    'Motor Fleet',
    'Live Monitoring',
    'Analytics',
    'Alerts & Events',
    'Work Orders',
    'ESP32 Devices',
    'User Management',
    'Reports',
    'Settings',
  ];

  const tabAuditResults = [];

  for (const tName of tabNames) {
    console.log(`Clicking tab: "${tName}" ...`);
    await page.eval((label) => {
      const btn = Array.from(document.querySelectorAll('.sidebar-item-btn')).find(b => b.innerText.includes(label));
      if (btn) btn.click();
    }, tName);
    await sleep(2500);

    const safeName = tName.toLowerCase().replace(/[^a-z0-9]/g, '_');
    const screenshotPath = `${ARTIFACT_DIR}/deployed_tab_${safeName}.png`;
    await page.screenshot({ path: screenshotPath, format: 'png' });

    const info = await page.eval(() => {
      const h1 = document.querySelector('h1')?.innerText || '';
      const h2 = document.querySelector('h2')?.innerText || '';
      const body = document.body.innerText;
      const hasErrorBanner = body.includes('Error') || body.includes('Unavailable') || body.includes('Failed to fetch');
      const tableRows = document.querySelectorAll('tbody tr').length;
      return { h1, h2, hasErrorBanner, tableRows, preview: body.slice(0, 200).replace(/\n/g, ' ') };
    });

    console.log(`  -> Saved ${screenshotPath} | Header: "${info.h1 || info.h2}" | Error: ${info.hasErrorBanner}`);
    tabAuditResults.push({ name: tName, ...info });
  }

  // Mobile responsiveness check
  console.log('Testing mobile responsiveness...');
  await page.setViewport({ width: 390, height: 844, mobile: true });
  await sleep(1500);
  await page.screenshot({ path: `${ARTIFACT_DIR}/deployed_mobile_authenticated.png`, format: 'png' });
  console.log('Saved deployed_mobile_authenticated.png');

  const report = {
    timestamp: new Date().toISOString(),
    tabAuditResults,
    networkErrors,
    recentConsoleMessages: consoleMessages.slice(-50),
  };

  fs.writeFileSync(`${ARTIFACT_DIR}/deployed_tabs_audit_report.json`, JSON.stringify(report, null, 2));
  console.log('Saved deployed_tabs_audit_report.json');

  await browser.close();
  console.log('ALL DEPLOYED TABS AUDITED!');
}

captureAllDeployedTabs().catch(console.error);

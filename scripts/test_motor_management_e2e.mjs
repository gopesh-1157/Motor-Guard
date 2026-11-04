import { Browser, sleep } from '../.agents/skills/design-taste-frontend/scripts/lib/cdp.mjs';
import { mkdirSync } from 'node:fs';
import { join } from 'node:path';

const ARTIFACT_DIR = 'C:/Users/gopes/.gemini/antigravity-ide/brain/f363d4bc-05f0-48db-8381-51e7db45ebcb';
mkdirSync(ARTIFACT_DIR, { recursive: true });

async function run() {
  console.log('[1/10] Authenticating as admin on isolated test backend (port 8001)...');
  const loginRes = await fetch('http://127.0.0.1:8001/api/v1/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: 'admin', password: 'adminpassword123' })
  });
  if (!loginRes.ok) throw new Error('Login failed: ' + (await loginRes.text()));
  const loginData = await loginRes.json();
  const token = loginData.access_token;
  const user = loginData.user;
  console.log('Logged in as:', user.username, 'Role:', user.role);

  // Clean up any pre-existing MTR-775-E2E in test backend first
  try {
    const delRes = await fetch('http://127.0.0.1:8001/api/v1/motors/MTR-775-E2E', {
      method: 'DELETE',
      headers: { 'Authorization': `Bearer ${token}` }
    });
    console.log('Pre-test cleanup of MTR-775-E2E status:', delRes.status);
  } catch (err) {
    console.log('Pre-test cleanup note:', err.message);
  }

  console.log('[2/10] Launching browser at 1440x900...');
  const browser = await Browser.launch({ width: 1440, height: 900 });
  const page = await browser.newPage({ width: 1440, height: 900 });

  // Navigate to test Vite frontend (port 5174 -> proxies to 8001)
  console.log('[3/10] Loading test Vite app (port 5174)...');
  await page.goto('http://127.0.0.1:5174/', { timeoutMs: 15000, settleMs: 1000 });
  await page.eval(({ t, u }) => {
    localStorage.setItem('motorguard_auth_token', t);
    localStorage.setItem('motorguard_auth_user', JSON.stringify(u));
    localStorage.setItem('motorguard_theme', 'dark');
    localStorage.setItem('motorguard_theme_v5', 'dark');
  }, { t: token, u: user });

  await page.goto('http://127.0.0.1:5174/', { timeoutMs: 15000, settleMs: 1500 });

  // Navigate to Motor Fleet tab
  console.log('[4/10] Navigating to Motor Fleet...');
  await page.eval(() => {
    const btn = Array.from(document.querySelectorAll('button, a, .nav-item, [role="button"]')).find(el => el.textContent.includes('Motor Fleet'));
    if (btn) btn.click();
  });
  await sleep(1500);

  // Capture 1440px Dark & Light
  console.log('[5/10] Capturing 1440px Dark & Light...');
  await page.screenshot({ path: join(ARTIFACT_DIR, 'motormanagement_1440px_dark.png'), format: 'png' });

  await page.eval(() => {
    document.documentElement.setAttribute('data-theme', 'light');
    localStorage.setItem('motorguard_theme', 'light');
  });
  await sleep(800);
  await page.screenshot({ path: join(ARTIFACT_DIR, 'motormanagement_1440px_light.png'), format: 'png' });

  // Switch back to dark
  await page.eval(() => {
    document.documentElement.setAttribute('data-theme', 'dark');
    localStorage.setItem('motorguard_theme', 'dark');
  });
  await sleep(600);

  // Capture 768px Dark & Light
  console.log('[6/10] Capturing 768px Dark & Light...');
  const page768 = await browser.newPage({ width: 768, height: 1024 });
  await page768.goto('http://127.0.0.1:5174/', { timeoutMs: 15000, settleMs: 1000 });
  await page768.eval(({ t, u }) => {
    localStorage.setItem('motorguard_auth_token', t);
    localStorage.setItem('motorguard_auth_user', JSON.stringify(u));
    localStorage.setItem('motorguard_theme', 'dark');
    localStorage.setItem('motorguard_theme_v5', 'dark');
  }, { t: token, u: user });
  await page768.goto('http://127.0.0.1:5174/', { timeoutMs: 15000, settleMs: 1500 });
  await page768.eval(() => {
    const btn = Array.from(document.querySelectorAll('button, a, .nav-item, [role="button"]')).find(el => el.textContent.includes('Motor Fleet'));
    if (btn) btn.click();
  });
  await sleep(1500);
  await page768.screenshot({ path: join(ARTIFACT_DIR, 'motormanagement_768px_dark.png'), format: 'png' });

  await page768.eval(() => {
    document.documentElement.setAttribute('data-theme', 'light');
    localStorage.setItem('motorguard_theme', 'light');
  });
  await sleep(800);
  await page768.screenshot({ path: join(ARTIFACT_DIR, 'motormanagement_768px_light.png'), format: 'png' });
  await page768.close();

  // Capture 375px Dark & Light
  console.log('[7/10] Capturing 375px Dark & Light...');
  const page375 = await browser.newPage({ width: 375, height: 812, mobile: true });
  await page375.goto('http://127.0.0.1:5174/', { timeoutMs: 15000, settleMs: 1000 });
  await page375.eval(({ t, u }) => {
    localStorage.setItem('motorguard_auth_token', t);
    localStorage.setItem('motorguard_auth_user', JSON.stringify(u));
    localStorage.setItem('motorguard_theme', 'dark');
    localStorage.setItem('motorguard_theme_v5', 'dark');
  }, { t: token, u: user });
  await page375.goto('http://127.0.0.1:5174/', { timeoutMs: 15000, settleMs: 1500 });
  await page375.eval(() => {
    const btn = Array.from(document.querySelectorAll('button, a, .nav-item, [role="button"]')).find(el => el.textContent.includes('Motor Fleet'));
    if (btn) btn.click();
  });
  await sleep(1500);
  await page375.screenshot({ path: join(ARTIFACT_DIR, 'motormanagement_375px_dark.png'), format: 'png' });

  await page375.eval(() => {
    document.documentElement.setAttribute('data-theme', 'light');
    localStorage.setItem('motorguard_theme', 'light');
  });
  await sleep(800);
  await page375.screenshot({ path: join(ARTIFACT_DIR, 'motormanagement_375px_light.png'), format: 'png' });
  await page375.close();

  // Flow 1: ADD MOTOR FLOW on 1440px desktop
  console.log('[8/10] Executing Flow 1: Add Motor via UI Registration Wizard...');
  await page.eval(() => {
    const regBtn = Array.from(document.querySelectorAll('button')).find(b => b.textContent.includes('Register Physical Motor'));
    if (regBtn) regBtn.click();
  });
  await sleep(1000);

  await page.screenshot({ path: join(ARTIFACT_DIR, 'motor_flow_01_wizard_open.png'), format: 'png' });

  // Fill in Step 1
  await page.eval(() => {
    function setInput(el, val) {
      const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
      setter.call(el, val);
      el.dispatchEvent(new Event('input', { bubbles: true }));
      el.dispatchEvent(new Event('change', { bubbles: true }));
    }
    const inputs = Array.from(document.querySelectorAll('.modal-container input[type="text"]'));
    if (inputs[0]) setInput(inputs[0], 'MTR-775-E2E');
    if (inputs[1]) setInput(inputs[1], 'E2E Secondary Coolant Pump');
  });
  await sleep(600);

  // Advance through steps 1 -> 2 -> 3 -> 4 -> 5 -> 6 -> 7 using Next Step button
  for (let s = 1; s <= 6; s++) {
    console.log(`Advancing wizard step ${s} -> ${s + 1}...`);
    await page.eval(() => {
      const nextBtn = Array.from(document.querySelectorAll('.modal-container button')).find(b => b.textContent.includes('Next Step'));
      if (nextBtn) nextBtn.click();
    });
    await sleep(500);
  }

  // On Step 7, click Confirm & Commit
  console.log('Committing motor registration on Step 7...');
  await page.eval(() => {
    const commitBtn = Array.from(document.querySelectorAll('.modal-container button')).find(b => b.textContent.includes('Confirm & Commit'));
    if (commitBtn) commitBtn.click();
  });
  await sleep(3000);

  await page.screenshot({ path: join(ARTIFACT_DIR, 'motor_flow_02_motor_added.png'), format: 'png' });

  // Flow 2: EDIT MOTOR & CUSTOM ALARM LIMITS FLOW
  console.log('[9/10] Executing Flow 2: Edit Motor Configuration & Custom Alarm Limits...');
  await page.eval(() => {
    const rows = Array.from(document.querySelectorAll('tbody tr'));
    const targetRow = rows.find(r => r.textContent.includes('MTR-775-E2E'));
    if (targetRow) {
      const configBtn = Array.from(targetRow.querySelectorAll('button')).find(b => b.textContent.includes('Config'));
      if (configBtn) configBtn.click();
    }
  });
  await sleep(1200);

  await page.screenshot({ path: join(ARTIFACT_DIR, 'motor_flow_03_edit_modal.png'), format: 'png' });

  // Adjust thresholds
  await page.eval(() => {
    function setInput(el, val) {
      const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
      setter.call(el, val);
      el.dispatchEvent(new Event('input', { bubbles: true }));
      el.dispatchEvent(new Event('change', { bubbles: true }));
    }
    const numInputs = Array.from(document.querySelectorAll('.modal-container input[type="number"]'));
    // Order: tempWarn, tempCrit, currWarn, currCrit, vibWarn, vibCrit
    if (numInputs[0]) setInput(numInputs[0], '52.5'); // Temp warn
    if (numInputs[1]) setInput(numInputs[1], '82.0'); // Temp crit
    if (numInputs[4]) setInput(numInputs[4], '2.4');  // Vib warn
    if (numInputs[5]) setInput(numInputs[5], '4.8');  // Vib crit
  });
  await sleep(600);

  // Click Save Changes button
  await page.eval(() => {
    const saveBtn = Array.from(document.querySelectorAll('.modal-container button')).find(b => b.textContent.includes('Save Changes'));
    if (saveBtn) saveBtn.click();
  });
  await sleep(2500);

  await page.screenshot({ path: join(ARTIFACT_DIR, 'motor_flow_04_limits_saved.png'), format: 'png' });

  // Flow 3: DELETE / DISABLE MOTOR FLOW
  console.log('[10/10] Executing Flow 3: Deactivate/Disable Motor in UI...');
  await page.eval(() => {
    const rows = Array.from(document.querySelectorAll('tbody tr'));
    const targetRow = rows.find(r => r.textContent.includes('MTR-775-E2E'));
    if (targetRow) {
      // Find button with PowerOff icon or title "Deactivate motor"
      const disableBtn = targetRow.querySelector('button[title*="Deactivate"]');
      if (disableBtn) disableBtn.click();
    }
  });
  await sleep(1200);

  await page.screenshot({ path: join(ARTIFACT_DIR, 'motor_flow_05_disable_modal.png'), format: 'png' });

  // Click Confirm Deactivation
  await page.eval(() => {
    const confirmBtn = Array.from(document.querySelectorAll('.modal-container button')).find(b => b.textContent.includes('Confirm Deactivation'));
    if (confirmBtn) confirmBtn.click();
  });
  await sleep(2500);

  await page.screenshot({ path: join(ARTIFACT_DIR, 'motor_flow_06_motor_disabled.png'), format: 'png' });

  console.log('SUCCESS: All UI test flows and responsive captures completed successfully!');
  await browser.close();
}

run().catch(err => {
  console.error('Test execution failed:', err);
  process.exit(1);
});

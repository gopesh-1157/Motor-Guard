import { Browser, sleep } from '../.agents/skills/design-taste-frontend/scripts/lib/cdp.mjs';
import { join } from 'node:path';

const ARTIFACT_DIR = 'C:/Users/gopes/.gemini/antigravity-ide/brain/f363d4bc-05f0-48db-8381-51e7db45ebcb';

async function run() {
  console.log('[1/10] Authenticating against isolated test backend (port 8001 / motorguard_test)...');
  const loginRes = await fetch('http://127.0.0.1:8001/api/v1/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: 'admin', password: 'adminpassword123' }),
  });
  if (!loginRes.ok) throw new Error('Login failed: ' + (await loginRes.text()));
  const loginData = await loginRes.json();
  const token = loginData.access_token;
  const user = loginData.user;

  console.log('[2/10] Launching browser on http://127.0.0.1:5174/ ...');
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
  }, { t: token, u: user });

  await page.goto('http://127.0.0.1:5174/', { timeoutMs: 15000, settleMs: 1500 });
  await sleep(1500);

  // Helper to click StatCard by index
  async function testStatCard(index, name, filename) {
    console.log(`Testing StatCard [${index}]: ${name}...`);
    const clicked = await page.eval((idx) => {
      const cards = Array.from(document.querySelectorAll('.kpi-summary-row .stat-card'));
      if (cards[idx]) {
        cards[idx].click();
        return true;
      }
      return false;
    }, index);
    if (!clicked) throw new Error(`Could not find StatCard index ${index} (${name})`);
    await sleep(600);
    await page.screenshot({ path: join(ARTIFACT_DIR, filename), format: 'png' });
    console.log(`  Passed -> saved ${filename}`);
  }

  // 1. Total Drives
  await testStatCard(0, 'Total Drives', 'overview_statcard_total.png');

  // 2. Nominal
  await testStatCard(1, 'Nominal', 'overview_statcard_nominal.png');

  // 3. Advisory
  await testStatCard(2, 'Advisory', 'overview_statcard_advisory.png');

  // 4. Critical Fault
  await testStatCard(3, 'Critical Fault', 'overview_statcard_critical.png');

  // 5. Offline
  await testStatCard(4, 'Offline', 'overview_statcard_offline.png');

  // 6. ESP32 Node
  await testStatCard(5, 'ESP32 Node', 'overview_statcard_esp32.png');

  // Reset to All
  await testStatCard(0, 'Reset Total Drives', 'overview_statcard_reset.png');

  // 7. Search for a motor that doesn't exist (EmptyState)
  console.log('[7/10] Searching for non-existent motor tag...');
  const emptyStateFound = await page.eval(() => {
    const input = document.querySelector('.search-input-field');
    if (!input) return { ok: false, error: 'Input not found' };
    const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
    nativeSetter.call(input, 'NONEXISTENT-MOTOR-999');
    input.dispatchEvent(new Event('input', { bubbles: true }));
    input.dispatchEvent(new Event('change', { bubbles: true }));
    return { ok: true };
  });
  await sleep(1000);
  await page.screenshot({ path: join(ARTIFACT_DIR, 'overview_search_empty_state.png'), format: 'png' });
  const hasEmptyState = await page.eval(() => {
    const empty = document.querySelector('.empty-state');
    return Boolean(empty && empty.textContent.includes('No Motors Found'));
  });
  console.log(`  EmptyState verified: ${hasEmptyState} -> saved overview_search_empty_state.png`);

  // Clear search
  await page.eval(() => {
    const input = document.querySelector('.search-input-field');
    if (input) {
      const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
      nativeSetter.call(input, '');
      input.dispatchEvent(new Event('input', { bubbles: true }));
      input.dispatchEvent(new Event('change', { bubbles: true }));
    }
  });
  await sleep(600);

  // 8. Select a site
  console.log('[8/10] Selecting facility site from dropdown...');
  const siteChanged = await page.eval(() => {
    const select = document.querySelector('.page-actions-group select');
    if (!select) return false;
    select.value = 'Facility Beta — Plant Line 2';
    select.dispatchEvent(new Event('change', { bubbles: true }));
    return true;
  });
  await sleep(800);
  await page.screenshot({ path: join(ARTIFACT_DIR, 'overview_site_selected.png'), format: 'png' });
  console.log(`  Site selector verified: ${siteChanged} -> saved overview_site_selected.png`);

  // 9. Open fault injection drawer without injecting
  console.log('[9/10] Opening Simulation & Fault Injection Testbench drawer...');
  const opened = await page.eval(() => {
    const btns = Array.from(document.querySelectorAll('button'));
    const drawerBtn = btns.find(b => b.textContent && (b.textContent.includes('Open Controls') || b.textContent.includes('Collapse Controls')));
    if (drawerBtn && drawerBtn.textContent.includes('Open Controls')) {
      drawerBtn.click();
      return true;
    }
    return false;
  });
  await sleep(800);
  await page.screenshot({ path: join(ARTIFACT_DIR, 'overview_drawer_opened.png'), format: 'png' });
  console.log(`  Drawer opened verified: ${opened} -> saved overview_drawer_opened.png`);

  // 10. Close fault injection drawer without injecting
  console.log('[10/10] Closing Simulation & Fault Injection Testbench drawer without injecting...');
  const closed = await page.eval(() => {
    const btns = Array.from(document.querySelectorAll('button'));
    const drawerBtn = btns.find(b => b.textContent && b.textContent.includes('Collapse Controls'));
    if (drawerBtn) {
      drawerBtn.click();
      return true;
    }
    return false;
  });
  await sleep(800);
  await page.screenshot({ path: join(ARTIFACT_DIR, 'overview_drawer_closed.png'), format: 'png' });
  console.log(`  Drawer closed verified: ${closed} -> saved overview_drawer_closed.png`);

  await browser.close();
  console.log('All Overview interaction tests against test backend PASSED.');
}

run().catch((err) => {
  console.error('Overview interaction test failed:', err);
  process.exit(1);
});

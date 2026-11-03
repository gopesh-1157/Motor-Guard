import { Browser, sleep } from '../.agents/skills/design-taste-frontend/scripts/lib/cdp.mjs';
import { mkdirSync } from 'node:fs';
import { join } from 'node:path';

const ARTIFACT_DIR = 'C:/Users/gopes/.gemini/antigravity-ide/brain/f363d4bc-05f0-48db-8381-51e7db45ebcb';
mkdirSync(ARTIFACT_DIR, { recursive: true });

async function run() {
  console.log('[1/4] Logging in as admin...');
  const loginRes = await fetch('http://localhost:8000/api/v1/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: 'admin', password: 'adminpassword123' })
  });
  if (!loginRes.ok) throw new Error('Login failed: ' + (await loginRes.text()));
  const loginData = await loginRes.json();
  const token = loginData.access_token;
  const user = loginData.user;

  console.log('[2/4] Capturing 1440px Desktop...');
  const browser = await Browser.launch({ width: 1440, height: 900 });
  const page1440 = await browser.newPage({ width: 1440, height: 900 });

  await page1440.goto('http://localhost:5173/', { timeoutMs: 15000, settleMs: 1000 });
  await page1440.eval(({ t, u }) => {
    localStorage.setItem('motorguard_auth_token', t);
    localStorage.setItem('motorguard_token', t);
    localStorage.setItem('motorguard_auth_user', JSON.stringify(u));
    localStorage.setItem('motorguard_theme', 'dark');
    localStorage.setItem('motorguard_theme_v5', 'dark');
  }, { t: token, u: user });

  await page1440.goto('http://localhost:5173/', { timeoutMs: 15000, settleMs: 1500 });

  // Ensure Overview tab
  await page1440.eval(() => {
    const btn = Array.from(document.querySelectorAll('button, a, .nav-item')).find(el => el.textContent.includes('Overview') || el.id === 'nav-overview');
    if (btn) btn.click();
  });
  await sleep(2000);

  await page1440.screenshot({ path: join(ARTIFACT_DIR, 'overview_1440px_dark.png'), format: 'png' });
  console.log('Saved: overview_1440px_dark.png');

  // 1440px Light
  await page1440.eval(() => {
    document.documentElement.setAttribute('data-theme', 'light');
    localStorage.setItem('motorguard_theme', 'light');
    localStorage.setItem('motorguard_theme_v5', 'light');
  });
  await sleep(1000);
  await page1440.screenshot({ path: join(ARTIFACT_DIR, 'overview_1440px_light.png'), format: 'png' });
  console.log('Saved: overview_1440px_light.png');
  await page1440.close();

  // 768px Tablet
  console.log('[3/4] Capturing 768px Tablet...');
  const page768 = await browser.newPage({ width: 768, height: 1024 });
  await page768.goto('http://localhost:5173/', { timeoutMs: 15000, settleMs: 1000 });
  await page768.eval(({ t, u }) => {
    localStorage.setItem('motorguard_auth_token', t);
    localStorage.setItem('motorguard_token', t);
    localStorage.setItem('motorguard_auth_user', JSON.stringify(u));
    localStorage.setItem('motorguard_theme', 'dark');
    localStorage.setItem('motorguard_theme_v5', 'dark');
  }, { t: token, u: user });
  await page768.goto('http://localhost:5173/', { timeoutMs: 15000, settleMs: 1500 });
  await sleep(2000);

  await page768.screenshot({ path: join(ARTIFACT_DIR, 'overview_768px_dark.png'), format: 'png' });
  console.log('Saved: overview_768px_dark.png');

  await page768.eval(() => {
    document.documentElement.setAttribute('data-theme', 'light');
    localStorage.setItem('motorguard_theme', 'light');
    localStorage.setItem('motorguard_theme_v5', 'light');
  });
  await sleep(1000);
  await page768.screenshot({ path: join(ARTIFACT_DIR, 'overview_768px_light.png'), format: 'png' });
  console.log('Saved: overview_768px_light.png');
  await page768.close();

  // 375px Mobile
  console.log('[4/4] Capturing 375px Mobile...');
  const page375 = await browser.newPage({ width: 375, height: 812 });
  await page375.goto('http://localhost:5173/', { timeoutMs: 15000, settleMs: 1000 });
  await page375.eval(({ t, u }) => {
    localStorage.setItem('motorguard_auth_token', t);
    localStorage.setItem('motorguard_token', t);
    localStorage.setItem('motorguard_auth_user', JSON.stringify(u));
    localStorage.setItem('motorguard_theme', 'dark');
    localStorage.setItem('motorguard_theme_v5', 'dark');
  }, { t: token, u: user });
  await page375.goto('http://localhost:5173/', { timeoutMs: 15000, settleMs: 1500 });
  await sleep(2000);

  await page375.screenshot({ path: join(ARTIFACT_DIR, 'overview_375px_dark.png'), format: 'png' });
  console.log('Saved: overview_375px_dark.png');

  await page375.eval(() => {
    document.documentElement.setAttribute('data-theme', 'light');
    localStorage.setItem('motorguard_theme', 'light');
    localStorage.setItem('motorguard_theme_v5', 'light');
  });
  await sleep(1000);
  await page375.screenshot({ path: join(ARTIFACT_DIR, 'overview_375px_light.png'), format: 'png' });
  console.log('Saved: overview_375px_light.png');
  await page375.close();

  await browser.close();
  console.log('All Overview screenshots captured successfully!');
}

run().catch(err => {
  console.error('Overview capture failed:', err);
  process.exit(1);
});

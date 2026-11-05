import { Browser, sleep } from '../.agents/skills/design-taste-frontend/scripts/lib/cdp.mjs';

const ARTIFACT_DIR = 'C:/Users/gopes/.gemini/antigravity/brain/8074a34a-ec58-4570-b5aa-54093d6ef762';

async function testRealBrowserLogin() {
  const browser = await Browser.launch({ width: 1440, height: 900 });
  const page = await browser.newPage({ width: 1440, height: 900 });

  console.log('Navigating to deployed site...');
  await page.goto('https://motor-guard-sandy.vercel.app/', { timeoutMs: 30000, settleMs: 2000 });

  // Open modal
  console.log('Clicking Sign In button...');
  await page.eval(() => {
    const btn = Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('Sign In') || b.innerText.includes('Login'));
    if (btn) btn.click();
  });
  await sleep(1500);

  // Type admin and password
  console.log('Typing credentials...');
  await page.eval(() => {
    const inputs = document.querySelectorAll('input');
    for (const input of inputs) {
      if (input.type === 'text') {
        input.value = 'admin';
        input.dispatchEvent(new Event('input', { bubbles: true }));
      } else if (input.type === 'password') {
        input.value = 'adminpassword123';
        input.dispatchEvent(new Event('input', { bubbles: true }));
      }
    }
    const submitBtn = Array.from(document.querySelectorAll('button')).find(b => b.type === 'submit' || b.innerText.includes('Sign In') || b.innerText.includes('Authenticate'));
    if (submitBtn) submitBtn.click();
  });

  console.log('Submitted form. Waiting for authentication response...');
  await sleep(4000);

  const authState = await page.eval(() => {
    const user = localStorage.getItem('motorguard_auth_user');
    const token = localStorage.getItem('motorguard_auth_token');
    const header = document.querySelector('h1')?.innerText || document.querySelector('h2')?.innerText || '';
    const body = document.body.innerText.slice(0, 300).replace(/\n/g, ' ');
    return { hasUser: !!user, hasToken: !!token, header, body };
  });

  console.log('Auth State in Browser:', JSON.stringify(authState, null, 2));
  await page.screenshot({ path: `${ARTIFACT_DIR}/deployed_real_login_result.png`, format: 'png' });
  console.log('Saved deployed_real_login_result.png');

  await browser.close();
}

testRealBrowserLogin().catch(err => {
  console.error('Error:', err);
  process.exit(1);
});

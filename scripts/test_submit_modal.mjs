import { Browser, sleep } from '../.agents/skills/design-taste-frontend/scripts/lib/cdp.mjs';

const ARTIFACT_DIR = 'C:/Users/gopes/.gemini/antigravity/brain/8074a34a-ec58-4570-b5aa-54093d6ef762';

async function testSubmitModal() {
  const browser = await Browser.launch({ width: 1440, height: 900 });
  const page = await browser.newPage({ width: 1440, height: 900 });

  await page.send('Network.enable');
  browser.on(page.sessionId, 'Network.requestWillBeSent', (p) => {
    if (p.request.url.includes('auth') || p.request.url.includes('login')) {
      console.log('>>> HTTP REQUEST:', p.request.method, p.request.url, p.request.postData);
    }
  });

  browser.on(page.sessionId, 'Network.responseReceived', (p) => {
    if (p.response.url.includes('auth') || p.response.url.includes('login')) {
      console.log('<<< HTTP RESPONSE:', p.response.status, p.response.statusText, p.response.url);
    }
  });

  console.log('1. Loading site...');
  await page.goto('https://motor-guard-sandy.vercel.app/', { timeoutMs: 30000, settleMs: 2000 });

  console.log('2. Opening modal...');
  await page.eval(() => {
    const btn = Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('AUTHORIZED SIGN IN') || b.innerText.includes('Secure sign in'));
    if (btn) btn.click();
  });
  await sleep(1500);

  console.log('3. Filling form and clicking submit...');
  const res = await page.eval(() => {
    const setVal = (el, val) => {
      const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
      setter.call(el, val);
      el.dispatchEvent(new Event('input', { bubbles: true }));
      el.dispatchEvent(new Event('change', { bubbles: true }));
    };

    const userInput = document.querySelector('input.rbac-input[type="text"]');
    const pwdInput = document.querySelector('input.rbac-input[type="password"]');

    if (!userInput || !pwdInput) return { error: 'Inputs not found' };

    setVal(userInput, 'admin');
    setVal(pwdInput, 'adminpassword123');

    const submitBtn = document.querySelector('button.btn-rbac-submit') || document.querySelector('button[type="submit"]');
    if (submitBtn) {
      submitBtn.click();
      return { success: true, btnText: submitBtn.innerText };
    }
    return { error: 'Submit button not found' };
  });

  console.log('Submission trigger:', res);
  await sleep(5000);

  const finalState = await page.eval(() => {
    const u = localStorage.getItem('motorguard_auth_user');
    const t = localStorage.getItem('motorguard_auth_token');
    const sidebarItems = Array.from(document.querySelectorAll('.sidebar-item-btn')).map(b => b.innerText.trim());
    const h1 = document.querySelector('h1')?.innerText || '';
    return { hasUser: !!u, hasToken: !!t, sidebarItems, h1 };
  });

  console.log('Final state after login:', JSON.stringify(finalState, null, 2));
  await page.screenshot({ path: `${ARTIFACT_DIR}/deployed_authenticated_dashboard.png`, format: 'png' });
  console.log('Saved deployed_authenticated_dashboard.png');

  await browser.close();
}

testSubmitModal().catch(console.error);

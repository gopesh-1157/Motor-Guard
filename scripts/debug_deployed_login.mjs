import { Browser, sleep } from '../.agents/skills/design-taste-frontend/scripts/lib/cdp.mjs';

async function debugDeployedLogin() {
  const browser = await Browser.launch({ width: 1440, height: 900 });
  const page = await browser.newPage({ width: 1440, height: 900 });

  await page.send('Network.enable');
  browser.on(page.sessionId, 'Network.requestWillBeSent', (p) => {
    if (p.request.url.includes('auth') || p.request.url.includes('login')) {
      console.log('>>> REQUEST SENT:', p.request.method, p.request.url, p.request.postData);
    }
  });

  browser.on(page.sessionId, 'Network.responseReceived', (p) => {
    if (p.response.url.includes('auth') || p.response.url.includes('login')) {
      console.log('<<< RESPONSE RECEIVED:', p.response.status, p.response.statusText, p.response.url);
    }
  });

  browser.on(page.sessionId, 'Runtime.consoleAPICalled', (p) => {
    const text = p.args.map(a => a.value || a.description || '').join(' ');
    console.log('CONSOLE:', p.type, text);
  });

  await page.goto('https://motor-guard-sandy.vercel.app/', { timeoutMs: 30000, settleMs: 2000 });

  // Open modal
  await page.eval(() => {
    const btn = Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('Sign In') || b.innerText.includes('Login'));
    if (btn) btn.click();
  });
  await sleep(1500);

  // Fill inputs using React-compatible setter
  const submitSuccess = await page.eval(() => {
    const setReactValue = (input, val) => {
      const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
      setter.call(input, val);
      input.dispatchEvent(new Event('input', { bubbles: true }));
      input.dispatchEvent(new Event('change', { bubbles: true }));
    };

    const textInput = document.querySelector('input[type="text"], input:not([type="password"])');
    const pwdInput = document.querySelector('input[type="password"]');

    if (textInput && pwdInput) {
      setReactValue(textInput, 'admin');
      setReactValue(pwdInput, 'adminpassword123');

      const submitBtn = document.querySelector('form button[type="submit"]') || Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('Sign In') || b.innerText.includes('Authenticate'));
      if (submitBtn) {
        submitBtn.click();
        return true;
      }
    }
    return false;
  });

  console.log('Form inputs populated & submitted:', submitSuccess);
  await sleep(4000);

  const authState = await page.eval(() => {
    const user = localStorage.getItem('motorguard_auth_user');
    const token = localStorage.getItem('motorguard_auth_token');
    const header = document.querySelector('h1')?.innerText || document.querySelector('h2')?.innerText || '';
    return { hasUser: !!user, user: user ? JSON.parse(user) : null, hasToken: !!token, header };
  });

  console.log('Resulting Auth State:', JSON.stringify(authState, null, 2));
  await browser.close();
}

debugDeployedLogin().catch(err => {
  console.error('Error:', err);
  process.exit(1);
});

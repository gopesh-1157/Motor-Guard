import { Browser, sleep } from '../.agents/skills/design-taste-frontend/scripts/lib/cdp.mjs';

async function inspectModal() {
  const browser = await Browser.launch({ width: 1440, height: 900 });
  const page = await browser.newPage({ width: 1440, height: 900 });

  await page.goto('https://motor-guard-sandy.vercel.app/', { timeoutMs: 30000, settleMs: 2000 });

  // Look for sign in button
  const allButtons = await page.eval(() => Array.from(document.querySelectorAll('button')).map(b => b.innerText.trim()));
  console.log('Buttons on landing page:', allButtons);

  await page.eval(() => {
    const btn = Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('SIGN IN') || b.innerText.includes('Sign In') || b.innerText.includes('Login'));
    if (btn) btn.click();
  });
  await sleep(1500);

  const info = await page.eval(() => {
    const inputs = Array.from(document.querySelectorAll('input')).map(i => ({
      type: i.type,
      placeholder: i.placeholder,
      id: i.id,
      name: i.name,
      className: i.className,
    }));
    const forms = Array.from(document.querySelectorAll('form')).length;
    const modals = Array.from(document.querySelectorAll('[class*="modal"], [class*="dialog"], [class*="overlay"], [class*="popup"]')).map(el => el.className);
    const bodySnippet = document.body.innerHTML.slice(0, 1000);
    return { inputs, forms, modals, bodySnippet };
  });

  console.log('Modal DOM Info:', JSON.stringify(info, null, 2));
  await browser.close();
}

inspectModal().catch(console.error);

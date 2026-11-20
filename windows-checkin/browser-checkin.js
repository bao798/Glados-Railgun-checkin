// Local adaptation of badarch47/glados_checkin: normal page UI only.
import { selectCheckinButton, parseCookiePairs, hasRecordToday } from './ui-policy.js';

export async function browserCheckin({ domain, cookie, ua }) {
  if (domain !== 'glados.cloud') throw new Error('Only the configured GLaDOS origin is allowed.');
  const { chromium } = await import('playwright');
  const browser = await chromium.launch({ channel: 'msedge', headless: false });
  try {
    const context = await browser.newContext({ userAgent: ua, locale: 'zh-CN' });
    const pairs = parseCookiePairs(cookie);
    if (!pairs.length) throw new Error('No login cookie configured.');
    await context.addCookies(pairs.map(p => ({ ...p, domain, path: '/', secure: true })));
    const page = await context.newPage();
    await page.goto('https://glados.cloud/console/checkin', { waitUntil: 'domcontentloaded', timeout: 60000 });
    const deadline = Date.now() + 90000;
    // Read-only history check prevents daily duplicate clicks.
    const pointsReply = await context.request.get('https://glados.cloud/api/user/points', {timeout:30000});
    const points = await pointsReply.json().catch(() => null);
    if (points?.code === 0 && hasRecordToday(points.history || points.list) === true)
      return {code:1, message:'Today is confirmed in the Beijing-date points history.'};
    let clicked = false;
    let responseBody;
    // Observe only the response produced by the actual website's check-in action.
    page.on('response', async response => {
      const url = new URL(response.url());
      if (url.origin === 'https://glados.cloud' && url.pathname === '/api/user/checkin'
          && response.request().method() === 'POST') {
        try { responseBody = await response.json(); } catch {}
      }
    });
    while (Date.now() < deadline) {
      if (responseBody) {
        // A verification rejection is terminal for this attempt; never retry or evade it.
        if (responseBody.code === 0 || responseBody.code === 1) {
          const verification = await context.request.get('https://glados.cloud/api/user/points', {timeout:30000});
          const ledger = await verification.json().catch(() => null);
          if (ledger?.code !== 0 || hasRecordToday(ledger.history || ledger.list) !== true)
            throw new Error('Response received but today is not confirmed in the points history.');
        }
        return responseBody;
      }
      if (/\/(authenticate|login)(?:[/?#]|$)/.test(page.url()))
        throw new Error('Login expired: update this account in Configure.ps1.');
      const buttons = page.getByRole('button');
      const candidates = [];
      for (const button of await buttons.all()) {
        if (await button.isVisible() && await button.isEnabled())
          candidates.push({ button, text: (await button.innerText()).trim() });
      }
      const candidate = selectCheckinButton(candidates);
      if (!clicked && candidate) {
        clicked = true;
        await candidate.button.click();
      }
      // No CAPTCHA clicks, injected widgets, challenge proofs, or fingerprint overrides.
      // If interaction is required, the actual Edge window stays visible for the user.
      await page.waitForTimeout(750);
    }
    throw new Error('No confirmed check-in response within 90 seconds; login or human verification may be required.');
  } finally {
    await browser.close();
  }
}

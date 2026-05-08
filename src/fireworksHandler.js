require('dotenv').config();
const { randomDelay, humanType } = require('./browser');
const logger = require('./logger');

const FIREWORKS_SIGNUP_URL = 'https://app.fireworks.ai/signup';
const FIREWORKS_SETTINGS_URL = 'https://app.fireworks.ai/settings/users/api-keys';

async function registerFireworksAccount({ page, aliasEmail, firstName, lastName }) {
  const password = process.env.FIREWORKS_PASSWORD || 'ZOE.jerry2024';

  logger.info(`🔥 Fireworks AI Registrierung: ${aliasEmail}`);
  await page.goto(FIREWORKS_SIGNUP_URL, { waitUntil: 'networkidle2', timeout: 30000 });
  await randomDelay(2000, 4000);

  logger.info('📧 E-Mail eingeben...');
  await page.waitForSelector(
    'input[type="email"], input[name="email"], input[placeholder*="email" i]',
    { timeout: 10000 }
  );
  await humanType(
    page,
    'input[type="email"], input[name="email"], input[placeholder*="email" i]',
    aliasEmail
  );
  await randomDelay();

  const nextBtn1 = await page.$(
    'button:has-text("Next"), button:has-text("Weiter"), button[type="submit"]'
  );
  if (!nextBtn1) throw new Error('Next-Button nicht gefunden');
  await nextBtn1.click();
  await randomDelay(2000, 3000);

  logger.info('🔑 Passwort eingeben...');
  await page.waitForSelector('input[type="password"], input[name="password"]', { timeout: 8000 });
  await humanType(page, 'input[type="password"], input[name="password"]', password);
  await randomDelay();

  const createBtn = await page.$(
    'button:has-text("Create Account"), button:has-text("Account erstellen"), button:has-text("Sign Up"), button[type="submit"]'
  );
  if (!createBtn) throw new Error('Create-Account-Button nicht gefunden');
  await createBtn.click();
  await randomDelay(2000, 4000);
  logger.info('✅ Account-Erstellung abgeschickt');
}

async function confirmFireworksAccount({ page, confirmUrl, firstName, lastName }) {
  const password = process.env.FIREWORKS_PASSWORD || 'ZOE.jerry2024';

  logger.info('🔗 OTP-URL öffnen...');
  await page.goto(confirmUrl, { waitUntil: 'networkidle2', timeout: 30000 });
  await randomDelay(2000, 4000);

  const signInBtn = await page.$(
    'button:has-text("Sign In"), a:has-text("Sign In"), button:has-text("Anmelden")'
  );
  if (signInBtn) {
    await signInBtn.click();
    await randomDelay(1500, 3000);
    logger.info('✅ Sign In geklickt');
  }

  const emailLoginBtn = await page.$(
    'button:has-text("Email Login"), a:has-text("Email Login"), button:has-text("Continue with Email")'
  );
  if (emailLoginBtn) {
    await emailLoginBtn.click();
    await randomDelay(1500, 3000);
    logger.info('✅ Email Login geklickt');
  }

  // E-Mail + Passwort Login
  const emailField = await page.$('input[type="email"], input[name="email"]');
  if (emailField && await emailField.isIntersectingViewport().catch(() => false)) {
    await randomDelay();
  }

  const passField = await page.$('input[type="password"]');
  if (passField) {
    await humanType(page, 'input[type="password"]', password);
    await randomDelay();

    const nextBtn = await page.$('button:has-text("Next"), button[type="submit"]');
    if (nextBtn) {
      await nextBtn.click();
      await randomDelay(2000, 3000);
      logger.info('✅ Login-Daten eingegeben');
    }
  }

  // Vorname + Nachname + Häkchen
  const firstNameField = await page.$(
    'input[name="firstName"], input[placeholder*="First" i], input[placeholder*="Vorname" i]'
  );
  if (firstNameField) {
    await humanType(page, 'input[name="firstName"], input[placeholder*="First" i]', firstName);
    await randomDelay(500, 1000);

    const lastNameField = await page.$(
      'input[name="lastName"], input[placeholder*="Last" i], input[placeholder*="Nachname" i]'
    );
    if (lastNameField) {
      await humanType(page, 'input[name="lastName"], input[placeholder*="Last" i]', lastName);
    }
    await randomDelay();

    // Häkchen setzen
    const checkboxes = await page.$$('input[type="checkbox"]');
    for (const cb of checkboxes) {
      const isChecked = await page.evaluate((el) => el.checked, cb);
      if (!isChecked) await cb.click();
    }
    await randomDelay(500, 1000);

    const continueBtn = await page.$(
      'button:has-text("Continue"), button:has-text("Weiter"), button[type="submit"]'
    );
    if (continueBtn) {
      await continueBtn.click();
      await randomDelay(2000, 3000);
      logger.info('✅ Profil ausgefüllt');
    }
  }

  // Use-Case: Flexible capacity + Conversational AI
  try {
    const flexibleCb = await page.$(
      'input[value*="flexible" i], label:has-text("Flexible capacity") input, label:has-text("Flexible") input'
    );
    if (flexibleCb) {
      const isChecked = await page.evaluate((el) => el.checked, flexibleCb);
      if (!isChecked) await flexibleCb.click();
    }

    const conversationalCb = await page.$(
      'input[value*="conversational" i], label:has-text("Conversational AI") input, label:has-text("Conversational") input'
    );
    if (conversationalCb) {
      const isChecked = await page.evaluate((el) => el.checked, conversationalCb);
      if (!isChecked) await conversationalCb.click();
    }

    await randomDelay(500, 1000);

    const submitBtn = await page.$(
      'button:has-text("Submit"), button:has-text("$5"), button[type="submit"]'
    );
    if (submitBtn) {
      await submitBtn.click();
      await randomDelay(2000, 4000);
      logger.info('✅ Use-Case ausgewählt, $5 Credits beantragt');
    }
  } catch (err) {
    logger.warn(`⚠️ Use-Case Auswahl: ${err.message}`);
  }
}

async function createFireworksApiKey({ page }) {
  logger.info('🔑 Fireworks AI API Key erstellen...');

  await page.goto(FIREWORKS_SETTINGS_URL, { waitUntil: 'networkidle2', timeout: 15000 });
  await randomDelay(2000, 3000);

  const createKeyBtn = await page.$(
    'button:has-text("Create API Key"), button:has-text("New API Key"), button:has-text("Add Key"), button:has-text("Create")'
  );
  if (!createKeyBtn) throw new Error('Create-API-Key-Button nicht gefunden');
  await createKeyBtn.click();
  await randomDelay(1500, 3000);
  logger.info('✅ Create API Key geklickt');

  const keyNameInput = await page.$(
    'input[name="name"], input[placeholder*="name" i], input[placeholder*="Key" i]'
  );
  if (keyNameInput) {
    await humanType(page, 'input[name="name"], input[placeholder*="name" i]', 'API');
    await randomDelay();
  }

  const generateBtn = await page.$(
    'button:has-text("Generate"), button:has-text("Create"), button[type="submit"]'
  );
  if (!generateBtn) throw new Error('Generate-Button nicht gefunden');
  await generateBtn.click();
  await randomDelay(2000, 4000);

  let apiKey = null;

  const keySelectors = [
    'input[readonly]',
    'code',
    'pre',
    '[data-testid*="api-key"]',
    '.api-key',
    'input[value*="fw_"]',
    'span:has-text("fw_")',
  ];

  for (const selector of keySelectors) {
    try {
      const el = await page.$(selector);
      if (el) {
        const val = await page.evaluate((node) => node.value || node.textContent, el);
        if (val && val.trim().length > 10) {
          apiKey = val.trim();
          break;
        }
      }
    } catch {}
  }

  if (!apiKey) {
    try {
      const copyBtn = await page.$('button:has-text("Copy"), button[title*="copy" i]');
      if (copyBtn) {
        await copyBtn.click();
        apiKey = await page.evaluate(() => navigator.clipboard.readText());
      }
    } catch {}
  }

  if (!apiKey) {
    throw new Error('API Key konnte nicht ausgelesen werden');
  }

  logger.info(`✅ API Key generiert: ${apiKey.substring(0, 12)}...`);
  return apiKey;
}

module.exports = {
  registerFireworksAccount,
  confirmFireworksAccount,
  createFireworksApiKey,
};
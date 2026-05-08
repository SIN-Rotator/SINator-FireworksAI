require('dotenv').config();
const { createStealthBrowser, randomDelay, humanType } = require('./browser');
const logger = require('./logger');

const GMX_LOGIN_URL = 'https://www.gmx.net/';
const GMX_MAIL_SETTINGS_URL = 'https://navigator.gmx.net/mail_settings';
const GMX_MAIL_URL = 'https://navigator.gmx.net/mail';
const GMX_ALIASES_URL = 'https://navigator.gmx.net/mail_settings/email_addresses';

async function loginToGmx() {
  const { browser, context, page, cdp } = await createStealthBrowser();

  try {
    logger.info('🔐 GMX Login gestartet...');
    await page.goto(GMX_LOGIN_URL, { waitUntil: 'networkidle2', timeout: 30000 });
    await randomDelay();

    const loginBtn = await page.$('a[href*="login"], button:has-text("Login"), a:has-text("Login")');
    if (loginBtn) {
      await loginBtn.click();
      await randomDelay();
    }

    await page.waitForSelector('input[name="username"], input[type="email"], #username', { timeout: 10000 });
    await humanType(page, 'input[name="username"], input[type="email"], #username', process.env.GMX_EMAIL);
    await randomDelay(500, 1500);

    await humanType(page, 'input[name="password"], input[type="password"], #password', process.env.GMX_PASSWORD);
    await randomDelay(500, 1500);

    await page.keyboard.press('Enter');
    await page.waitForNavigation({ waitUntil: 'networkidle2', timeout: 15000 });
    await randomDelay();

    logger.info('✅ GMX Login erfolgreich');
    return { browser, context, page, cdp };
  } catch (err) {
    logger.error(`❌ GMX Login fehlgeschlagen: ${err.message}`);
    await browser.close();
    throw err;
  }
}

async function manageGmxAlias({ page, aliasName }) {
  logger.info('📧 GMX Alias-Verwaltung gestartet...');

  await page.goto(GMX_MAIL_SETTINGS_URL, { waitUntil: 'networkidle2', timeout: 15000 });
  await randomDelay();

  const emailAddressesLink = await page.$(
    'a:has-text("E-Mail-Adressen"), li:has-text("E-Mail-Adressen"), [href*="email_addresses"], [href*="mail_addresses"]'
  );
  if (emailAddressesLink) {
    await emailAddressesLink.click();
    await randomDelay();
    logger.info('📋 E-Mail-Adressen Seite geöffnet');
  }

  try {
    const deleteButtons = await page.$$(
      'button:has-text("Löschen"), a:has-text("Löschen"), [title="Löschen"], .delete-alias, button[data-action="delete"]'
    );
    if (deleteButtons.length > 0) {
      await deleteButtons[deleteButtons.length - 1].click();
      await randomDelay(1000, 2000);

      const confirmBtn = await page.$(
        'button:has-text("Ja"), button:has-text("Bestätigen"), button:has-text("OK"), button:has-text("Löschen")'
      );
      if (confirmBtn) {
        await confirmBtn.click();
        await randomDelay();
      }
      logger.info('🗑️ Alter Alias gelöscht');
    } else {
      logger.info('ℹ️ Kein Alias zum Löschen gefunden');
    }
  } catch (err) {
    logger.warn(`⚠️ Alias löschen: ${err.message}`);
  }

  const newAliasEmail = `${aliasName}@gmx.de`;
  logger.info(`➕ Erstelle neuen Alias: ${newAliasEmail}`);

  try {
    const addBtn = await page.$(
      'button:has-text("Hinzufügen"), button:has-text("Neu"), a:has-text("Alias hinzufügen"), button:has-text("Alias")'
    );
    if (!addBtn) throw new Error('Alias-Hinzufügen-Button nicht gefunden');
    await addBtn.click();
    await randomDelay();

    await page.waitForSelector(
      'input[name="alias"], input[placeholder*="alias"], input[placeholder*="Alias"], input[type="text"]',
      { timeout: 5000 }
    );
    await humanType(
      page,
      'input[name="alias"], input[placeholder*="alias"], input[placeholder*="Alias"], input[type="text"]',
      aliasName
    );
    await randomDelay();

    const saveBtn = await page.$(
      'button:has-text("Speichern"), button:has-text("Erstellen"), button[type="submit"]'
    );
    if (!saveBtn) throw new Error('Speichern-Button nicht gefunden');
    await saveBtn.click();
    await randomDelay(2000, 4000);

    logger.info(`✅ Alias erstellt: ${newAliasEmail}`);
  } catch (err) {
    logger.error(`❌ Alias erstellen fehlgeschlagen: ${err.message}`);
    throw err;
  }

  return newAliasEmail;
}

async function readOtpFromGmx({ page, aliasEmail }) {
  logger.info('📬 Warte auf OTP-E-Mail von Fireworks AI...');

  await page.goto(GMX_MAIL_URL, { waitUntil: 'networkidle2', timeout: 15000 });
  await randomDelay(3000, 6000);

  const maxRetries = 12;
  let confirmUrl = null;

  for (let i = 0; i < maxRetries; i++) {
    logger.info(`🔄 Versuch ${i + 1}/${maxRetries} - Suche OTP-E-Mail...`);

    await page.reload({ waitUntil: 'networkidle2', timeout: 15000 });
    await randomDelay(2000, 4000);

    const emailRow = await page.$('tr:has-text("Fireworks"), div:has-text("Fireworks"), li:has-text("Fireworks")');
    if (emailRow) {
      await emailRow.click();
      await randomDelay(2000, 3000);

      const content = await page.content();
      const urlMatch = content.match(
        /https:\/\/app\.fireworks\.ai\/[^\s"'<>]+(?:confirm|verify|token)[^\s"'<>]*/i
      );

      if (urlMatch) {
        confirmUrl = urlMatch[0];
        logger.info(`✅ OTP-URL gefunden: ${confirmUrl.substring(0, 50)}...`);
        break;
      }

      const confirmLink = await page.$('a[href*="fireworks.ai"]');
      if (confirmLink) {
        confirmUrl = await page.evaluate((el) => el.href, confirmLink);
        logger.info('✅ OTP-Link gefunden');
        break;
      }
    }

    await randomDelay(5000, 8000);
  }

  if (!confirmUrl) {
    throw new Error('OTP-E-Mail nicht gefunden nach ' + maxRetries + ' Versuchen');
  }

  return confirmUrl;
}

module.exports = { loginToGmx, manageGmxAlias, readOtpFromGmx };
#!/usr/bin/env node
/**
 * GMX Alias Test — CHROME SUBPROCESS + CDP CONNECT
 * =================================================
 * Chrome wird DIREKT via subprocess gestartet (kein puppeteer.launch).
 * puppeteer.connect() verbindet via CDP WebSocket zum laufenden Chrome.
 *
 * Warum? GMX blockiert puppeteer.launch() mit 403 Forbidden.
 * Direkter Chrome-Start umgeht die Automation-Erkennung.
 * Stealth-suite macht das genau so (subprocess.Popen → CDP connect).
 */
require('dotenv').config();
const { spawn } = require('child_process');
const puppeteer = require('puppeteer-extra');
const StealthPlugin = require('puppeteer-extra-plugin-stealth');
const http = require('http');
const logger = require('./src/logger');
const { randomDelay, clickByText } = require('./src/browser');
const { generateAliasName } = require('./src/nameGenerator');

puppeteer.use(StealthPlugin());

const CDP_PORT = 9222;
const CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';

async function getWsUrl(port) {
  return new Promise((resolve, reject) => {
    http.get(`http://127.0.0.1:${port}/json/version`, res => {
      let d = ''; res.on('data', c => d += c);
      res.on('end', () => resolve(JSON.parse(d).webSocketDebuggerUrl));
    }).on('error', reject);
  });
}

async function launchChromeSubprocess() {
  const tmpDir = `/tmp/sinator-fresh-${Date.now()}`;
  require('fs').mkdirSync(tmpDir, { recursive: true });
  return new Promise((resolve, reject) => {
    const child = spawn(CHROME, [
      `--user-data-dir=${tmpDir}`,
      `--remote-debugging-port=${CDP_PORT}`,
      '--remote-allow-origins=*',
      '--no-first-run',
      '--no-default-browser-check',
      '--disable-blink-features=AutomationControlled',
      '--disable-infobars',
      '--window-size=1366,768',
      '--lang=de-DE',
      'about:blank',
    ], { stdio: 'ignore', detached: false });

    child.on('error', reject);
    // Warte auf CDP
    setTimeout(async () => {
      try {
        const ws = await getWsUrl(CDP_PORT);
        logger.info(`Chrome subprocess gestartet, CDP: ${ws.substring(0,60)}...`);
        resolve(child);
      } catch (e) {
        reject(e);
      }
    }, 3000);
  });
}

(async () => {
  const aliasName = generateAliasName();
  const aliasEmail = `${aliasName}@gmx.de`;
  const gmxUser = process.env.GMX_EMAIL;
  const gmxPass = process.env.GMX_PASSWORD;

  logger.info(`👤 Alias: ${aliasEmail}`);
  logger.info(`🔑 GMX: ${gmxUser}`);

  await launchChromeSubprocess();
  const wsUrl = await getWsUrl(CDP_PORT);
  const browser = await puppeteer.connect({ browserWSEndpoint: wsUrl });
  const pages = await browser.pages();
  const page = pages[0] || await browser.newPage();

  try {
    // Stealth JS injecten
    await page.evaluateOnNewDocument(() => {
      Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
      Object.defineProperty(navigator, 'plugins', { get: () => [1,2,3,4,5] });
      window.chrome = { runtime: {} };
    });

    // 1. GMX öffnen
    logger.info('🌐 Öffne www.gmx.net...');
    await page.goto('https://www.gmx.net/', { waitUntil: 'networkidle2', timeout: 15000 });
    await randomDelay(2000, 3000);
    logger.info(`📍 URL: ${page.url()}`);

    // 2. Login-Button klicken
    logger.info('🔍 Login-Button suchen...');
    await clickByText(page, 'Login', 'a');
    await randomDelay(2000, 3000);

    // Wenn wir auf consent sind: akzeptieren
    if (page.url().includes('consent')) {
      logger.info('🍪 Consent akzeptieren...');
      await clickByText(page, 'Alle akzeptieren', 'button');
      await randomDelay(2000, 3000);
      await page.waitForNavigation({ timeout: 10000 }).catch(() => {});
    }

    // Prüfen ob Login-Form da ist
    logger.info(`📍 Nach Login-Click: ${page.url()}`);
    const hasEmail = await page.$('input[name="username"]');
    if (!hasEmail) {
      // Vielleicht auf redirect zu login-Seite
      if (page.url().includes('login')) {
        // OK, auf login-Seite
      } else {
        // Gehe direkt zu login
        await page.goto('https://www.gmx.net/', { waitUntil: 'networkidle2', timeout: 10000 });
        await randomDelay();
        await clickByText(page, 'Login', 'a');
        await randomDelay(2000, 3000);
      }
    }

    logger.info(`📍 Login-Seite: ${page.url()}`);
    const bodyText = await page.evaluate(() => document.body ? document.body.innerText.substring(0, 300) : '');
    logger.info(`📄 ${bodyText}`);

    // 3. E-Mail eingeben
    const emailInput = await page.$('input[name="username"]');
    if (emailInput) {
      logger.info('📧 E-Mail eingeben...');
      await emailInput.click();
      for (const c of gmxUser) {
        await page.keyboard.type(c, { delay: Math.random() * 60 + 30 });
      }
      await randomDelay(800, 1200);
    }

    // 4. Passwort eingeben
    const passInput = await page.$('input[type="password"]');
    if (passInput) {
      logger.info('🔐 Passwort eingeben...');
      await passInput.click();
      for (const c of gmxPass) {
        await page.keyboard.type(c, { delay: Math.random() * 60 + 30 });
      }
      await randomDelay(500, 1000);
    }

    // 5. Login abschicken
    logger.info('⏎ Enter...');
    await page.keyboard.press('Enter');
    await randomDelay(3000, 5000);
    await page.waitForNavigation({ timeout: 15000 }).catch(() => {});
    logger.info(`📍 Nach Login: ${page.url()}`);

    // Consent nach Login
    if (page.url().includes('consent')) {
      await clickByText(page, 'Alle akzeptieren', 'button');
      await randomDelay(2000, 3000);
      await page.waitForNavigation({ timeout: 10000 }).catch(() => {});
    }

    logger.info(`📍 Final: ${page.url()}`);

    if (page.url().includes('navigator.gmx.net')) {
      logger.info('✅✅✅ GMX LOGIN ERFOLGREICH!');
    } else if (page.url().includes('403') || page.url().includes('forbidden')) {
      logger.error('❌ GMX blockiert (403) — Bot-Detection');
      await browser.disconnect();
      return;
    } else {
      logger.warn('⚠️  Unerwartete URL nach Login');
    }

    // 6. E-Mail-Adressen Seite
    logger.info('⚙️  E-Mail-Adressen...');
    await page.goto('https://navigator.gmx.net/mail_settings/email_addresses', {
      waitUntil: 'networkidle2', timeout: 15000,
    });
    await randomDelay(2000, 3000);
    logger.info(`📍 ${page.url()}`);

    // 7. Alias löschen
    logger.info('🗑️  Alias löschen...');
    await clickByText(page, 'Löschen', 'button');
    await randomDelay(1500, 2000);
    await clickByText(page, 'Ja', 'button');
    await randomDelay(2000, 3000);

    // 8. Neuen Alias
    logger.info(`➕ ${aliasEmail}`);
    await clickByText(page, 'Hinzufügen', 'button');
    await randomDelay(2000, 3000);

    const inputs = await page.$$('input[type="text"]');
    if (inputs.length > 0) {
      await inputs[0].click();
      for (const c of aliasName) {
        await page.keyboard.type(c, { delay: Math.random() * 50 + 25 });
      }
      logger.info(`✅ "${aliasName}" getippt`);
    }
    await randomDelay(500, 1000);

    await clickByText(page, 'Speichern', 'button');
    await randomDelay(3000, 5000);

    const result = await page.evaluate(() => document.body.innerText);
    if (result.includes(aliasName)) {
      logger.info(`✅✅✅ ALIAS ERFOLGREICH: ${aliasEmail}`);
    }
    logger.info('📄 ' + result.substring(0, 400));

    logger.info('⏸️  10s...');
    await new Promise(r => setTimeout(r, 10000));
    await browser.disconnect();

  } catch (err) {
    logger.error(`💥 ${err.message}`);
    try { await browser.disconnect(); } catch {}
  }
})();
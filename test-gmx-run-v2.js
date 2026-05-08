#!/usr/bin/env node
/**
 * SINator GMX Runner — Subprozess + CDP + Frischer Login
 * =======================================================
 * 1. Chrome via spawn starten (mit --user-data-dir=/tmp/sinator-xxx)
 * 2. puppeteer.connect via CDP WebSocket
 * 3. www.gmx.net → Login → Credentials eingeben → Einloggen
 * 4. E-Mail-Adressen Seite → Alias löschen → Neuen erstellen
 */
require('dotenv').config();
const { spawn } = require('child_process');
const fs = require('fs');
const puppeteer = require('puppeteer-extra');
const StealthPlugin = require('puppeteer-extra-plugin-stealth');
const http = require('http');
const logger = require('./src/logger');
const { generateAliasName } = require('./src/nameGenerator');

puppeteer.use(StealthPlugin());

const CDP_PORT = 9222;
const CHROME = process.env.CHROME_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const GMX_USER = process.env.GMX_EMAIL;
const GMX_PASS = process.env.GMX_PASSWORD;

async function getWs(port) {
  return new Promise((resolve, reject) => {
    const req = http.get(`http://127.0.0.1:${port}/json/version`, res => {
      let body = '';
      res.on('data', c => body += c);
      res.on('end', () => {
        try { resolve(JSON.parse(body).webSocketDebuggerUrl); }
        catch(e) { reject(e); }
      });
    });
    req.on('error', reject);
    req.setTimeout(3000, () => { req.destroy(); reject(new Error('timeout')); });
  });
}

async function wait(ms) { return new Promise(r => setTimeout(r, ms)); }

function delay(min, max) {
  return Math.floor(Math.random() * (max - min + 1)) + min;
}

(async () => {
  const aliasName = generateAliasName();
  const aliasEmail = `${aliasName}@gmx.de`;
  logger.info(`👤 Ziel: ${aliasEmail}`);

  // ── 1. CHROME SUBPROZESS ──────────────────────────────────────────
  const tmpDir = `/tmp/sinator-${Date.now()}`;
  fs.mkdirSync(tmpDir, { recursive: true });

  logger.info('🚀 Starte Chrome subprocess...');
  const chrome = spawn(CHROME, [
    `--user-data-dir=${tmpDir}`,
    `--remote-debugging-port=${CDP_PORT}`,
    '--remote-allow-origins=*',
    '--no-first-run', '--no-default-browser-check',
    '--disable-blink-features=AutomationControlled',
    '--disable-infobars', '--disable-features=OptimizationHints,Translate,MediaRouter',
    '--window-size=1280,800', '--lang=de-DE',
    'about:blank',
  ], { stdio: 'ignore' });

  // Warte auf CDP-Bereitschaft
  let wsUrl;
  for (let i = 0; i < 10; i++) {
    try { wsUrl = await getWs(CDP_PORT); break; } catch { await wait(1000); }
  }
  if (!wsUrl) { logger.error('❌ CDP nicht erreichbar'); process.exit(1); }
  logger.info(`✅ CDP: ${wsUrl.substring(0,55)}...`);

  const browser = await puppeteer.connect({ browserWSEndpoint: wsUrl });
  const pages = await browser.pages();
  const page = pages[0];

  // ── 2. GMX LANDING PAGE ───────────────────────────────────────────
  logger.info('🌐 Lade www.gmx.net...');
  await page.goto('https://www.gmx.net/', { waitUntil: 'domcontentloaded', timeout: 15000 });
  await wait(3000);

  // Consent check
  if (page.url().includes('consent')) {
    logger.info('🍪 Consent Page erkannt...');
    const clicked = await page.evaluate(() => {
      const btns = document.querySelectorAll('button');
      for (const b of btns) {
        if (b.textContent.includes('Alle akzeptieren') || b.textContent.includes('Akzeptieren')) {
          b.click(); return true;
        }
      }
      return false;
    });
    await wait(3000);
    try { await page.waitForNavigation({ timeout: 8000 }); } catch {}
    logger.info(`📍 Nach Consent: ${page.url()}`);
  }

  // Login-Button auf Landing Page
  logger.info('🔍 Suche Login-Button...');
  const loginClicked = await page.evaluate(() => {
    const all = document.querySelectorAll('a, button, span');
    for (const el of all) {
      const t = el.textContent || '';
      if (t.includes('Login') || t.includes('Anmelden') || t.includes('Einloggen')) {
        el.click(); return el.tagName;
      }
    }
    return false;
  });

  logger.info(`Login-Button: ${loginClicked || 'NICHT gefunden'}`);
  await wait(3000);

  // Wurden wir zur Login-Seite weitergeleitet?
  const postClickUrl = page.url();
  logger.info(`📍 Nach Login-Click: ${postClickUrl}`);

  if (!postClickUrl.includes('login') && !postClickUrl.includes('account')) {
    // Fallback: direkt login.gmx.net
    logger.info('⚠️  Umleitung hat nicht funktioniert. Direkt zu login.gmx.net...');
    await page.goto('https://login.gmx.net/', { waitUntil: 'domcontentloaded', timeout: 15000 });
    await wait(4000);
    logger.info(`📍 Login-Seite: ${page.url()}`);

    // 403 Check
    const bodyText = await page.evaluate(() => document.body.innerText);
    if (bodyText.includes('403') || bodyText.includes('Forbidden')) {
      logger.error('❌ GMX blockiert (403). Bot-Detection aktiv.');
      await browser.disconnect();
      chrome.kill();
      process.exit(1);
    }
  }

  // ── 3. CREDENTIALS EINGEBEN ───────────────────────────────────────
  // Finde das E-Mail-Feld
  logger.info('📧 Suche E-Mail-Feld...');
  const emailField = await page.evaluateHandle(() => {
    return document.querySelector('input[name="username"]')
      || document.querySelector('input[type="email"]')
      || document.querySelector('#email')
      || document.querySelector('input[name="email"]');
  });

  if (emailField.asElement()) {
    await emailField.asElement().then(e => e.click());
    await wait(500);
    for (const c of GMX_USER) {
      await page.keyboard.type(c, { delay: delay(30, 80) });
    }
    logger.info('✅ E-Mail eingegeben');
  } else {
    logger.error('❌ E-Mail-Feld nicht gefunden');
    const html = await page.evaluate(() => document.body.innerHTML.substring(0, 1000));
    logger.info('HTML: ' + html);
    await browser.disconnect();
    chrome.kill();
    process.exit(1);
  }
  await wait(delay(500, 1000));

  // Finde das Passwort-Feld
  logger.info('🔐 Suche Passwort-Feld...');
  const passField = await page.evaluateHandle(() => {
    return document.querySelector('input[type="password"]')
      || document.querySelector('input[name="password"]')
      || document.querySelector('#password');
  });

  if (passField.asElement()) {
    await passField.asElement().then(e => e.click());
    await wait(300);
    for (const c of GMX_PASS) {
      await page.keyboard.type(c, { delay: delay(30, 70) });
    }
    logger.info('✅ Passwort eingegeben');
  } else {
    logger.error('❌ Passwort-Feld nicht gefunden');
  }
  await wait(500);

  // Login abschicken
  logger.info('⏎ Login abschicken...');
  await page.keyboard.press('Enter');
  await wait(5000);
  try { await page.waitForNavigation({ timeout: 15000 }); } catch {}

  logger.info(`📍 Nach Login: ${page.url()}`);

  // Post-Login Consent?
  if (page.url().includes('consent')) {
    logger.info('🍪 Post-Login Consent...');
    await page.evaluate(() => {
      document.querySelectorAll('button').forEach(b => {
        if (b.textContent.includes('Alle akzeptieren')) b.click();
      });
    });
    await wait(3000);
    try { await page.waitForNavigation({ timeout: 8000 }); } catch {}
    logger.info(`📍 Nach Post-Consent: ${page.url()}`);
  }

  // Ist Login erfolgreich?
  if (page.url().includes('navigator.gmx.net') || page.url().includes('bap.navigator')) {
    logger.info('✅✅✅ GMX LOGIN ERFOLGREICH!');
  } else {
    logger.warn(`⚠️  Unerwartete URL: ${page.url()}`);
  }

  // ── 4. ALIAS-PROZESS ──────────────────────────────────────────────
  logger.info('⚙️  Öffne E-Mail-Adressen...');
  await page.goto('https://navigator.gmx.net/mail_settings/email_addresses', {
    waitUntil: 'domcontentloaded', timeout: 15000,
  });
  await wait(4000);
  logger.info(`📍 ${page.url()}`);

  // Alias löschen
  logger.info('🗑️  Alias löschen...');
  await page.evaluate(() => {
    document.querySelectorAll('button, a').forEach(el => {
      if (el.textContent.includes('Löschen')) el.click();
    });
  });
  await wait(2000);
  await page.evaluate(() => {
    document.querySelectorAll('button').forEach(el => {
      if (el.textContent.includes('Ja') || el.textContent.includes('Bestätigen')) el.click();
    });
  });
  await wait(3000);

  // Neuen Alias
  logger.info(`➕ ${aliasEmail}`);
  await page.evaluate((name) => {
    document.querySelectorAll('button, a').forEach(el => {
      if (el.textContent.includes('Hinzufügen') || el.textContent.includes('Neu')) el.click();
    });
  }, aliasName);
  await wait(3000);

  logger.info('✏️  Alias eintippen...');
  const textInputs = await page.$$('input[type="text"]');
  if (textInputs.length > 0) {
    await textInputs[0].click();
    await wait(400);
    for (const c of aliasName) {
      await page.keyboard.type(c, { delay: delay(25, 60) });
    }
    logger.info('✅ Alias-Name eingetippt');
  }
  await wait(500);

  // Speichern
  await page.evaluate(() => {
    document.querySelectorAll('button').forEach(el => {
      if (el.textContent.includes('Speichern') || el.textContent.includes('Erstellen')) el.click();
    });
  });
  await wait(5000);

  // Ergebnis
  const result = await page.evaluate(() => document.body.innerText.substring(0, 500));
  logger.info(`📄 Ergebnis: ${result.substring(0, 300)}`);
  logger.info(result.includes(aliasName) ? `✅✅✅ ALIAS ERFOLGREICH: ${aliasEmail}` : `⚠️  Kein Match für "${aliasName}"`);

  logger.info('⏸️  10s anzeigen...');
  await wait(10000);
  await browser.disconnect();
  chrome.kill();
  logger.info('🏁 Fertig');
})();
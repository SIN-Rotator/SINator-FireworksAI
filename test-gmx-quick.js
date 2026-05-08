#!/usr/bin/env node
/**
 * GMX Alias Test — QUICK Version
 * ===============================
 * Verbindet zum bereits laufenden Chrome auf Port 9222 via CDP.
 * Chrome wurde manuell gestartet mit kopiertem Profile 73.
 */

require('dotenv').config();
const puppeteer = require('puppeteer-extra');
const StealthPlugin = require('puppeteer-extra-plugin-stealth');
const { randomDelay, humanType } = require('./src/browser');
const { generateAliasName } = require('./src/nameGenerator');
const logger = require('./src/logger');
const http = require('http');

puppeteer.use(StealthPlugin());

async function getWsEndpoint(port = 9222) {
  return new Promise((resolve, reject) => {
    http.get(`http://127.0.0.1:${port}/json/version`, (res) => {
      let data = '';
      res.on('data', c => data += c);
      res.on('end', () => {
        const json = JSON.parse(data);
        resolve(json.webSocketDebuggerUrl);
      });
    }).on('error', reject);
  });
}

async function findByText(page, text, tag = '*') {
  const xpath = `//${tag}[contains(text(), '${text}')]`;
  const elements = await page.$x(xpath);
  return elements[0] || null;
}

async function clickByText(page, text, tag = '*') {
  const el = await findByText(page, text, tag);
  if (el) { await el.click(); return true; }
  return false;
}

async function run() {
  const aliasName = generateAliasName();
  const aliasEmail = `${aliasName}@gmx.de`;
  logger.info(`👤 Geplanter Alias: ${aliasEmail}`);

  const wsUrl = await getWsEndpoint();
  logger.info(`🔗 CDP: ${wsUrl.substring(0,60)}...`);

  const browser = await puppeteer.connect({ browserWSEndpoint: wsUrl });
  const pages = await browser.pages();
  const page = pages[0] || await browser.newPage();

  try {
    // 1. GMX öffnen
    logger.info('📬 Öffne navigator.gmx.net...');
    await page.goto('https://navigator.gmx.net/mail', { waitUntil: 'networkidle2', timeout: 30000 });
    await randomDelay(2000, 3000);
    logger.info(`📍 URL: ${page.url()}`);

    // Consent-Management handlen
    if (page.url().includes('consent')) {
      logger.info('🍪 Consent erkannt — akzeptiere...');
      await clickByText(page, 'Alle akzeptieren', 'button');
      await randomDelay(1500, 2500);
      await page.waitForNavigation({ timeout: 10000 }).catch(() => {});
      await randomDelay();
    }

    logger.info(`📍 Nach Consent: ${page.url()}`);
    if (page.url().includes('navigator.gmx.net/mail')) {
      logger.info('✅ EINGELOGGT im Posteingang!');
    } else if (page.url().includes('login')) {
      logger.error('❌ NICHT eingeloggt!');
      await browser.disconnect();
      return;
    }

    // 2. E-Mail-Einstellungen → Alias-Seite
    logger.info('⚙️  Öffne E-Mail-Adressen...');
    await page.goto('https://navigator.gmx.net/mail_settings/email_addresses', {
      waitUntil: 'networkidle2', timeout: 15000,
    });
    await randomDelay(2000, 3000);
    logger.info(`📍 Alias-Seite: ${page.url()}`);

    // Aliase zählen
    const pageText = await page.evaluate(() => document.body.innerText);
    const aliases = pageText.match(/[a-z0-9._-]+@gmx\.de/gi) || [];
    logger.info(`📋 ${aliases.length} @gmx.de Adressen: ${[...new Set(aliases)].join(', ') || 'keine'}`);

    // 3. Alias löschen
    logger.info('🗑️  Suche Lösch-Button...');
    for (const txt of ['Löschen', 'Entfernen']) {
      if (await clickByText(page, txt, 'button') || await clickByText(page, txt, 'a')) {
        logger.info(`🗑️  "${txt}" geklickt`);
        await randomDelay(1500, 2500);
        await clickByText(page, 'Ja', 'button') || await clickByText(page, 'Bestätigen', 'button');
        await randomDelay(2000, 3000);
        break;
      }
    }

    // 4. Neuen Alias erstellen
    logger.info(`➕ Neuer Alias: ${aliasEmail}`);
    let addDone = false;
    for (const txt of ['Hinzufügen', 'Neu', 'Alias', 'hinzufügen']) {
      if (await clickByText(page, txt, 'button') || await clickByText(page, txt, 'a')) {
        logger.info(`➕ "${txt}" Button/Link geklickt`);
        addDone = true;
        break;
      }
    }

    if (!addDone) {
      logger.error('❌ Kein Hinzufügen-Button');
      logger.info('Seite Text (1000): ' + pageText.substring(0, 1000));
      await browser.disconnect();
      return;
    }

    await randomDelay(2000, 3000);

    // Input finden + Alias eintragen
    const inputs = await page.$$('input[type="text"]');
    if (inputs.length > 0) {
      await inputs[0].click();
      await inputs[0].type(aliasName, { delay: Math.random() * 80 + 40 });
      logger.info(`✅ "${aliasName}" in Input getippt`);
    } else {
      logger.error('❌ Kein Input-Feld');
      const html = await page.evaluate(() => document.body.innerHTML.substring(0, 2000));
      logger.info('HTML: ' + html);
      await browser.disconnect();
      return;
    }

    await randomDelay();

    // Speichern
    let saved = false;
    for (const txt of ['Speichern', 'Erstellen', 'Anlegen', 'OK', 'Bestätigen']) {
      if (await clickByText(page, txt, 'button')) {
        logger.info(`💾 "${txt}" geklickt`);
        saved = true;
        break;
      }
    }
    if (!saved) { await page.keyboard.press('Enter'); }

    await randomDelay(3000, 5000);

    // Ergebnis
    const resultText = await page.evaluate(() => document.body.innerText);
    if (resultText.includes(aliasName)) {
      logger.info(`✅ ALIAS ERFOLGREICH: ${aliasEmail}`);
    } else {
      logger.warn(`⚠️  Alias nicht im Ergebnis gefunden`);
    }
    logger.info('📄 Ergebnis (500): ' + resultText.substring(0, 500));

    logger.info('⏸️  10s zum Anschauen...');
    await new Promise(r => setTimeout(r, 10000));
    await browser.disconnect();

  } catch (err) {
    logger.error(`💥 ${err.message}`);
    try { await browser.disconnect(); } catch {}
  }
}

run();
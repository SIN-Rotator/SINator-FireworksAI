#!/usr/bin/env node
/**
 * GMX Alias Test — FRISCHER LOGIN
 * ================================
 * Kein Profil kopieren. Kein bestehendes Profil.
 * Chrome startet frisch → GMX Login mit Credentials → Alias erstellen.
 *
 * Workflow:
 *   1. Chrome starten (frisch, stealth-flags, CDP)
 *   2. www.gmx.net → Login-Button → E-Mail + Passwort
 *   3. Consent akzeptieren falls nötig
 *   4. navigator.gmx.net → Einstellungen → E-Mail-Adressen
 *   5. Alias löschen (falls vorhanden)
 *   6. Neuen Alias-Namen generieren + erstellen
 */
require('dotenv').config();
const { createStealthBrowser, randomDelay, humanType, clickByText } = require('./src/browser');
const { generateAliasName } = require('./src/nameGenerator');
const logger = require('./src/logger');

(async () => {
  const aliasName = generateAliasName();
  const aliasEmail = `${aliasName}@gmx.de`;
  const gmxUser = process.env.GMX_EMAIL;
  const gmxPass = process.env.GMX_PASSWORD;

  logger.info(`👤 Alias: ${aliasEmail}`);
  logger.info(`🔑 GMX Login: ${gmxUser}`);

  // ── 1. Chrome starten ────────────────────────────────────────────
  const { browser, page } = await createStealthBrowser();

  try {
    // ── 2. GMX Login ───────────────────────────────────────────────
    logger.info('🌐 Öffne gmx.net...');
    await page.goto('https://www.gmx.net/', { waitUntil: 'networkidle2', timeout: 30000 });
    await randomDelay(2000, 3000);

    // Login-Button suchen (gmx.net Landing Page)
    logger.info('🔍 Suche Login-Button...');
    let loginClicked = await clickByText(page, 'Login', 'a')
      || await clickByText(page, 'Anmelden', 'a')
      || await clickByText(page, 'Einloggen', 'a');

    if (!loginClicked) {
      // Fallback: direkt zur Login-Seite
      logger.info('⚠️  Kein Login-Button, gehe direkt zu login.gmx.net...');
      await page.goto('https://login.gmx.net/', { waitUntil: 'networkidle2', timeout: 15000 });
    }
    await randomDelay(2000, 3000);

    // E-Mail-Feld finden und ausfüllen
    logger.info('📧 E-Mail eingeben...');
    const emailSel = 'input[name="username"], input[type="email"], #email, input[name="email"]';
    await page.waitForSelector(emailSel, { timeout: 10000 });
    await humanType(page, emailSel, gmxUser);
    await randomDelay(800, 1500);

    // Passwort-Feld finden und ausfüllen
    logger.info('🔐 Passwort eingeben...');
    const passSel = 'input[name="password"], input[type="password"], #password';
    await page.waitForSelector(passSel, { timeout: 5000 });
    await humanType(page, passSel, gmxPass);
    await randomDelay(500, 1000);

    // Login abschicken (Enter)
    logger.info('⏎ Login abschicken...');
    await page.keyboard.press('Enter');
    await randomDelay(3000, 5000);
    // Warte auf Navigation nach Login
    await page.waitForNavigation({ waitUntil: 'networkidle2', timeout: 20000 }).catch(() => {});

    // ── 3. Consent-Management ──────────────────────────────────────
    const url = page.url();
    logger.info(`📍 Nach Login: ${url}`);

    if (url.includes('consent')) {
      logger.info('🍪 Consent erkannt — akzeptiere...');
      await clickByText(page, 'Alle akzeptieren', 'button')
        || await clickByText(page, 'Akzeptieren', 'button')
        || await clickByText(page, 'Zustimmen', 'button');

      await randomDelay(2000, 3000);
      await page.waitForNavigation({ timeout: 15000 }).catch(() => {});
      logger.info(`📍 Nach Consent: ${page.url()}`);
    }

    if (page.url().includes('navigator.gmx.net')) {
      logger.info('✅ GMX Login erfolgreich!');
    } else if (page.url().includes('login')) {
      logger.error('❌ Login fehlgeschlagen — falsche Credentials?');
      await browser.close();
      return;
    }

    // ── 4. E-Mail-Adressen (Aliase) öffnen ─────────────────────────
    logger.info('⚙️  Öffne E-Mail-Adressen...');
    await page.goto('https://navigator.gmx.net/mail_settings/email_addresses', {
      waitUntil: 'networkidle2', timeout: 15000,
    });
    await randomDelay(2000, 3000);
    logger.info(`📍 Alias-Seite: ${page.url()}`);

    // ── 5. Alias löschen ───────────────────────────────────────────
    logger.info('🗑️  Lösung vorhandene Aliase...');
    for (const txt of ['Löschen', 'Entfernen']) {
      const clicked = await clickByText(page, txt, 'button')
        || await clickByText(page, txt, 'a');
      if (clicked) {
        logger.info(`🗑️  "${txt}" geklickt`);
        await randomDelay(1500, 2500);
        await clickByText(page, 'Ja', 'button')
          || await clickByText(page, 'Bestätigen', 'button')
          || await clickByText(page, 'OK', 'button');
        await randomDelay(2000, 3000);
        break;
      }
    }

    // ── 6. Neuen Alias erstellen ───────────────────────────────────
    logger.info(`➕ Neuer Alias: ${aliasEmail}`);
    for (const txt of ['Hinzufügen', 'Neu', 'Alias', 'hinzufügen']) {
      const clicked = await clickByText(page, txt, 'button')
        || await clickByText(page, txt, 'a');
      if (clicked) { logger.info(`➕ "${txt}" geklickt`); break; }
    }
    await randomDelay(2000, 3000);

    // Input-Feld finden
    const inputs = await page.$$('input[type="text"]');
    if (inputs.length > 0) {
      await inputs[0].click();
      for (const c of aliasName) {
        await page.keyboard.type(c, { delay: Math.random() * 60 + 30 });
      }
      logger.info(`✅ "${aliasName}" eingetippt`);
    }
    await randomDelay(500, 1000);

    // Speichern
    for (const txt of ['Speichern', 'Erstellen', 'Anlegen', 'OK']) {
      if (await clickByText(page, txt, 'button')) {
        logger.info(`💾 "${txt}" geklickt`);
        break;
      }
    }
    await randomDelay(3000, 5000);

    // Ergebnis prüfen
    const text = await page.evaluate(() => document.body.innerText);
    if (text.includes(aliasName)) {
      logger.info(`✅✅✅ ALIAS ERFOLGREICH: ${aliasEmail}`);
    } else {
      logger.warn(`⚠️  Prüfe manuell...`);
      logger.info('Seite (500): ' + text.substring(0, 500));
    }

    logger.info('⏸️  Browser bleibt 10s offen...');
    await new Promise(r => setTimeout(r, 10000));
    await browser.close();
    logger.info('🏁 Fertig.');

  } catch (err) {
    logger.error(`💥 ${err.message}`);
    try { await page.screenshot({ path: './logs/error.png', fullPage: true }); } catch {}
    try { await browser.close(); } catch {}
  }
})();
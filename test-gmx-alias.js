#!/usr/bin/env node
/**
 * GMX Alias Test-Skript (Puppeteer-kompatibel)
 * ===========================================
 * Verwendet Chrome Profile 73 (zukunftsorientierte.energie@gmail.com).
 * Kein Playwright — alles natives Puppeteer XPath + CSS.
 *
 * Puppeteer hat KEIN :has-text() → XPath mit contains(text(), ...)
 */

require('dotenv').config();
const { createStealthBrowser, randomDelay, humanType } = require('./src/browser');
const { generateAliasName } = require('./src/nameGenerator');
const logger = require('./src/logger');

const GMX_MAIL_URL = 'https://navigator.gmx.net/mail';
const GMX_SETTINGS_URL = 'https://navigator.gmx.net/mail_settings';

/**
 * Puppeteer-kompatibler Helfer: Findet Element per XPath Text-Suche
 */
async function findByText(page, text, tag = '*') {
  const xpath = `//${tag}[contains(text(), '${text}')]`;
  const elements = await page.$x(xpath);
  return elements[0] || null;
}

/**
 * Helfer: Klickt Element mit Text
 */
async function clickByText(page, text, tag = '*') {
  const el = await findByText(page, text, tag);
  if (el) {
    await el.click();
    return true;
  }
  return false;
}

/**
 * Helfer: Findet Element per CSS oder XPath-Fallback
 */
async function findElement(page, cssSelector, textFallback = null) {
  const el = await page.$(cssSelector);
  if (el) return el;
  if (textFallback) return findByText(page, textFallback);
  return null;
}

async function gmxAliasTest() {
  const aliasName = generateAliasName();
  const aliasEmail = `${aliasName}@gmx.de`;

  logger.info('═══════════════════════════════════════');
  logger.info('🧪 GMX Alias Test [Puppeteer + Profile 73]');
  logger.info(`👤 Geplanter Alias: ${aliasEmail}`);
  logger.info('═══════════════════════════════════════');

  // ── Chrome mit Profile 73 starten ──────────────────────────────────
  logger.info('🔧 Chrome mit Profile 73 (zukunftsorientierte.energie@gmail.com)...');
  const { browser, page } = await createStealthBrowser();

  try {
    // ── Schritt 1: GMX Navigator öffnen ───────────────────────────────
    // navigator.gmx.net ist das Webmail-Interface (nicht www.gmx.net)
    logger.info('📬 Öffne GMX Webmail (navigator.gmx.net)...');
    await page.goto(GMX_MAIL_URL, { waitUntil: 'networkidle2', timeout: 30000 });
    await randomDelay(2000, 3000);

    const currentUrl = page.url();
    logger.info(`📍 URL: ${currentUrl}`);

    // Wenn wir auf eine Login/Consent-Seite umgeleitet werden → nicht eingeloggt
    if (currentUrl.includes('login') || currentUrl.includes('consent')) {
      // Bei Consent-Management: Cookies akzeptieren
      if (currentUrl.includes('consent')) {
        logger.info('🍪 Consent-Management erkannt — akzeptiere...');
        const acceptBtn = await findByText(page, 'Alle akzeptieren', 'button')
          || await findByText(page, 'Akzeptieren', 'button')
          || await findByText(page, 'Zustimmen', 'button')
          || await page.$('button[data-accept]')
          || await page.$('.consent-accept');

        if (acceptBtn) {
          await acceptBtn.click();
          await randomDelay(1500, 2500);
          // Redirect abwarten
          await page.waitForNavigation({ waitUntil: 'networkidle2', timeout: 15000 }).catch(() => {});
          await randomDelay();
        }
      }
    }

    // Prüfe finale URL
    const finalUrl = page.url();
    logger.info(`📍 Final URL: ${finalUrl}`);

    if (finalUrl.includes('navigator.gmx.net/mail')) {
      logger.info('✅ Im Posteingang — eingeloggt!');
    } else if (finalUrl.includes('login')) {
      logger.error('❌ NICHT eingeloggt! GMX-Login nötig.');
      await page.screenshot({ path: './logs/01-gmx-login-page.png' });
      logger.info('📸 Screenshot: logs/01-gmx-login-page.png');
      await browser.close();
      return;
    }

    await page.screenshot({ path: './logs/01-gmx-mail.png' });
    logger.info('📸 Screenshot: logs/01-gmx-mail.png');

    // ── Schritt 2: E-Mail-Einstellungen öffnen ────────────────────────
    logger.info('⚙️  Öffne GMX Einstellungen → E-Mail-Adressen...');
    await page.goto(GMX_SETTINGS_URL, { waitUntil: 'networkidle2', timeout: 15000 });
    await randomDelay(2000, 3000);

    await page.screenshot({ path: './logs/02-gmx-settings.png' });
    logger.info(`📍 Settings URL: ${page.url()}`);

    // E-Mail-Adressen Link finden (XPath für Text-Suche)
    let clicked = false;

    // Option A: E-Mail-Adressen Link
    if (await clickByText(page, 'E-Mail-Adressen', 'a')) {
      clicked = true;
      logger.info('🔗 E-Mail-Adressen via Link-Text geklickt');
    } else if (await clickByText(page, 'E-Mail-Adressen', 'span')) {
      clicked = true;
      logger.info('🔗 E-Mail-Adressen via Span-Text geklickt');
    }

    // Option B: Direkt-URL falls Navigation nicht funktioniert
    if (!clicked) {
      logger.info('⚠️  Nav-Link nicht gefunden, versuche Direkt-URL...');
      await page.goto('https://navigator.gmx.net/mail_settings/email_addresses', {
        waitUntil: 'networkidle2', timeout: 15000,
      });
      await randomDelay(2000, 3000);
      clicked = true;
    }

    const aliasPageUrl = page.url();
    logger.info(`📍 E-Mail-Adressen URL: ${aliasPageUrl}`);
    await page.screenshot({ path: './logs/03-gmx-email-addresses.png' });

    // ── Schritt 3: Alias-Löschung (falls vorhanden) ────────────────────
    logger.info('🗑️  Prüfe Aliase...');

    // Zähle vorhandene @gmx.de Adressen auf der Seite
    const pageText = await page.evaluate(() => document.body.innerText);
    const aliases = pageText.match(/[a-z0-9._-]+@gmx\.de/gi) || [];
    logger.info(`📋 ${aliases.length} @gmx.de Adressen gefunden: ${[...new Set(aliases)].join(', ') || 'keine'}`);

    // Lösche Alias wenn vorhanden (Löschen-Button per XPath)
    let deleteClicked = false;
    for (const delText of ['Löschen', 'Entfernen', 'löschen', 'entfernen']) {
      if (await clickByText(page, delText, 'button')) {
        deleteClicked = true;
        logger.info(`🗑️  "${delText}" Button geklickt`);
        await randomDelay(1500, 2500);
        break;
      }
      if (await clickByText(page, delText, 'a')) {
        deleteClicked = true;
        logger.info(`🗑️  "${delText}" Link geklickt`);
        await randomDelay(1500, 2500);
        break;
      }
    }

    if (deleteClicked) {
      // Bestätigung
      for (const confirmText of ['Ja', 'Bestätigen', 'OK', 'Löschen']) {
        if (await clickByText(page, confirmText, 'button')) {
          logger.info(`✅ Bestätigung "${confirmText}" geklickt`);
          break;
        }
      }
      await randomDelay(2000, 3000);
    } else {
      logger.info('ℹ️  Kein Löschen-Button — keine Aliase oder kein Button');
    }

    await page.screenshot({ path: './logs/04-after-delete.png' });

    // ── Schritt 4: Neuen Alias erstellen ──────────────────────────────
    logger.info(`➕ Erstelle Alias: ${aliasEmail}`);

    // "Hinzufügen" / "Neu" finden
    let addClicked = false;
    for (const addText of ['Hinzufügen', 'Neu', 'Alias', 'hinzufügen']) {
      if (await clickByText(page, addText, 'button')) {
        addClicked = true;
        logger.info(`➕ "${addText}" Button geklickt`);
        break;
      }
      if (await clickByText(page, addText, 'a')) {
        addClicked = true;
        logger.info(`➕ "${addText}" Link geklickt`);
        break;
      }
    }

    if (!addClicked) {
      logger.error('❌ Kein Hinzufügen-Button gefunden!');
      await page.screenshot({ path: './logs/99-no-add.png', fullPage: true });
      logger.info('📄 Seiteninhalt (erste 800 Zeichen):');
      logger.info(pageText.substring(0, 800));
      await browser.close();
      return;
    }

    await randomDelay(2000, 3000);
    await page.screenshot({ path: './logs/05-alias-form.png' });

    // Alias-Name eingeben (Input-Feld)
    const inputSelectors = [
      'input[name="alias"]',
      'input[placeholder*="alias" i]',
      'input[placeholder*="Alias" i]',
      'input[placeholder*="Name" i]',
      'input[type="text"]',
    ];

    let inputFound = false;
    for (const sel of inputSelectors) {
      try {
        const input = await page.$(sel);
        if (input) {
          await humanType(page, sel, aliasName);
          await randomDelay(500, 1500);
          inputFound = true;
          logger.info(`✅ "${aliasName}" in Input (${sel}) eingegeben`);
          break;
        }
      } catch {}
    }

    // Fallback: Input per XPath
    if (!inputFound) {
      const textInputs = await page.$x('//input[@type="text"]');
      if (textInputs.length > 0) {
        await textInputs[0].click();
        await textInputs[0].type(aliasName, {
          delay: Math.floor(Math.random() * 80) + 40,
        });
        inputFound = true;
        logger.info(`✅ "${aliasName}" via XPath input[type=text]`);
      }
    }

    if (!inputFound) {
      logger.error('❌ Kein Input-Feld gefunden!');
      await page.screenshot({ path: './logs/99-no-input.png', fullPage: true });
      logger.info('📄 HTML (erste 2000 Zeichen):');
      const html = await page.evaluate(() => document.body.innerHTML);
      logger.info(html.substring(0, 2000));
      await browser.close();
      return;
    }

    // Speichern-Button
    let saveClicked = false;
    for (const saveText of ['Speichern', 'Erstellen', 'Anlegen', 'OK']) {
      if (await clickByText(page, saveText, 'button')) {
        saveClicked = true;
        logger.info(`💾 "${saveText}" geklickt`);
        break;
      }
    }

    if (!saveClicked) {
      // Enter als Fallback
      await page.keyboard.press('Enter');
      logger.info('⏎ Enter gedrückt (Fallback)');
    }

    await randomDelay(3000, 5000);

    // Prüfe das Ergebnis
    const resultUrl = page.url();
    const resultText = await page.evaluate(() => document.body.innerText);

    if (resultText.includes(aliasEmail) || resultText.includes(aliasName)) {
      logger.info(`✅ Alias ${aliasEmail} ERFOLGREICH erstellt!`);
    } else if (resultText.includes('Fehler') || resultText.includes('Error') || resultText.includes('existiert bereits')) {
      logger.warn(`⚠️  Möglicher Fehler bei Alias-Erstellung`);
    }

    await page.screenshot({ path: './logs/06-result.png' });

    // ── ERGEBNIS ──────────────────────────────────────────────────────
    logger.info('═══════════════════════════════════════');
    logger.info('🎉 GMX Alias Test ABGESCHLOSSEN');
    logger.info(`📧 Alias: ${aliasEmail}`);
    logger.info('═══════════════════════════════════════');
    logger.info('⏸️  Browser bleibt 10s offen...');
    await new Promise((r) => setTimeout(r, 10000));
    await browser.close();
  } catch (err) {
    logger.error(`💥 Fehler: ${err.message}`);
    try {
      await page.screenshot({ path: './logs/99-error.png', fullPage: true });
    } catch {}
    await browser.close();
  }
}

gmxAliasTest();
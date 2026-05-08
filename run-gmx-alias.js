#!/usr/bin/env node
/**
 * ╔══════════════════════════════════════════════════════════════════════════════╗
 * ║                    SINATOR-ROTATOR — GMX Alias Test                         ║
 * ╠══════════════════════════════════════════════════════════════════════════════╣
 * ║                                                                              ║
 * ║  ARCHITEKTUR:                                                                ║
 * ║  ┌─────────────┐     ┌──────────────┐     ┌──────────────────┐              ║
 * ║  │ Chrome       │────▶│ CDP Port     │────▶│ puppeteer        │              ║
 * ║  │ subprocess   │     │ 9222         │     │ .connect()       │              ║
 * ║  │ (spawn)      │     │ (WebSocket)  │     │ (direkt via WS)  │              ║
 * ║  └─────────────┘     └──────────────┘     └──────────────────┘              ║
 * ║                                                                              ║
 * ║  PROFIL-STRATEGIE:                                                           ║
 * ║  • Symlink auf ORIGINAL Profile 73 in /tmp                                   ║
 * ║  • Chrome erkennt NON-DEFAULT user-data-dir → erlaubt remote-debugging       ║
 * ║  • Cookies/Logins bleiben im ORIGINAL-Profil erhalten                        ║
 * ║  • KEIN Kopieren = KEINE Verschlüsselungs-Probleme                           ║
 * ║                                                                              ║
 * ║  GMX-CONSENT-STRATEGIE:                                                      ║
 * ║  • Consent-Manager lädt in IFRAME (dl.gmx.net/permission/...)                ║
 * ║  • puppeteer switcht ins Iframe → findet "Akzeptieren und weiter" Button     ║
 * ║  • Klickt via frame.evaluate() + element.click()                             ║
 * ║                                                                              ║
 * ╚══════════════════════════════════════════════════════════════════════════════╝
 */
require('dotenv').config();
const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');
const puppeteer = require('puppeteer');
const http = require('http');

// ─── Konfiguration aus .env ──────────────────────────────────────────────────
// Diese Werte kommen aus der .env-Datei im Projekt-Root.
// CHROME_PATH kann leer sein → puppeteer findet Chrome automatisch.
// GMX_EMAIL + GMX_PASSWORD = Login-Daten für den GMX-Hauptaccount.
const CHROME_BIN = process.env.CHROME_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const CDP_PORT = parseInt(process.env.CDP_PORT || '9222');
const GMX_EMAIL = process.env.GMX_EMAIL;
const GMX_PASS = process.env.GMX_PASSWORD;

// ─── Pfade ───────────────────────────────────────────────────────────────────
// ORIGINAL_PROFILE = das echte Chrome-Profil mit den GMX-Cookies und Logins.
// Wir verlinken es via Symlink in ein TEMP-Verzeichnis,
// weil Chrome remote-debugging NUR mit non-default user-data-dir erlaubt.
const ORIGINAL_PROFILE = '/Users/jeremy/Library/Application Support/Google/Chrome/Profile 73';
const ORIGINAL_CHROME_DIR = '/Users/jeremy/Library/Application Support/Google/Chrome';

// ─── Name Generator ──────────────────────────────────────────────────────────
// Generiert kreative Alias-Namen wie "elron-vader", "swift-hawk" etc.
const ADJECTIVES = 'elron dark swift iron silver golden black red blue storm fire ice shadow bright wild stone thunder ghost steel neon cyber alpha omega nova solar lunar astro turbo hyper ultra mega super'.split(' ');
const NOUNS = 'vader runner hawk wolf fox bear eagle tiger lion shark blade storm rider hunter seeker knight wizard ranger pilot scout agent cipher nexus apex viper cobra falcon raven phoenix dragon titan zeus'.split(' ');

function generateAliasName() {
  return ADJECTIVES[Math.floor(Math.random() * ADJECTIVES.length)] + '-' +
         NOUNS[Math.floor(Math.random() * NOUNS.length)];
}

// ─── Hilfsfunktionen ─────────────────────────────────────────────────────────

/** Wartet ms Millisekunden */
const sleep = ms => new Promise(r => setTimeout(r, ms));

/** Zufälliges Delay zwischen min und max ms (Human-like) */
function randomDelay(min, max) {
  return Math.floor(Math.random() * (max - min + 1)) + min;
}

/**
 * Holt die CDP WebSocket-URL vom laufenden Chrome.
 * Chrome öffnet den Debug-Port und stellt unter /json/version
 * die webSocketDebuggerUrl bereit, über die puppeteer.connect() sich verbindet.
 *
 * @param {number} port - Der CDP-Debug-Port (default: 9222)
 * @returns {Promise<string>} WebSocket-URL für puppeteer.connect()
 */
function getWebSocketUrl(port) {
  return new Promise((resolve, reject) => {
    const req = http.get(`http://127.0.0.1:${port}/json/version`, res => {
      let body = '';
      res.on('data', chunk => body += chunk);
      res.on('end', () => {
        try { resolve(JSON.parse(body).webSocketDebuggerUrl); }
        catch (e) { reject(e); }
      });
    });
    req.on('error', reject);
    req.setTimeout(5000, () => { req.destroy(); reject(new Error('CDP timeout')); });
  });
}

/**
 * Wartet bis Chrome gestartet ist und der CDP-Port antwortet.
 * Retry-Loop: versucht es mehrfach mit 1s Abstand.
 *
 * @param {number} port - CDP-Port
 * @param {number} maxRetries - Maximale Anzahl Versuche
 * @returns {Promise<string>} WebSocket-URL
 */
async function waitForCdp(port, maxRetries = 15) {
  for (let i = 0; i < maxRetries; i++) {
    try { return await getWebSocketUrl(port); }
    catch { await sleep(1000); }
  }
  throw new Error(`CDP nicht erreichbar auf Port ${port} nach ${maxRetries} Versuchen`);
}

/**
 * Klickt einen Button MIT BESTIMMTEM TEXT in einem Frame.
 * Sucht alle Buttons im Frame, findet den mit passendem Text,
 * und klickt ihn via DOM-API.
 *
 * WARUM FRAME? GMX Consent lädt in einem IFRAME von dl.gmx.net/permission/...
 * puppeteer kann in Frames wechseln und darin Elemente manipulieren.
 *
 * @param {puppeteer.Frame} frame - Der Iframe in dem gesucht wird
 * @param {string} textContains - Text der im Button enthalten sein muss
 * @returns {Promise<boolean>} true wenn Button gefunden und geklickt
 */
async function clickButtonInFrame(frame, textContains) {
  return frame.evaluate((searchText) => {
    const buttons = document.querySelectorAll('button');
    for (const btn of buttons) {
      const label = (btn.textContent || '').trim();
      if (label.includes(searchText)) {
        btn.click();
        return true;
      }
    }
    return false;
  }, textContains);
}

/**
 * Sucht das GMX-Consent-IFrame und klickt den Accept-Button.
 * GMX lädt den Consent-Dialog in einem Iframe von:
 *   dl.gmx.net/permission/live/portal/v1/ppp/core.html
 *
 * Wir müssen:
 *   1. Alle Frames der Page durchgehen
 *   2. Das Permission-Iframe finden
 *   3. Darin den "Akzeptieren und weiter" Button klicken
 *   4. Warten bis die Haupt-Seite nach dem Consent neu lädt
 *
 * @param {puppeteer.Page} page - Die aktuelle Page
 * @returns {Promise<boolean>} true wenn Consent erfolgreich akzeptiert
 */
async function acceptGmxConsent(page) {
  const frames = page.frames();
  for (const frame of frames) {
    const frameUrl = frame.url();
    // Das Consent-Iframe kommt von dl.gmx.net/permission/
    if (frameUrl.includes('permission') || frameUrl.includes('ppp')) {
      console.log(`   📋 Consent-Iframe: ${frameUrl.substring(0, 70)}...`);

      // Buttons im Iframe auflisten (Debug)
      const btns = await frame.evaluate(() =>
        Array.from(document.querySelectorAll('button')).map(b => b.textContent?.trim())
      );
      console.log(`   🔘 Buttons im Consent: [${btns.filter(Boolean).join(', ')}]`);

      // Versuche verschiedene Accept-Texte (GMX kann variieren)
      const acceptTexts = ['Akzeptieren', 'Alle akzeptieren', 'Zustimmen', 'Accept'];
      for (const txt of acceptTexts) {
        const clicked = await clickButtonInFrame(frame, txt);
        if (clicked) {
          console.log(`   ✅ "${txt}" geklickt!`);
          await sleep(4000);
          try { await page.waitForNavigation({ timeout: 10000 }); } catch {}
          return true;
        }
      }
    }
  }
  return false;
}

// ═══════════════════════════════════════════════════════════════════════════════
//  MAIN — Kompletter GMX Alias Flow
// ═══════════════════════════════════════════════════════════════════════════════
(async () => {
  const aliasName = generateAliasName();
  const aliasEmail = `${aliasName}@gmx.de`;
  console.log(`\n👤 NEUER ALIAS: ${aliasEmail}`);
  console.log(`🔑 GMX Login:   ${GMX_EMAIL}\n`);

  // ── PHASE 0: Chrome-Profil vorbereiten ─────────────────────────────────
  // Chrome erlaubt --remote-debugging-port NUR mit non-default user-data-dir.
  // Lösung: Symlink auf das ORIGINAL Profile 73 in /tmp.
  // Chrome sieht /tmp als user-data-dir (non-default) → erlaubt Debugging.
  // Das Profil ist via Symlink = original → Cookies/Logins bleiben erhalten.
  const tempDir = `/tmp/sinator-gmx-${Date.now()}`;
  fs.mkdirSync(tempDir, { recursive: true });
  fs.symlinkSync(ORIGINAL_PROFILE, path.join(tempDir, 'Profile 73'));

  try { fs.copyFileSync(path.join(ORIGINAL_CHROME_DIR, 'Local State'), path.join(tempDir, 'Local State')); } catch {}
  try { fs.copyFileSync(path.join(ORIGINAL_CHROME_DIR, 'Last Version'), path.join(tempDir, 'Last Version')); } catch {}
  fs.writeFileSync(path.join(tempDir, 'First Run'), '');

  console.log('🚀 Chrome wird gestartet...\n');

  // ── PHASE 1: Chrome Subprocess starten ─────────────────────────────────
  // KEIN puppeteer.launch() — das würde Automation-Flags setzen die GMX erkennt.
  // Stattdessen: direkter spawn() ohne Puppeteer-Eingriffe.
  // So sieht Chrome aus wie ein NORMAL gestarteter Browser.
  const chromeProc = spawn(CHROME_BIN, [
    `--user-data-dir=${tempDir}`,
    `--remote-debugging-port=${CDP_PORT}`,
    '--remote-allow-origins=*',
    '--no-first-run',
    '--no-default-browser-check',
    '--profile-directory=Profile 73',
    '--window-size=1280,800',
    '--lang=de-DE',
    'https://www.gmx.net/',
  ], { stdio: 'ignore' });

  // ── PHASE 2: Auf CDP-Bereitschaft warten ───────────────────────────────
  console.log('⏳ Warte auf CDP...');
  const wsUrl = await waitForCdp(CDP_PORT);
  console.log(`🔗 CDP verbunden: ${wsUrl.substring(0, 55)}...\n`);

// ── PHASE 3: puppeteer via CDP connecten ───────────────────────────────
  const browser = await puppeteer.connect({ browserWSEndpoint: wsUrl });
  const page = (await browser.pages())[0];

  // Warten bis die Seite wirklich geladen ist (kann etwas dauern)
  await sleep(2000);
  let currentUrl = page.url();
  console.log(`📍 Aktuelle URL: ${currentUrl}`);

  // ── PHASE 4: GMX Consent-Management ────────────────────────────────────
  // GMX lädt als erstes den Consent-Manager im Iframe.
  // Wir warten auf das Erscheinen des Consent-Iframes.
  // Der Consent kann auch nach einem Redirect erscheinen.

  // WICHTIG: Zuerst prüfen ob wir auf der Consent-Seite sind.
  // Die URL kann auch leer sein (about:blank → Weiterleitung).
  const isConsentPage = currentUrl.includes('consent') || currentUrl === ':' || !currentUrl;
  if (isConsentPage) {
    console.log('\n🍪 GMX Consent-Manager erwartet...');
    // Warte auf das Consent-Iframe (kann bis zu 8s dauern)
    let consentAccepted = false;
    for (let attempt = 1; attempt <= 8; attempt++) {
      await sleep(1500);
      currentUrl = page.url();
      console.log(`   🔄 Versuch ${attempt}/8 | URL: ${currentUrl}`);
      if (await acceptGmxConsent(page)) {
        consentAccepted = true;
        break;
      }
      // Wenn URL sich ändert (z.B. zu www.gmx.net nach Consent)
      if (currentUrl.includes('gmx.net') && !currentUrl.includes('consent')) break;
    }

    if (!consentAccepted && page.url().includes('consent')) {
      console.log('   ⚠️  Consent nicht automatisch akzeptiert.');
      console.log('   Bitte MANUELL klicken... (warte 12s)');
      await sleep(12000);
    }

currentUrl = page.url();
    console.log(`📍 Nach Consent-Phase: ${currentUrl}\n`);
  }

  // ── PHASE 5: GMX Login ─────────────────────────────────────────────────
  console.log('🔐 GMX LOGIN');

  // Sicherstellen dass wir auf www.gmx.net sind (nicht mehr auf Consent)
  // Wenn immer noch auf Consent → Seite ist nicht geladen → warten
  if (!currentUrl.includes('www.gmx.net') || currentUrl.includes('consent')) {
    console.log('   ⏳ Warte auf www.gmx.net (nicht consent)...');
    for (let i = 0; i < 10; i++) {
      await sleep(1000);
      currentUrl = page.url();
      if (currentUrl.includes('www.gmx.net') && !currentUrl.includes('consent')) break;
    }
    console.log(`   📍 ${currentUrl}`);
  }

  // Wenn wir auf einer nicht-gmx Seite sind → direkt zu gmx.net navigieren
  if (!currentUrl.includes('gmx.net')) {
    console.log('   🌐 Navigiere zu www.gmx.net...');
    await page.goto('https://www.gmx.net/', { waitUntil: 'domcontentloaded', timeout: 15000 });
    await sleep(3000);
    currentUrl = page.url();
    console.log(`   📍 ${currentUrl}`);
  }

  console.log('   Suche Login-Button...');

  // Login-Link auf der GMX-Startseite finden und klicken
  await page.evaluate(() => {
    for (const el of document.querySelectorAll('a, button, span')) {
      if ((el.textContent || '').trim() === 'Login') { el.click(); return; }
    }
  });
  await sleep(4000);
  try { await page.waitForNavigation({ timeout: 10000 }); } catch {}
  currentUrl = page.url();
  console.log(`   📍 Login-Seite: ${currentUrl}`);

  // 403-Check: Wenn GMX uns blockiert → Fehler
  if (currentUrl.includes('403')) {
    console.log('   ❌ GMX blockiert den Login (403 Forbidden).');
    await browser.disconnect();
    chromeProc.kill();
    process.exit(1);
  }

  // E-Mail-Feld finden
  const emailField = await page.$('input[name="username"], input[type="email"], #email, input[name="email"]');
  if (!emailField) {
    console.log('   ❌ E-Mail-Feld nicht gefunden!');
    await browser.disconnect();
    chromeProc.kill();
    process.exit(1);
  }

  // E-Mail eintippen und abschicken
  console.log('   📧 E-Mail eintippen...');
  await emailField.click();
  await sleep(300);
  for (const char of GMX_EMAIL) {
    await page.keyboard.type(char, { delay: randomDelay(30, 80) });
  }
  console.log('   ✅ E-Mail eingegeben');

  // AUTH.GMX.NET hat ZWEISTUFIGEN Login (JavaScript-Transition, KEIN Page-Reload!):
  // Schritt 1: E-Mail → Next/Enter → JS zeigt Passwort-Feld
  // Schritt 2: Passwort → Enter → Login
  console.log('   ⏎ E-Mail abschicken (Next)...');

  // Enter drücken (auth.gmx.net reagiert auf Enter im E-Mail-Feld)
  await page.keyboard.press('Enter');
  console.log('   ⏳ Warte auf Passwort-Feld (JS-Transition)...');

  // Warte bis das Passwort-Feld erscheint (auth.gmx.net macht JS-Show/Hide)
  try {
    await page.waitForSelector('input[type="password"]', { timeout: 8000 });
  } catch {
    // Fallback: Seite analysieren
    const debugHtml = await page.evaluate(() => document.body.innerHTML.substring(0, 1500));
    console.log(`   ⚠️  Passwort-Feld nicht erschienen. HTML:\n${debugHtml}`);
    await browser.disconnect();
    chromeProc.kill();
    process.exit(1);
  }

  console.log('   ✅ Passwort-Feld erschienen');

  // Passwort-Feld finden
  const passField = await page.$('input[type="password"]');
  if (!passField) {
    console.log('   ❌ Passwort-Feld nicht gefunden!');
    await browser.disconnect();
    chromeProc.kill();
    process.exit(1);
  }

  // Passwort eintippen
  console.log('   🔐 Passwort eintippen...');
  await passField.click();
  await sleep(300);
  for (const char of GMX_PASS) {
    await page.keyboard.type(char, { delay: randomDelay(30, 70) });
  }
  console.log('   ✅ Passwort eingegeben');

  // Login abschicken (Enter)
  console.log('   ⏎ Login abschicken...');
  await page.keyboard.press('Enter');
  await sleep(5000);
  try { await page.waitForNavigation({ timeout: 15000 }); } catch {}
  currentUrl = page.url();
  console.log(`   📍 Nach Login: ${currentUrl}`);

  // Post-Login: Erneuter Consent-Check (GMX fragt nach Login nochmal)
  if (currentUrl.includes('consent')) {
    console.log('   🍪 Post-Login Consent...');
    for (let attempt = 1; attempt <= 3; attempt++) {
      if (await acceptGmxConsent(page)) break;
      await sleep(2000);
    }
    currentUrl = page.url();
    console.log(`   📍 Nach Post-Consent: ${currentUrl}`);
  }

  // Login-Erfolg prüfen: navigator.gmx.net = eingeloggt
  if (currentUrl.includes('navigator.gmx.net')) {
    console.log('\n✅✅✅ GMX LOGIN ERFOLGREICH!\n');
  } else {
    console.log(`\n⚠️  Nicht auf navigator.gmx.net: ${currentUrl}\n`);
  }

  // ── PHASE 6: GMX Alias-Verwaltung ──────────────────────────────────────
  console.log('📧 ALIAS-VERWALTUNG');
  console.log('   Öffne E-Mail-Adressen Seite...');

  await page.goto('https://navigator.gmx.net/mail_settings/email_addresses', {
    waitUntil: 'domcontentloaded', timeout: 15000,
  });
  await sleep(4000);
  console.log(`   📍 ${page.url()}`);

  // 6a. Vorhandenen Alias löschen
  console.log('   🗑️  Prüfe auf existierende Aliase...');
  await page.evaluate(() => {
    for (const el of document.querySelectorAll('button, a')) {
      if ((el.textContent || '').includes('Löschen')) { el.click(); return; }
    }
  });
  await sleep(2000);

  // Bestätigung des Lösch-Dialogs
  await page.evaluate(() => {
    for (const el of document.querySelectorAll('button')) {
      if ((el.textContent || '').includes('Ja') || (el.textContent || '').includes('Bestätigen')) {
        el.click(); return;
      }
    }
  });
  await sleep(3000);

  // 6b. Neuen Alias erstellen
  console.log(`   ➕ Neuer Alias: ${aliasEmail}`);
  await page.evaluate(() => {
    for (const el of document.querySelectorAll('button, a')) {
      const txt = el.textContent || '';
      if (txt.includes('Hinzufügen') || txt.includes('Neu') || txt.includes('Alias')) {
        el.click(); return;
      }
    }
  });
  await sleep(3000);

  // 6c. Alias-Namen in Input-Feld tippen
  const textInput = await page.$('input[type="text"]');
  if (textInput) {
    await textInput.click();
    await sleep(300);
    for (const char of aliasName) {
      await page.keyboard.type(char, { delay: randomDelay(25, 60) });
    }
    console.log(`   ✅ Alias-Name "${aliasName}" eingetippt`);
  }

  // 6d. Speichern
  await page.evaluate(() => {
    for (const el of document.querySelectorAll('button')) {
      const txt = el.textContent || '';
      if (txt.includes('Speichern') || txt.includes('Erstellen') || txt.includes('OK')) {
        el.click(); return;
      }
    }
  });
  await sleep(5000);

  // ── PHASE 7: Ergebnis prüfen ───────────────────────────────────────────
  const resultText = await page.evaluate(() => document.body.innerText);

  if (resultText.includes(aliasName)) {
    console.log(`\n🎉🎉🎉 ALIAS ERFOLGREICH ERSTELLT: ${aliasEmail}`);
  } else {
    console.log(`\n⚠️  Alias "${aliasName}" nicht im Seiten-Text gefunden.`);
    console.log(`   Manuell prüfen.\n`);
  }
  console.log(`   📄 Seiten-Text (Ausschnitt): ${resultText.substring(0, 300)}\n`);

  // ── Cleanup ────────────────────────────────────────────────────────────
  console.log('⏸️  Browser bleibt 10 Sekunden offen...');
  await sleep(10000);

  await browser.disconnect();
  chromeProc.kill('SIGTERM');
  console.log('🏁 Fertig.');
})().catch(err => {
  console.error('💥 Fataler Fehler:', err.message);
  process.exit(1);
});
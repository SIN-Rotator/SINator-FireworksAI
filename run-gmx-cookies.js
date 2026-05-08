#!/usr/bin/env node
/**
 * ╔══════════════════════════════════════════════════════════════════════════════╗
 * ║           SINATOR-ROTATOR — GMX Cookie Injection & Alias Flow                ║
 * ╠══════════════════════════════════════════════════════════════════════════════╣
 * ║                                                                              ║
 * ║  ZWECK:                                                                      ║
 * ║  Startet Chrome mit kopiertem Profil, injiziert gespeicherte GMX-Cookies     ║
 * ║  via CDP Network.setCookies, und führt den kompletten Alias-Erstellungs-     ║
 * ║  Flow durch.                                                                   ║
 * ║                                                                              ║
 * ║  WARUM COOKIE-INJECTION NACH PROFIL-KOPIE?                                   ║
 * ║  Das kopierte Profil hat eine ABGELAUFENE Session (Chrome erstellt neue      ║
 * ║  Security Tokens beim Kopieren). Die frischen Cookies aus                    ║
 * ║  extract-gmx-cookies.js werden via CDP Network.setCookies injiziert.         ║
 * ║                                                                              ║
 * ║  ABLAUF:                                                                      ║
 * ║  1. Profil kopieren (Local State + Profile 73 → /tmp)                        ║
 * ║  2. Chrome starten mit --user-data-dir=/tmp/...                              ║
 * ║  3. CDP verbinden via puppeteer.connect()                                    ║
 * ║  4. Cookies injizieren via CDP Network.setCookies                            ║
 * ║  5. GMX öffnen → Session prüfen → Alias erstellen                            ║
 * ║                                                                              ║
 * ╚══════════════════════════════════════════════════════════════════════════════╝
 */
require('dotenv').config();
const { spawn, execSync } = require('child_process');
const fs = require('fs');
const path = require('path');
const http = require('http');
const puppeteer = require('puppeteer');

// ═══════════════════════════════════════════════════════════════════════════════
//  KONSTANTEN
// ═══════════════════════════════════════════════════════════════════════════════

const CHROME_BIN = process.env.CHROME_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const SOURCE_USER_DATA_DIR = '/Users/jeremy/Library/Application Support/Google/Chrome';
const SOURCE_PROFILE_NAME = 'Profile 73';
const CDP_PORT = parseInt(process.env.CDP_PORT || '9222');
const COOKIES_FILE = path.join(__dirname, 'data', 'gmx-cookies.json');

// ═══════════════════════════════════════════════════════════════════════════════
//  ALIAS-NAMEN-GENERATOR
// ═══════════════════════════════════════════════════════════════════════════════

const ADJECTIVES = [
  'elron', 'dark', 'swift', 'iron', 'silver', 'golden', 'black', 'red',
  'blue', 'storm', 'fire', 'ice', 'shadow', 'bright', 'wild', 'stone',
  'thunder', 'ghost', 'steel', 'neon', 'cyber', 'alpha', 'omega', 'nova',
  'solar', 'lunar', 'astro', 'turbo', 'hyper', 'ultra', 'mega', 'super',
];

const NOUNS = [
  'vader', 'runner', 'hawk', 'wolf', 'fox', 'bear', 'eagle', 'tiger',
  'lion', 'shark', 'blade', 'storm', 'rider', 'hunter', 'seeker', 'knight',
  'wizard', 'ranger', 'pilot', 'scout', 'agent', 'cipher', 'nexus', 'apex',
  'viper', 'cobra', 'falcon', 'raven', 'phoenix', 'dragon', 'titan', 'zeus',
];

function generateAliasName() {
  const adj = ADJECTIVES[Math.floor(Math.random() * ADJECTIVES.length)];
  const noun = NOUNS[Math.floor(Math.random() * NOUNS.length)];
  return `${adj}-${noun}`;
}

// ═══════════════════════════════════════════════════════════════════════════════
//  HILFSFUNKTIONEN
// ═══════════════════════════════════════════════════════════════════════════════

const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));

function getWebSocketUrl(port) {
  return new Promise((resolve, reject) => {
    const req = http.get(`http://127.0.0.1:${port}/json/version`, res => {
      let body = '';
      res.on('data', chunk => body += chunk);
      res.on('end', () => {
        try {
          const json = JSON.parse(body);
          if (json.webSocketDebuggerUrl) resolve(json.webSocketDebuggerUrl);
          else reject(new Error(`Kein webSocketDebuggerUrl: ${body.substring(0, 200)}`));
        } catch (e) {
          reject(new Error(`Invalid JSON: ${body.substring(0, 200)}`));
        }
      });
    });
    req.on('error', reject);
    req.setTimeout(5000, () => { req.destroy(); reject(new Error('CDP timeout')); });
  });
}

async function waitForCdp(port, maxRetries = 15) {
  for (let i = 0; i < maxRetries; i++) {
    try { return await getWebSocketUrl(port); }
    catch { await sleep(1000); }
  }
  throw new Error(`CDP nicht erreichbar nach ${maxRetries}s auf Port ${port}`);
}

function copyChromeProfile() {
  const tempDir = `/tmp/sinator-gmx-${Date.now()}`;
  const sourceProfile = path.join(SOURCE_USER_DATA_DIR, SOURCE_PROFILE_NAME);

  console.log(`📋 Kopiere Profil: ${sourceProfile} → ${tempDir}`);
  fs.mkdirSync(tempDir, { recursive: true });

  const localStateSrc = path.join(SOURCE_USER_DATA_DIR, 'Local State');
  if (fs.existsSync(localStateSrc)) {
    fs.copyFileSync(localStateSrc, path.join(tempDir, 'Local State'));
    console.log('   ✅ Local State kopiert');
  }

  if (fs.existsSync(sourceProfile)) {
    execSync(`cp -R "${sourceProfile}" "${tempDir}"`, { stdio: 'pipe' });
    console.log(`   ✅ ${SOURCE_PROFILE_NAME} kopiert`);
  }

  fs.writeFileSync(path.join(tempDir, 'First Run'), '');
  return tempDir;
}

function cleanupTempProfile(tempDir) {
  if (tempDir && tempDir.startsWith('/tmp/sinator-gmx-')) {
    try {
      execSync(`rm -rf "${tempDir}"`, { stdio: 'pipe' });
      console.log(`🗑️  Temp-Profil aufgeräumt`);
    } catch (e) {
      console.log(`⚠️  Aufräumen fehlgeschlagen: ${e.message}`);
    }
  }
}

/**
 * Injiziert Cookies via CDP Network.setCookies.
 *
 * WARUM CDP? page.setCookie() erfordert dass die Ziel-Domain geladen ist
 * und kann zu unerwünschten Redirects führen (www.gmx.net statt navigator.gmx.net).
 * CDP Network.setCookies setzt Cookies direkt im Browser-Cookie-Store.
 *
 * @param {CDPSession} cdp - CDP Session
 * @param {Object[]} cookies - Array von Cookie-Objekten
 */
async function injectCookiesViaCDP(cdp, cookies) {
  console.log(`🍪 Injiziere ${cookies.length} Cookies via CDP...`);

  const cdpCookies = cookies.map(c => ({
    name: c.name,
    value: c.value,
    domain: c.domain,
    path: c.path || '/',
    expires: typeof c.expires === 'number' && c.expires > 0 ? c.expires : -1,
    httpOnly: c.httpOnly || false,
    secure: c.secure || false,
    sameSite: c.sameSite || 'None',
    // url = Scope des Cookies. Muss auf domain matchen.
    url: c.domain.startsWith('.') ? `https://${c.domain.substring(1)}` : `https://${c.domain}`,
  }));

  try {
    await cdp.send('Network.setCookies', { cookies: cdpCookies });
    console.log('   ✅ Cookies injiziert');
  } catch (e) {
    console.log(`   ⚠️  CDP setCookies Fehler: ${e.message}`);
    throw e;
  }
}

// ═══════════════════════════════════════════════════════════════════════════════
//  MAIN — GMX ALIAS FLOW MIT COOKIE-INJECTION
// ═══════════════════════════════════════════════════════════════════════════════
(async () => {
  const aliasName = generateAliasName();
  const aliasEmail = `${aliasName}@gmx.de`;
  console.log(`\n👤 NEUER ALIAS: ${aliasEmail}\n`);

  let tempDir = null;
  let chromeProc = null;
  let browser = null;

  try {
    // ── PHASE 0 | PROFIL KOPIEREN ──────────────────────────────────────
    console.log('📦 Phase 0: Chrome-Profil kopieren');
    tempDir = copyChromeProfile();

    // ── PHASE 1 | CHROME STARTEN ───────────────────────────────────────
    console.log('\n🚀 Phase 1: Chrome starten');
    chromeProc = spawn(CHROME_BIN, [
      `--user-data-dir=${tempDir}`,
      `--profile-directory=${SOURCE_PROFILE_NAME}`,
      `--remote-debugging-port=${CDP_PORT}`,
      '--remote-allow-origins=*',
      '--no-first-run',
      '--no-default-browser-check',
      '--window-size=1280,800',
      '--lang=de-DE',
      'about:blank',
    ], { stdio: 'ignore' });

    // ── PHASE 2 | CDP VERBINDEN ────────────────────────────────────────
    console.log('\n🔗 Phase 2: CDP verbinden');
    const wsUrl = await waitForCdp(CDP_PORT);
    console.log(`   ✅ CDP: ${wsUrl.substring(0, 60)}...`);

    browser = await puppeteer.connect({ browserWSEndpoint: wsUrl });
    const pages = await browser.pages();
    const page = pages[0] || await browser.newPage();

    // ── PHASE 3 | COOKIES INJIZIEREN ───────────────────────────────────
    console.log('\n🍪 Phase 3: Cookies injizieren');
    const cookies = JSON.parse(fs.readFileSync(COOKIES_FILE, 'utf-8'));
    const cdp = await page.createCDPSession();
    await cdp.send('Network.enable');

    // ZUERST zu GMX navigieren (sonst kann page.cookies() keine Cookies zeigen)
    console.log('   🌐 Navigiere zu www.gmx.net für Cookie-Kontext...');
    await page.goto('https://www.gmx.net/', { waitUntil: 'domcontentloaded', timeout: 15000 });
    await sleep(2000);

    // JETZT Cookies injizieren
    await injectCookiesViaCDP(cdp, cookies);

    // Verifizierung: Cookies für aktuelle Domain prüfen
    const activeCookies = await page.cookies();
    const gmxActive = activeCookies.filter(c => c.domain.includes('gmx'));
    console.log(`   📊 ${gmxActive.length} GMX-Cookies im Store aktiv\n`);

    // Seite refreshen damit die neuen Cookies wirksam werden
    console.log('   🔄 Seite refreshen für Session-Aktivierung...');
    await page.reload({ waitUntil: 'domcontentloaded', timeout: 15000 });
    await sleep(3000);

    // ── PHASE 4 | GMX SESSION PRÜFEN ───────────────────────────────────
    console.log('📬 Phase 4: GMX Session-Check');
    await page.goto('https://navigator.gmx.net/mail', {
      waitUntil: 'domcontentloaded', timeout: 20000,
    });
    await sleep(3000);

    const sessionUrl = page.url();
    console.log(`   📍 URL: ${sessionUrl}`);

    if (sessionUrl.includes('navigator.gmx.net') || sessionUrl.includes('bap.navigator')) {
      console.log('   ✅✅✅ EINGELOGGT! Session aktiv!\n');
    } else if (sessionUrl.includes('consent')) {
      console.log('   🍪 Consent-Manager detected');
      for (const frame of page.frames()) {
        if (frame.url().includes('permission') || frame.url().includes('ppp')) {
          await frame.evaluate(() => {
            for (const btn of document.querySelectorAll('button')) {
              if ((btn.textContent || '').includes('Akzeptieren')) { btn.click(); return; }
            }
          });
          console.log('   ✅ Consent akzeptiert');
          await sleep(4000);
          break;
        }
      }
    } else if (sessionUrl.includes('login') || sessionUrl.includes('auth.gmx')) {
      console.log('   ❌ NICHT eingeloggt! Cookies abgelaufen.');
      console.log('   Bitte extract-gmx-cookies.js erneut ausführen.\n');
      process.exit(1);
    } else {
      console.log(`   ⚠️  Unerwartete URL: ${sessionUrl}\n`);
    }

    // ── PHASE 5 | ALIAS SEITE ÖFFNEN ───────────────────────────────────
    console.log('📧 Phase 5: E-Mail-Adressen öffnen');
    await page.goto('https://navigator.gmx.net/mail_settings/email_addresses', {
      waitUntil: 'domcontentloaded', timeout: 15000,
    });
    await sleep(4000);
    console.log(`   📍 ${page.url()}\n`);

    // ── PHASE 6 | EXISTIERENDEN ALIAS LÖSCHEN ──────────────────────────
    console.log('🗑️  Phase 6: Existierenden Alias löschen');
    const deleted = await page.evaluate(() => {
      for (const el of document.querySelectorAll('button, a')) {
        const txt = (el.textContent || '').trim();
        if (txt === 'Löschen' || txt === 'E-Mail-Adresse löschen' || txt === 'Alias löschen') {
          el.click();
          return txt;
        }
      }
      return null;
    });

    if (deleted) {
      console.log(`   ✅ "${deleted}" geklickt`);
      await sleep(2000);
      await page.evaluate(() => {
        for (const el of document.querySelectorAll('button')) {
          const txt = el.textContent || '';
          if (txt.includes('Ja') || txt.includes('Bestätigen') || txt.includes('OK')) {
            el.click();
            return;
          }
        }
      });
      await sleep(3000);
      console.log('   ✅ Alias gelöscht\n');
    } else {
      console.log('   ℹ️  Kein Alias zum Löschen gefunden\n');
    }

    // ── PHASE 7 | NEUEN ALIAS ERSTELLEN ────────────────────────────────
    console.log(`➕ Phase 7: Neuen Alias erstellen: ${aliasEmail}`);
    const addClicked = await page.evaluate(() => {
      const targets = ['Hinzufügen', 'Neue E-Mail-Adresse hinzufügen', 'Alias erstellen',
        'Alias-Adresse erstellen', 'Weitere E-Mail-Adresse', 'Neuen Alias anlegen'];
      for (const el of document.querySelectorAll('button, a')) {
        const txt = (el.textContent || '').trim();
        for (const t of targets) {
          if (txt.includes(t)) { el.click(); return txt.substring(0, 30); }
        }
      }
      return null;
    });

    if (!addClicked) {
      console.log('   ❌ Kein "Hinzufügen"-Button gefunden!');
      const pageText = await page.evaluate(() => document.body.innerText.substring(0, 500));
      console.log(`   📄 Seiten-Text: ${pageText}`);
      process.exit(1);
    }
    console.log(`   ✅ "${addClicked}" geklickt`);
    await sleep(3000);

    const textInput = await page.$('input[type="text"]');
    if (!textInput) {
      console.log('   ❌ Kein Input-Feld gefunden!');
      process.exit(1);
    }

    await textInput.click();
    await sleep(300);
    for (const char of aliasName) {
      await page.keyboard.type(char, { delay: Math.floor(Math.random() * 35) + 25 });
    }
    console.log(`   ✅ "${aliasName}" eingetippt`);
    await sleep(500);

    const saved = await page.evaluate(() => {
      for (const el of document.querySelectorAll('button')) {
        const txt = el.textContent || '';
        if (txt.includes('Speichern') || txt.includes('Erstellen') || txt.includes('OK')) {
          el.click();
          return true;
        }
      }
      return false;
    });

    if (!saved) await page.keyboard.press('Enter');

    console.log('   ⏳ Warte auf Speicherung...');
    await sleep(5000);

    // ── PHASE 8 | ERGEBNIS PRÜFEN ──────────────────────────────────────
    console.log('\n🔍 Phase 8: Ergebnis prüfen');
    const resultText = await page.evaluate(() => document.body.innerText);

    if (resultText.includes(aliasName)) {
      console.log(`\n🎉🎉🎉 ALIAS ERFOLGREICH ERSTELLT: ${aliasEmail}\n`);
    } else {
      console.log(`\n⚠️  Alias "${aliasName}" nicht gefunden.`);
      console.log(`   📄 Text: ${resultText.substring(0, 400)}\n`);
    }

    // ── CLEANUP ────────────────────────────────────────────────────────
    console.log('⏸️  Browser bleibt 10 Sekunden offen zur Inspektion...');
    await sleep(10000);

  } catch (err) {
    console.error('\n💥 FATALER FEHLER:', err.message);
    console.error(err.stack);
  } finally {
    if (browser) { try { await browser.disconnect(); } catch {} }
    if (chromeProc) { try { chromeProc.kill('SIGTERM'); } catch {} }
    cleanupTempProfile(tempDir);
    console.log('🏁 SINator-Rotator beendet.\n');
  }
})();

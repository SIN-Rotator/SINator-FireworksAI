#!/usr/bin/env node
/**
 * ╔══════════════════════════════════════════════════════════════════════════════╗
 * ║                SINATOR-ROTATOR — GMX Cookie Extraction                       ║
 * ╠══════════════════════════════════════════════════════════════════════════════╣
 * ║                                                                              ║
 * ║  ZWECK:                                                                      ║
 * ║  Extrahiert GMX-Session-Cookies aus einem LÄUFENDEN Chrome-Profil und       ║
 * ║  speichert sie in ./data/gmx-cookies.json für die spätere Automation.        ║
 * ║                                                                              ║
 * ║  WARUM COOKIE-EXTRACTION?                                                     ║
 * ║  GMX zeigt nach Email-Eingabe im Login-Flow einen CAPTCHA.                   ║
 * ║  Automatisches Login ist damit nicht zuverlässig möglich.                    ║
 * ║  Lösung: Nutzer loggt sich EINMAL manuell ein → Script extrahiert Cookies    ║
 * ║  → Bei jedem weiteren Lauf werden die Cookies in ein kopiertes Profil        ║
 * ║  injectet → GMX erkennt den Browser als bereits eingeloggt.                  ║
 * ║                                                                              ║
 * ║  ARCHITEKTUR:                                                                 ║
 * ║  ┌─────────────────────────────────────────────────────────────────────┐    ║
 * ║  │ Phase 0: Chrome-Profil kopieren (Local State + Profile 73 → /tmp)  │    ║
 * ║  │ Phase 1: Chrome via spawn() mit kopiertem user-data-dir starten     │    ║
 * ║  │ Phase 2: Auf CDP-Bereitschaft warten (Retry-Loop, max 15s)         │    ║
 * ║  │ Phase 3: puppeteer.connect() zum WebSocket-Endpoint                │    ║
 * ║  │ Phase 4: GMX-Seite öffnen → prüfen ob Session aktiv                │    ║
 * ║  │ Phase 5: Cookies extrahieren via page.cookies()                     │    ║
 * ║  │ Phase 6: Cookies speichern nach ./data/gmx-cookies.json             │    ║
 * ║  │ Phase 7: Chrome beenden & Temp-Profil aufräumen                     │    ║
 * ║  └─────────────────────────────────────────────────────────────────────┘    ║
 * ║                                                                              ║
 * ║  WICHTIG:                                                                    ║
 * ║  • Chrome MUSS mit kopiertem Profil starten (nicht Default user-data-dir!)   ║
 * ║  • Cookies sind profilgebunden verschlüsselt (macOS Keychain)                ║
 * ║  • page.cookies() funktioniert NUR wenn die Ziel-Domain geladen ist          ║
 * ║  • Das Script extrahiert ALLE Cookies, nicht nur GMX-spezifische             ║
 * ║                                                                              ║
 * ║  VORAUSSETZUNGEN:                                                            ║
 * ║  • Node.js >= 18                                                             ║
 * ║  • Google Chrome installiert (/Applications/Google Chrome.app)               ║
 * ║  • Profil-Ordner: /Users/jeremy/Library/Application Support/Google/Chrome/   ║
 * ║    - Local State (Metadaten, Profil-Liste)                                   ║
 * ║    - Profile 73 (GMX-Session, Cookies, Login-Daten)                          ║
 * ║  • Nutzer muss VOR dem Script-Lauf in GMX eingeloggt sein!                   ║
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
//  KONSTANTEN — Chrome Pfade & Einstellungen
// ═══════════════════════════════════════════════════════════════════════════════

/**
 * CHROME_BIN — Pfad zur Google Chrome Binary auf macOS.
 * MUSS die echte Chrome Binary sein, NICHT chromium oder Chrome-for-Testing.
 * puppeteer-launch würde einen eigenen Chromium mitbringen, aber diesen
 * erkennen Anti-Bot-Systeme (DataDome, PerimeterX) sofort.
 */
const CHROME_BIN = process.env.CHROME_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';

/**
 * SOURCE_USER_DATA_DIR — Der ORIGINALE Chrome user-data-dir Pfad.
 * Hier liegen Local State, Profile 73, Cookies, Login-Daten.
 *
 * ACHTUNG: Chrome verweigert CDP wenn dieser Pfad direkt als --user-data-dir
 * verwendet wird! Deshalb muss er kopiert werden.
 */
const SOURCE_USER_DATA_DIR = '/Users/jeremy/Library/Application Support/Google/Chrome';

/**
 * SOURCE_PROFILE_NAME — Name des Profil-Ordners innerhalb von user-data-dir.
 * Profile 73 ist das GMX-Profil mit aktiver Session.
 */
const SOURCE_PROFILE_NAME = 'Profile 73';

/**
 * CDP_PORT — Port für das Chrome DevTools Protocol.
 * Chrome öffnet auf diesem Port einen HTTP+WebSocket-Server.
 * puppeteer.connect() verbindet sich per WebSocket und kann dann
 * Seiten steuern, JS evaluieren, Cookies setzen, etc.
 */
const CDP_PORT = parseInt(process.env.CDP_PORT || '9222');

/**
 * COOKIES_FILE — Pfad zur JSON-Datei wo die extrahierten Cookies gespeichert werden.
 * Diese Datei wird von diesem Script erstellt und von run-gmx-cookies.js gelesen.
 * Format: Array von Cookie-Objekten { name, value, domain, path, expires, httpOnly, secure, sameSite }
 */
const COOKIES_FILE = path.join(__dirname, 'data', 'gmx-cookies.json');

// ═══════════════════════════════════════════════════════════════════════════════
//  HILFSFUNKTIONEN
// ═══════════════════════════════════════════════════════════════════════════════

/**
 * Promise-basierte sleep-Funktion
 * @param {number} ms — Millisekunden warten
 */
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));

/**
 * Holt die CDP WebSocket-URL vom laufenden Chrome.
 *
 * Chrome stellt unter http://127.0.0.1:{port}/json/version eine JSON-Response
 * mit dem Feld "webSocketDebuggerUrl" bereit.
 * Diese URL ist der Einstiegspunkt für puppeteer.connect().
 *
 * Format: ws://127.0.0.1:9222/devtools/browser/{uuid}
 *
 * @param {number} port — Der CDP-Debug-Port (default: 9222)
 * @returns {Promise<string>} WebSocket-URL
 */
function getWebSocketUrl(port) {
  return new Promise((resolve, reject) => {
    const req = http.get(`http://127.0.0.1:${port}/json/version`, res => {
      let body = '';
      res.on('data', chunk => body += chunk);
      res.on('end', () => {
        try {
          const json = JSON.parse(body);
          if (json.webSocketDebuggerUrl) {
            resolve(json.webSocketDebuggerUrl);
          } else {
            reject(new Error(`Kein webSocketDebuggerUrl in CDP-Response: ${body.substring(0, 200)}`));
          }
        } catch (e) {
          reject(new Error(`Invalid JSON from CDP: ${body.substring(0, 200)}`));
        }
      });
    });
    req.on('error', reject);
    // Timeout: Wenn Chrome nicht antwortet → Abbruch nach 5 Sekunden
    req.setTimeout(5000, () => {
      req.destroy();
      reject(new Error('CDP request timeout (5s)'));
    });
  });
}

/**
 * Wartet in einer Retry-Loop bis der CDP-Port antwortet.
 *
 * Chrome braucht nach dem Start 2-5 Sekunden bis der Debug-Port bereit ist.
 * Diese Funktion pollt den Port bis zu maxRetries mal mit 1 Sekunde Abstand.
 *
 * @param {number} port — CDP-Port
 * @param {number} maxRetries — Maximale Anzahl Versuche (default: 15)
 * @returns {Promise<string>} WebSocket-URL
 */
async function waitForCdp(port, maxRetries = 15) {
  for (let i = 0; i < maxRetries; i++) {
    try {
      return await getWebSocketUrl(port);
    } catch (e) {
      // Erster und letzter Versuch werden geloggt
      if (i === 0) console.log(`   ⏳ Warte auf CDP (Port ${port})...`);
      if (i === maxRetries - 1) throw new Error(`CDP nicht erreichbar nach ${maxRetries}s auf Port ${port}`);
      await sleep(1000);
    }
  }
}

/**
 * Kopiert das Chrome-Profil in ein temporäres Verzeichnis.
 *
 * WARUM KOPIEREN?
 * Chrome verweigert CDP wenn --user-data-dir auf den Standard-Pfad zeigt.
 * Aber: Nur Profil-Subfolder kopieren (ohne Local State) führt dazu dass
 * Chrome ein NEUES leeres Profil erstellt → alle Sessions weg!
 *
 * WAS WIRD KOPIERT?
 * 1. Local State — Metadaten-Datei mit Profil-Liste, Einstellungen, etc.
 *    Ohne diese Datei weiß Chrome nicht welche Profile existieren.
 * 2. Profile 73 — Das eigentliche Browser-Profil mit:
 *    - Cookies (GMX-Session, auth.gmx.net Tokens)
 *    - Local Storage (GMX-Einstellungen)
 *    - Login Data (gespeicherte Passwörter)
 *    - Preferences (Chrome-Einstellungen)
 *    - History, Bookmarks, etc.
 *
 * @returns {string} Pfad zum kopierten Profil-Verzeichnis
 */
function copyChromeProfile() {
  const tempDir = `/tmp/sinator-chrome-extract-${Date.now()}`;
  const sourceProfile = path.join(SOURCE_USER_DATA_DIR, SOURCE_PROFILE_NAME);

  console.log(`📋 Kopiere Chrome-Profil: ${sourceProfile} → ${tempDir}`);

  // Verzeichnis erstellen
  fs.mkdirSync(tempDir, { recursive: true });

  // Local State kopieren (Metadaten, Profil-Liste)
  const localStateSrc = path.join(SOURCE_USER_DATA_DIR, 'Local State');
  const localStateDst = path.join(tempDir, 'Local State');
  if (fs.existsSync(localStateSrc)) {
    fs.copyFileSync(localStateSrc, localStateDst);
    console.log('   ✅ Local State kopiert');
  } else {
    console.log('   ⚠️  Local State nicht gefunden — Chrome erstellt möglicherweise neues Profil');
  }

  // Profil-Ordner kopieren (Cookies, Sessions, Login-Daten)
  if (fs.existsSync(sourceProfile)) {
    execSync(`cp -R "${sourceProfile}" "${tempDir}"`, { stdio: 'pipe' });
    console.log(`   ✅ Profile ${SOURCE_PROFILE_NAME} kopiert`);
  } else {
    throw new Error(`Profil-Ordner nicht gefunden: ${sourceProfile}`);
  }

  // First Run Datei erstellen (verhindert Chrome Welcome-Dialog)
  fs.writeFileSync(path.join(tempDir, 'First Run'), '');

  console.log(`   📁 Temp-Profil: ${tempDir}\n`);
  return tempDir;
}

/**
 * Räumt das temporäre Profil-Verzeichnis auf.
 * Wird nach Chrome-Beendigung aufgerufen.
 *
 * @param {string} tempDir — Pfad zum kopierten Profil
 */
function cleanupTempProfile(tempDir) {
  if (tempDir && tempDir.startsWith('/tmp/sinator-chrome-extract-')) {
    try {
      execSync(`rm -rf "${tempDir}"`, { stdio: 'pipe' });
      console.log(`🗑️  Temp-Profil aufgeräumt: ${tempDir}`);
    } catch (e) {
      console.log(`⚠️  Fehler beim Aufräumen: ${e.message}`);
    }
  }
}

/**
 * Speichert die extrahierten Cookies in eine JSON-Datei.
 *
 * @param {Object[]} cookies — Array von Cookie-Objekten
 * @param {string} filePath — Zielpfad für die JSON-Datei
 */
function saveCookies(cookies, filePath) {
  // Verzeichnis erstellen falls nicht existent
  const dir = path.dirname(filePath);
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }

  // Cookies serialisieren (some fields may be undefined)
  const serializable = cookies.map(c => ({
    name: c.name,
    value: c.value,
    domain: c.domain,
    path: c.path,
    expires: c.expires || -1,
    httpOnly: c.httpOnly || false,
    secure: c.secure || false,
    sameSite: c.sameSite || 'None',
  }));

  fs.writeFileSync(filePath, JSON.stringify(serializable, null, 2), 'utf-8');
  console.log(`💾 ${serializable.length} Cookies gespeichert nach: ${filePath}`);
}

// ═══════════════════════════════════════════════════════════════════════════════
//  MAIN — COOKIE EXTRACTION FLOW
// ═══════════════════════════════════════════════════════════════════════════════
(async () => {
  console.log('\n╔══════════════════════════════════════════════════════════════╗');
  console.log('║          SINATOR — GMX Cookie Extraction Tool               ║');
  console.log('╚══════════════════════════════════════════════════════════════╝\n');

  let tempDir = null;
  let chromeProc = null;
  let browser = null;

  try {
    // ── PHASE 0 | PROFIL KOPIEREN ──────────────────────────────────────
    console.log('📦 Phase 0: Chrome-Profil kopieren');
    tempDir = copyChromeProfile();

    // ── PHASE 1 | CHROME STARTEN ───────────────────────────────────────
    console.log('🚀 Phase 1: Chrome mit kopiertem Profil starten');
    console.log(`   user-data-dir: ${tempDir}`);
    console.log(`   profile:       ${SOURCE_PROFILE_NAME}`);
    console.log(`   CDP-Port:      ${CDP_PORT}`);

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
    ], {
      stdio: 'ignore', // Chrome stdout/stderr nicht in unsere Konsole
    });

    // ── PHASE 2 | CDP VERBINDUNG ───────────────────────────────────────
    console.log('\n🔗 Phase 2: Auf CDP warten...');
    const wsUrl = await waitForCdp(CDP_PORT);
    console.log(`   ✅ CDP verbunden: ${wsUrl.substring(0, 60)}...`);

    // ── PHASE 3 | PUPPETEER.CONNECT() ──────────────────────────────────
    console.log('\n🌐 Phase 3: puppeteer.connect()');
    browser = await puppeteer.connect({ browserWSEndpoint: wsUrl });
    const pages = await browser.pages();
    const page = pages[0] || await browser.newPage();
    console.log('   ✅ Puppeteer verbunden');

    // ── PHASE 4 | GMX SESSION PRÜFEN ───────────────────────────────────
    console.log('\n🔍 Phase 4: GMX Session prüfen');
    console.log('   Öffne GMX Mail...');

    await page.goto('https://navigator.gmx.net/mail', {
      waitUntil: 'domcontentloaded',
      timeout: 20000,
    });
    await sleep(3000);

    const currentUrl = page.url();
    console.log(`   📍 Aktuelle URL: ${currentUrl}`);

    // Prüfen ob wir eingeloggt sind
    const isLoggedIn = currentUrl.includes('navigator.gmx.net') ||
                       currentUrl.includes('bap.navigator') ||
                       !currentUrl.includes('login') && !currentUrl.includes('auth.gmx');

    if (!isLoggedIn) {
      console.log('\n❌ NICHT eingeloggt!');
      console.log('   Bitte zuerst manuell in GMX einloggen:');
      console.log('   1. Chrome mit kopiertem Profil öffnen');
      console.log('   2. Zu https://navigator.gmx.net/mail navigieren');
      console.log('   3. Einloggen mit: zukunftsorientierte.energie@gmail.com');
      console.log('   4. Dieses Script erneut ausführen\n');
      process.exit(1);
    }

    console.log('   ✅ GMX-Session aktiv!\n');

    // ── PHASE 5 | COOKIES EXTRAHIEREN ──────────────────────────────────
    console.log('🍪 Phase 5: Cookies extrahieren');
    const allCookies = await page.cookies();
    console.log(`   📊 ${allCookies.length} Cookies gefunden`);

    // GMX-spezifische Cookies filtern und anzeigen
    const gmxCookies = allCookies.filter(c =>
      c.domain.includes('gmx') || c.domain.includes('mail.gmx') || c.name.includes('GMX')
    );
    console.log(`   📧 ${gmxCookies.length} GMX-spezifische Cookies:`);
    gmxCookies.forEach(c => {
      console.log(`      • ${c.name} (domain: ${c.domain}, expires: ${c.expires > 0 ? new Date(c.expires * 1000).toISOString() : 'Session'})`);
    });

    // ── PHASE 6 | COOKIES SPEICHERN ────────────────────────────────────
    console.log('\n💾 Phase 6: Cookies speichern');
    saveCookies(allCookies, COOKIES_FILE);

    // ── PHASE 7 | CLEANUP ──────────────────────────────────────────────
    console.log('\n🏁 Phase 7: Cleanup');
    await browser.disconnect();
    chromeProc.kill('SIGTERM');
    cleanupTempProfile(tempDir);

    console.log('\n✅ Cookie-Extraction abgeschlossen!');
    console.log(`   📁 Cookies gespeichert in: ${COOKIES_FILE}`);
    console.log(`   📊 Total: ${allCookies.length} Cookies (${gmxCookies.length} GMX-spezifisch)`);
    console.log('   🚀 Jetzt kann run-gmx-cookies.js verwendet werden!\n');

  } catch (err) {
    console.error('\n💥 FEHLER bei der Cookie-Extraction:', err.message);

    // Cleanup im Fehlerfall
    if (browser) {
      try { await browser.disconnect(); } catch {}
    }
    if (chromeProc) {
      try { chromeProc.kill('SIGTERM'); } catch {}
    }
    if (tempDir) {
      cleanupTempProfile(tempDir);
    }

    process.exit(1);
  }
})();

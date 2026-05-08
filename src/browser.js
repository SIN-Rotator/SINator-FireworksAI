/**
 * ╔══════════════════════════════════════════════════════════════════════════════╗
 * ║                     SINATOR-ROTATOR — Browser Engine                        ║
 * ╠══════════════════════════════════════════════════════════════════════════════╣
 * ║                                                                              ║
 * ║  ZWECK:                                                                      ║
 * ║  Startet Chrome als Subprocess mit CDP-Debugging und verbindet puppeteer     ║
 * ║  über WebSocket. Das Profil wird VOR dem Start kopiert (Local State +        ║
 * ║  Profile 73), damit Chrome CDP akzeptiert UND die GMX-Session erhalten       ║
 * ║  bleibt.                                                                       ║
 * ║                                                                              ║
 * ║  WARUM NICHT puppeteer.launch()?                                              ║
 * ║  puppeteer.launch() setzt automatisch --enable-automation Flag.              ║
 * ║  Dieses Flag wird von Anti-Bot-Systemen (DataDome, Akamai, Cloudflare)       ║
 * ║  sofort erkannt → GMX zeigt CAPTCHA nach Email-Eingabe.                      ║
 * ║  Lösung: Chrome DIREKT via child_process.spawn() starten.                    ║
 * ║  puppeteer.connect() verbindet sich dann zum laufenden CDP-Endpoint.         ║
 * ║                                                                              ║
 * ║  WARUM PROFIL KOPIEREN?                                                      ║
 * ║  Chrome verweigert --remote-debugging-port wenn --user-data-dir auf den      ║
 * ║  Standard-Pfad zeigt (~/Library/Application Support/Google/Chrome).          ║
 * ║  Fehler: "DevTools remote debugging requires a non-default data directory"   ║
 * ║  Aber: Nur Profil-Subfolder kopieren (ohne Local State) führt dazu dass      ║
 * ║  Chrome ein NEUES leeres Profil erstellt → alle Sessions weg!                ║
 * ║  Lösung: GESAMTES user-data-dir kopieren (Local State + Profile 73).         ║
 * ║                                                                              ║
 * ║  WARUM KEINE COOKIE-INJECTION?                                                ║
 * ║  GMX-Cookies sind profilgebunden verschlüsselt (macOS Keychain).             ║
 * ║  page.setCookie() oder CDP Network.setCookies in ein FRISCHES Profil         ║
 * ║  funktioniert nicht — Chrome kann die Cookies nicht entschlüsseln.           ║
 * ║  Lösung: Profil kopieren → Chrome übernimmt kopierte Cookies automatisch.    ║
 * ║                                                                              ║
 * ║  ABLAUF:                                                                      ║
 * ║  ┌─────────────────────────────────────────────────────────────────────┐    ║
 * ║  │ Phase 0: Profil kopieren (Local State + Profile 73 → /tmp)         │    ║
 * ║  │ Phase 1: Chrome via spawn() mit kopiertem user-data-dir starten     │    ║
 * ║  │ Phase 2: Auf CDP-Bereitschaft warten (Retry-Loop, max 15s)         │    ║
 * ║  │ Phase 3: puppeteer.connect() zum WebSocket-Endpoint                │    ║
 * ║  │ Phase 4: Stealth-JS injecten (navigator.webdriver, plugins, etc.)  │    ║
 * ║  │ Phase 5: Page zurückgeben → bereit für GMX-Automation               │    ║
 * ║  └─────────────────────────────────────────────────────────────────────┘    ║
 * ║                                                                              ║
 * ║  VORAUSSETZUNGEN:                                                            ║
 * ║  • Node.js >= 18                                                             ║
 * ║  • Google Chrome installiert (/Applications/Google Chrome.app)               ║
 * ║  • Profil-Ordner: /Users/jeremy/Library/Application Support/Google/Chrome/   ║
 * ║    - Local State (Metadaten, Profil-Liste)                                   ║
 * ║    - Profile 73 (GMX-Session, Cookies, Login-Daten)                          ║
 * ║                                                                              ║
 * ╚══════════════════════════════════════════════════════════════════════════════╝
 */
const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');
const http = require('http');
const puppeteer = require('puppeteer');
const logger = require('./logger');

// ═══════════════════════════════════════════════════════════════════════════════
//  KONSTANTEN — Chrome Pfade & Einstellungen
// ═══════════════════════════════════════════════════════════════════════════════

/**
 * CHROME_BIN — Pfad zur Google Chrome Binary auf macOS.
 * MUSS die echte Chrome Binary sein, NICHT chromium oder Chrome-for-Testing.
 * puppeteer-launch würde einen eigenen Chromium mitbringen, aber diesen
 * erkennen Anti-Bot-Systeme (DataDome, PerimeterX) sofort.
 *
 * Kann via .env (CHROME_PATH) überschrieben werden.
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
 *
 * Default: 9222 (Standard Chrome Debugging-Port)
 * Kann via .env (CDP_PORT) überschrieben werden.
 */
const CDP_PORT = parseInt(process.env.CDP_PORT || '9222');

/**
 * STEALTH_FLAGS — Chrome-Flags die Bot-Detection umgehen.
 *
 * Jeder einzelne Flag verhindert ein bestimmtes Detection-Signal:
 *   --disable-blink-features=AutomationControlled
 *     → Entfernt navigator.webdriver=true (wird zusätzlich via JS überschrieben)
 *   --disable-features=IsolateOrigins,site-per-process,...
 *     → Deaktiviert Chrome-interne Features die CDP-Automation verraten
 *   --disable-sync, --disable-background-networking
 *     → Verhindert Netzwerk-Traffic der Bot-typisch ist
 *   --password-store=basic, --use-mock-keychain
 *     → Kein macOS Keychain-Zugriff (wir loggen uns selbst ein)
 *   --noerrdialogs, --deny-permission-prompts
 *     → Blockiert Dialoge die den Flow unterbrechen würden
 *
 * WICHTIG: --enable-automation wird NICHT gesetzt (im Gegensatz zu puppeteer.launch)!
 */
const STEALTH_FLAGS = [
  '--disable-blink-features=AutomationControlled',
  '--disable-infobars',
  '--disable-features=IsolateOrigins,site-per-process,Translate,AcceptCHFrame,MediaRouter,OptimizationHints,ChromeWhatsNewUI',
  '--no-first-run',
  '--no-default-browser-check',
  '--disable-dev-shm-usage',
  '--disable-gpu',
  '--disable-extensions',
  '--disable-component-update',
  '--disable-background-networking',
  '--disable-sync',
  '--disable-domain-reliability',
  '--disable-client-side-phishing-detection',
  '--disable-renderer-backgrounding',
  '--disable-backgrounding-occluded-windows',
  '--disable-ipc-flooding-protection',
  '--disable-search-engine-choice-screen',
  '--disable-prompt-on-repost',
  '--disable-hang-monitor',
  '--disable-breakpad',
  '--disable-popup-blocking',
  '--enable-features=NetworkService,NetworkServiceInProcess',
  '--metrics-recording-only',
  '--password-store=basic',
  '--use-mock-keychain',
  '--noerrdialogs',
  '--deny-permission-prompts',
  '--lang=de-DE,en-US',
];

/**
 * STEALTH_JS — JavaScript das via page.evaluateOnNewDocument() injectet wird.
 * Überschreibt Bot-Detection-Vektoren BEVOR die Seite lädt.
 *
 * - navigator.webdriver → undefined (statt true)
 * - navigator.plugins → [1,2,3,4,5] (statt leer)
 * - navigator.languages → ['de-DE','de','en-US','en'] (deutsche UI)
 * - window.chrome.runtime → existent (statt undefined)
 * - permissions.query → patched für notifications
 */
const STEALTH_JS = `
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
Object.defineProperty(navigator, 'languages', { get: () => ['de-DE', 'de', 'en-US', 'en'] });
window.chrome = { runtime: {}, loadTimes: function() {}, csi: function() {}, app: {} };
(() => {
  const oq = window.navigator.permissions.query;
  window.navigator.permissions.query = (p) => p.name === 'notifications'
    ? Promise.resolve({ state: Notification.permission })
    : oq(p);
})();
`;

// ═══════════════════════════════════════════════════════════════════════════════
//  PROFIL-KOPIERUNG
// ═══════════════════════════════════════════════════════════════════════════════

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
  const tempDir = `/tmp/sinator-chrome-${Date.now()}`;
  const sourceProfile = path.join(SOURCE_USER_DATA_DIR, SOURCE_PROFILE_NAME);

  logger.info(`Kopiere Chrome-Profil: ${sourceProfile} → ${tempDir}`);

  // Verzeichnis erstellen
  fs.mkdirSync(tempDir, { recursive: true });

  // Local State kopieren (Metadaten, Profil-Liste)
  const localStateSrc = path.join(SOURCE_USER_DATA_DIR, 'Local State');
  const localStateDst = path.join(tempDir, 'Local State');
  if (fs.existsSync(localStateSrc)) {
    fs.copyFileSync(localStateSrc, localStateDst);
    logger.info('Local State kopiert');
  } else {
    logger.warn('Local State nicht gefunden — Chrome erstellt möglicherweise neues Profil');
  }

  // Profil-Ordner kopieren (Cookies, Sessions, Login-Daten)
  if (fs.existsSync(sourceProfile)) {
    execSync(`cp -R "${sourceProfile}" "${tempDir}"`, { stdio: 'pipe' });
    logger.info(`Profile ${SOURCE_PROFILE_NAME} kopiert`);
  } else {
    throw new Error(`Profil-Ordner nicht gefunden: ${sourceProfile}`);
  }

  // First Run Datei erstellen (verhindert Chrome Welcome-Dialog)
  fs.writeFileSync(path.join(tempDir, 'First Run'), '');

  logger.info(`Profil kopiert nach: ${tempDir}`);
  return tempDir;
}

/**
 * Räumt das temporäre Profil-Verzeichnis auf.
 * Wird nach Chrome-Beendigung aufgerufen.
 *
 * @param {string} tempDir — Pfad zum kopierten Profil
 */
function cleanupTempProfile(tempDir) {
  if (tempDir && tempDir.startsWith('/tmp/sinator-chrome-')) {
    try {
      execSync(`rm -rf "${tempDir}"`, { stdio: 'pipe' });
      logger.info(`Temp-Profil aufgeräumt: ${tempDir}`);
    } catch (e) {
      logger.warn(`Fehler beim Aufräumen: ${e.message}`);
    }
  }
}

// ═══════════════════════════════════════════════════════════════════════════════
//  CDP VERBINDUNG
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
      // Kein Log hier — das Polling ist normal und würde das Log zuspammen
      // Erster und letzter Versuch werden geloggt
      if (i === 0) logger.debug(`Warte auf CDP (Port ${port})...`);
      if (i === maxRetries - 1) logger.error(`CDP nicht erreichbar nach ${maxRetries}s auf Port ${port}`);
      await sleep(1000);
    }
  }
  throw new Error(`CDP nicht erreichbar nach ${maxRetries} Sekunden auf Port ${port}`);
}

// ═══════════════════════════════════════════════════════════════════════════════
//  CHROME START & VERBINDUNG
// ═══════════════════════════════════════════════════════════════════════════════

/**
 * Startet Chrome als Subprocess mit kopiertem Profil und CDP-Debugging.
 *
 * ABLAUF:
 * 1. Profil kopieren (Local State + Profile 73 → /tmp/sinator-chrome-{timestamp})
 * 2. Chrome starten via spawn() mit --user-data-dir=/tmp/... --profile-directory="Profile 73"
 * 3. Auf CDP-Bereitschaft warten (Retry-Loop, max 15s)
 * 4. puppeteer.connect() zum WebSocket-Endpoint
 * 5. Stealth-JS injecten (navigator.webdriver, plugins, etc.)
 * 6. { browser, page, tempDir } zurückgeben
 *
 * FLAGS-ERKLÄRUNG:
 *   --user-data-dir=/tmp/...         → Nicht-Standard-Pfad (CDP erlaubt)
 *   --profile-directory="Profile 73" → Spezifisches Profil verwenden
 *   --remote-debugging-port=9222     → CDP-Endpoint öffnen
 *   --remote-allow-origins=*          → WebSocket von allen Origins erlauben
 *   --no-first-run                    → Kein Chrome Welcome-Dialog
 *   --no-default-browser-check       → Kein "Standardbrowser?" Dialog
 *   --window-size=1280,800           → Feste Fenstergröße (kein Bot-Signal)
 *   --lang=de-DE                     → Deutsche UI (GMX erwartet das)
 *
 * @param {Object} options — Optionale Konfiguration
 * @param {boolean} options.headless — Headless-Modus (default: false)
 * @param {number} options.cdpPort — CDP-Port (default: 9222)
 * @returns {Promise<{browser: Browser, page: Page, tempDir: string}>}
 */
async function startChrome(options = {}) {
  const { headless = false, cdpPort = CDP_PORT } = options;

  // Phase 0: Profil kopieren
  logger.info('Phase 0: Chrome-Profil kopieren');
  const tempDir = copyChromeProfile();

  // Phase 1: Chrome starten
  logger.info(`Phase 1: Chrome starten (CDP-Port: ${cdpPort})`);
  logger.info(`   user-data-dir: ${tempDir}`);
  logger.info(`   profile:       ${SOURCE_PROFILE_NAME}`);
  logger.info(`   Chrome:        ${CHROME_BIN}`);

  const chromeArgs = [
    `--user-data-dir=${tempDir}`,
    `--profile-directory=${SOURCE_PROFILE_NAME}`,
    `--remote-debugging-port=${cdpPort}`,
    '--remote-allow-origins=*',
    '--no-first-run',
    '--no-default-browser-check',
    '--window-size=1280,800',
    '--lang=de-DE',
    ...STEALTH_FLAGS,
    'about:blank',
  ];

  if (headless) {
    chromeArgs.push('--headless=new');
  }

  const chromeProc = spawn(CHROME_BIN, chromeArgs, {
    stdio: 'ignore', // Chrome stdout/stderr nicht in unsere Konsole
    detached: false, // Nicht vom Node-Prozess entkoppeln
  });

  // Phase 2: Auf CDP warten
  logger.info('Phase 2: Auf CDP warten...');
  const wsUrl = await waitForCdp(cdpPort);
  logger.info(`CDP verbunden: ${wsUrl.substring(0, 60)}...`);

  // Phase 3: puppeteer.connect()
  logger.info('Phase 3: puppeteer.connect()');
  const browser = await puppeteer.connect({ browserWSEndpoint: wsUrl });

  // Phase 4: Page holen & Stealth injecten
  const pages = await browser.pages();
  const page = pages[0] || await browser.newPage();

  await page.evaluateOnNewDocument(STEALTH_JS);
  await page.setUserAgent(
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 ' +
    '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
  );
  await page.setExtraHTTPHeaders({
    'Accept-Language': 'de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7',
  });

  logger.info('Chrome bereit mit GMX-Session aus kopiertem Profil');

  return { browser, page, tempDir, chromeProc };
}

/**
 * Beendet Chrome und räumt das temporäre Profil auf.
 *
 * @param {Object} params — Rückgabewerte von startChrome()
 * @param {Browser} params.browser — Puppeteer Browser-Instanz
 * @param {ChildProcess} params.chromeProc — Chrome Subprocess
 * @param {string} params.tempDir — Pfad zum kopierten Profil
 */
async function stopChrome({ browser, chromeProc, tempDir }) {
  logger.info('Chrome beenden & Temp-Profil aufräumen');

  try {
    if (browser) {
      await browser.disconnect();
      logger.info('puppeteer.disconnect() erfolgreich');
    }
  } catch (e) {
    logger.warn(`browser.disconnect() Fehler: ${e.message}`);
  }

  try {
    if (chromeProc) {
      chromeProc.kill('SIGTERM');
      logger.info('Chrome-Prozess beendet (SIGTERM)');
    }
  } catch (e) {
    logger.warn(`chromeProc.kill() Fehler: ${e.message}`);
  }

  cleanupTempProfile(tempDir);
}

// ═══════════════════════════════════════════════════════════════════════════════
//  HILFSFUNKTIONEN
// ═══════════════════════════════════════════════════════════════════════════════

/**
 * Generiert eine zufällige Wartezeit (human-like delay).
 *
 * @param {number} min — Minimum in ms (default: 1500)
 * @param {number} max — Maximum in ms (default: 3500)
 */
async function randomDelay(min = null, max = null) {
  const minMs = min || parseInt(process.env.DELAY_MIN) || 1500;
  const maxMs = max || parseInt(process.env.DELAY_MAX) || 3500;
  const delay = Math.floor(Math.random() * (maxMs - minMs + 1)) + minMs;
  logger.debug(`Warte ${delay}ms (human-like delay)`);
  await sleep(delay);
}

/**
 * Tippt Text Buchstabe für Buchstabe mit zufälligem Delay.
 * Simuliert menschliches Tippverhalten (25-80ms pro Buchstabe).
 *
 * @param {Page} page — Puppeteer Page
 * @param {string} selector — CSS-Selector des Input-Felds
 * @param {string} text — Der zu tippende Text
 */
async function humanType(page, selector, text) {
  await page.click(selector);
  await sleep(300); // Kurze Pause nach Klick

  // Input-Feld leeren
  await page.evaluate((sel) => {
    const el = document.querySelector(sel);
    if (el) el.value = '';
  }, selector);

  // Buchstabe für Buchstabe mit zufälligem Delay
  for (const char of text) {
    await page.keyboard.type(char, {
      delay: Math.floor(Math.random() * 55) + 25, // 25-80ms
    });
  }
  logger.debug(`Human-Type: "${text}" in ${selector}`);
}

/**
 * Findet und klickt ein Element das einen bestimmten Text enthält.
 *
 * Puppeteer hat kein :has-text() (Playwright-only).
 * Stattdessen: page.evaluate() durchsucht den DOM nach Text-Match,
 * returned das Element, und klickt es.
 *
 * WICHTIG: Verwende EXAKTE Text-Matches für kritische Buttons
 * (z.B. "Hinzufügen" statt nur "A" — sonst matcht "Anmelden"!)
 *
 * @param {Page} page — Puppeteer Page
 * @param {string} text — Der gesuchte Text (case-sensitive contains)
 * @param {string} [tag='*'] — Optional einschränken auf Tag (button, a, span...)
 * @returns {boolean} true wenn Element gefunden und geklickt wurde
 */
async function clickByText(page, text, tag = '*') {
  try {
    const clicked = await page.evaluate(({ text, tag }) => {
      const all = document.querySelectorAll(tag);
      for (const el of all) {
        if (el.textContent && el.textContent.includes(text)) {
          // Nur sichtbare/clickbare Elemente
          const rect = el.getBoundingClientRect();
          if (rect.width > 0 && rect.height > 0) {
            el.scrollIntoView({ block: 'center', behavior: 'instant' });
            el.click();
            return true;
          }
        }
      }
      return false;
    }, { text, tag });
    return clicked;
  } catch (e) {
    logger.warn(`clickByText("${text}") Fehler: ${e.message}`);
    return false;
  }
}

/**
 * Findet ein Element mit EXAKTEM Text-Match.
 *
 * Im Gegensatz zu clickByText() muss der Text GENAU übereinstimmen
 * (nicht nur contains). Verhindert false positives wie "A" → "Anmelden".
 *
 * @param {Page} page — Puppeteer Page
 * @param {string} exactText — Der EXAKT gesuchte Text
 * @param {string} [tag='button'] — Tag-Filter (default: button)
 * @returns {boolean} true wenn Element gefunden und geklickt wurde
 */
async function clickByExactText(page, exactText, tag = 'button') {
  try {
    const clicked = await page.evaluate(({ exactText, tag }) => {
      const all = document.querySelectorAll(tag);
      for (const el of all) {
        const txt = (el.textContent || '').trim();
        if (txt === exactText) {
          const rect = el.getBoundingClientRect();
          if (rect.width > 0 && rect.height > 0) {
            el.scrollIntoView({ block: 'center', behavior: 'instant' });
            el.click();
            return true;
          }
        }
      }
      return false;
    }, { exactText, tag });
    return clicked;
  } catch (e) {
    logger.warn(`clickByExactText("${exactText}") Fehler: ${e.message}`);
    return false;
  }
}

/**
 * Wartet auf ein DOM-Element (statt auf Navigation).
 *
 * auth.gmx.net ist eine SPA — es gibt keine Page-Navigation nach Login.
 * Stattdessen muss auf DOM-Elemente gewartet werden die nach dem
 * JavaScript-Übergang erscheinen.
 *
 * @param {Page} page — Puppeteer Page
 * @param {string} selector — CSS-Selector des Elements
 * @param {number} timeout — Timeout in ms (default: 10000)
 * @returns {Promise<ElementHandle>} Das gefundene Element
 */
async function waitForElement(page, selector, timeout = 10000) {
  logger.debug(`Warte auf Element: ${selector} (timeout: ${timeout}ms)`);
  return await page.waitForSelector(selector, { timeout });
}

// ═══════════════════════════════════════════════════════════════════════════════
//  EXPORTS
// ═══════════════════════════════════════════════════════════════════════════════

module.exports = {
  startChrome,
  stopChrome,
  randomDelay,
  humanType,
  clickByText,
  clickByExactText,
  waitForElement,
  copyChromeProfile,
  cleanupTempProfile,
  getWebSocketUrl,
  waitForCdp,
};

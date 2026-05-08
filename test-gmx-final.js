#!/usr/bin/env node
require('dotenv').config();
const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');
const puppeteer = require('puppeteer');
const http = require('http');
require('./src/logger');const l = console;

const PORT = 9222;
const CHROME = process.env.CHROME_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const USER = process.env.GMX_EMAIL;
const PASS = process.env.GMX_PASSWORD;
const { generateAliasName } = require('./src/nameGenerator');

function dly(min, max) { return Math.floor(Math.random() * (max - min + 1)) + min; }
const S = ms => new Promise(r => setTimeout(r, ms));

async function ws(port) {
  return new Promise((resolve, reject) => {
    http.get(`http://127.0.0.1:${port}/json/version`, res => {
      let b = ''; res.on('data', c => b += c);
      res.on('end', () => resolve(JSON.parse(b).webSocketDebuggerUrl));
    }).on('error', reject);
  });
}

(async () => {
  const alias = generateAliasName();
  l.log(`👤 ${alias}@gmx.de`);

  // Symlink original profile
  const dir = `/tmp/sinator-${Date.now()}`;
  fs.mkdirSync(dir);
  fs.symlinkSync(
    '/Users/jeremy/Library/Application Support/Google/Chrome/Profile 73',
    path.join(dir, 'Profile 73')
  );
  cpIfExists('/Users/jeremy/Library/Application Support/Google/Chrome/Local State', dir);
  cpIfExists('/Users/jeremy/Library/Application Support/Google/Chrome/Last Version', dir);
  fs.writeFileSync(path.join(dir, 'First Run'), '');
  
  spawn(CHROME, [
    `--user-data-dir=${dir}`, `--remote-debugging-port=${PORT}`,
    '--remote-allow-origins=*', '--no-first-run', '--no-default-browser-check',
    '--profile-directory=Profile 73', '--window-size=1280,800',
    'https://www.gmx.net/'
  ], { stdio: 'ignore' });
  
  for (let i = 0; i < 15; i++) {
    try { await ws(PORT); break; } catch { await S(1000); }
  }
  const w = await ws(PORT);
  l.log('CDP connected');
  
  const b = await puppeteer.connect({ browserWSEndpoint: w });
  const p = (await b.pages())[0];
  
  // ── Consent ─────────────────
  if (p.url().includes('consent')) {
    l.log('🍪 Consent');
    await p.click('button');  // Erstes bestes = Alle akzeptieren
    await S(4000);
    try { await p.waitForNavigation({ timeout: 8000 }); } catch {}
  }
  l.log(`📍 ${p.url()}`);

  // ── Login klicken ──────────
  l.log('🔍 Suche Login...');
  const loginEl = await p.evaluateHandle(() => {
    for (const el of document.querySelectorAll('a, button, span')) {
      if ((el.textContent||'').trim() === 'Login') return el;
    }
    return null;
  });
  if (loginEl.asElement()) {
    await loginEl.asElement().then(e => e.click());
    l.log('✅ Login geklickt');
  }
  await S(4000);
  try { await p.waitForNavigation({ timeout: 10000 }); } catch {}
  l.log(`📍 ${p.url()}`);
  
  // ── 403 check ──────────────
  if (p.url().includes('403') || (await p.evaluate(() => document.body.innerText)).includes('403')) {
    l.log('❌ 403 - GMX blocked');
    await b.disconnect();
    process.exit(1);
  }

  // ── Credentials ────────────
  l.log('📧 Type email...');
  const ei = await p.$('input[name="username"], input[type="email"], #email, input[name="email"]');
  if (ei) {
    await ei.click(); await S(300);
    for (const c of USER) await p.keyboard.type(c, { delay: dly(30, 80) });
    l.log('✅ Email done');
  } else { l.log('❌ No email field'); await b.disconnect(); process.exit(1); }
  await S(dly(500, 1000));

  l.log('🔐 Type password...');
  const pi = await p.$('input[type="password"], input[name="password"]');
  if (pi) {
    await pi.click(); await S(300);
    for (const c of PASS) await p.keyboard.type(c, { delay: dly(30, 70) });
    l.log('✅ Password done');
  } else { l.log('❌ No password field'); await b.disconnect(); process.exit(1); }
  await S(500);
  
  l.log('⏎ Submit...');
  await p.keyboard.press('Enter');
  await S(5000);
  try { await p.waitForNavigation({ timeout: 15000 }); } catch {}
  l.log(`📍 ${p.url()}`);

  // Post-login consent
  if (p.url().includes('consent')) {
    await p.click('button');
    await S(4000);
    try { await p.waitForNavigation({ timeout: 8000 }); } catch {}
    l.log(`📍 ${p.url()}`);
  }

  if (p.url().includes('navigator.gmx.net')) {
    l.log('✅✅✅ GMX LOGIN OK');
  } else {
    l.log('⚠️ ' + p.url());
  }

  // ── Alias Prozess ──────────
  l.log('⚙️  Email addresses...');
  await p.goto('https://navigator.gmx.net/mail_settings/email_addresses', { waitUntil: 'domcontentloaded', timeout: 15000 });
  await S(4000);
  l.log(`📍 ${p.url()}`);

  l.log('🗑️  Delete alias...');
  await p.evaluate(() => {
    for (const el of document.querySelectorAll('button, a')) {
      if (el.textContent.includes('Löschen')) { el.click(); return; }
    }
  });
  await S(2000);
  await p.evaluate(() => {
    for (const el of document.querySelectorAll('button')) {
      if (el.textContent.includes('Ja') || el.textContent.includes('Bestätigen')) { el.click(); return; }
    }
  });
  await S(3000);

  l.log(`➕ ${alias}@gmx.de`);
  await p.evaluate((n) => {
    for (const el of document.querySelectorAll('button, a')) {
      if (el.textContent.includes('Hinzufügen') || el.textContent.includes('Neu')) { el.click(); return; }
    }
  }, alias);
  await S(3000);

  const inp = await p.$('input[type="text"]');
  if (inp) {
    await inp.click(); await S(300);
    for (const c of alias) await p.keyboard.type(c, { delay: dly(25, 60) });
    l.log(`✅ Typed: ${alias}`);
  }
  await S(500);

  await p.evaluate(() => {
    for (const el of document.querySelectorAll('button')) {
      if (el.textContent.includes('Speichern') || el.textContent.includes('Erstellen') || el.textContent.includes('OK')) { el.click(); return; }
    }
  });
  await S(5000);

  const res = await p.evaluate(() => document.body.innerText.substring(0, 400));
  l.log(res.includes(alias) ? `✅✅✅ ALIAS OK: ${alias}@gmx.de` : '⚠️ Check manually');
  l.log(`📄 ${res.substring(0, 250)}`);
  
  l.log('⏸️ 10s...');
  await S(10000);
  await b.disconnect();
})();

function cpIfExists(src, dir) {
  try { fs.copyFileSync(src, path.join(dir, path.basename(src))); } catch {}
}
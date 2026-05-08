#!/usr/bin/env node
require('dotenv').config();

const { createStealthBrowser, randomDelay } = require('./browser');
const { loginToGmx, manageGmxAlias, readOtpFromGmx } = require('./gmxHandler');
const {
  registerFireworksAccount,
  confirmFireworksAccount,
  createFireworksApiKey,
} = require('./fireworksHandler');
const { generateAliasName, splitAliasToName } = require('./nameGenerator');
const { saveToPool, poolStats } = require('./pool');
const logger = require('./logger');

const ACCOUNTS_PER_RUN = parseInt(process.env.ACCOUNTS_PER_RUN) || 1;
const args = process.argv.slice(2);
const MODE = args.includes('--loop') ? 'loop' : 'once';

async function runRotationCycle() {
  const aliasName = generateAliasName();
  const { firstName, lastName } = splitAliasToName(aliasName);

  logger.info('═══════════════════════════════════════════════');
  logger.info(`🚀 Starte Rotations-Zyklus`);
  logger.info(`👤 Alias: ${aliasName} (${firstName} ${lastName})`);
  logger.info('═══════════════════════════════════════════════');

  let gmxBrowser, gmxPage, aliasEmail;

  try {
    const gmx = await loginToGmx();
    gmxBrowser = gmx.browser;
    gmxPage = gmx.page;

    aliasEmail = await manageGmxAlias({ page: gmxPage, aliasName });
    logger.info(`📧 Alias bereit: ${aliasEmail}`);
  } catch (err) {
    logger.error(`❌ GMX Phase fehlgeschlagen: ${err.message}`);
    if (gmxBrowser) await gmxBrowser.close();
    throw err;
  }

  let fwBrowser, fwPage;

  try {
    const fw = await createStealthBrowser();
    fwBrowser = fw.browser;
    fwPage = fw.page;

    await registerFireworksAccount({
      page: fwPage,
      aliasEmail,
      firstName,
      lastName,
    });

    logger.info('⏳ Warte auf OTP-E-Mail...');
    await randomDelay(5000, 10000);
  } catch (err) {
    logger.error(`❌ Fireworks Registrierung fehlgeschlagen: ${err.message}`);
    if (fwBrowser) await fwBrowser.close();
    if (gmxBrowser) await gmxBrowser.close();
    throw err;
  }

  let confirmUrl;
  try {
    confirmUrl = await readOtpFromGmx({ page: gmxPage, aliasEmail });
    logger.info('📬 OTP-URL erhalten');
  } catch (err) {
    logger.error(`❌ OTP lesen fehlgeschlagen: ${err.message}`);
    if (fwBrowser) await fwBrowser.close();
    if (gmxBrowser) await gmxBrowser.close();
    throw err;
  }

  let apiKey;
  try {
    await confirmFireworksAccount({
      page: fwPage,
      confirmUrl,
      firstName,
      lastName,
    });

    apiKey = await createFireworksApiKey({ page: fwPage });
  } catch (err) {
    logger.error(`❌ Account-Bestätigung/API Key fehlgeschlagen: ${err.message}`);
    if (fwBrowser) await fwBrowser.close();
    if (gmxBrowser) await gmxBrowser.close();
    throw err;
  }

  saveToPool({
    alias: aliasName,
    email: aliasEmail,
    password: process.env.FIREWORKS_PASSWORD || 'ZOE.jerry2024',
    apiKey,
    firstName,
    lastName,
    createdAt: new Date().toISOString(),
  });

  await fwBrowser.close();
  await gmxBrowser.close();

  logger.info('🎉 Rotations-Zyklus abgeschlossen!');
  logger.info(`🔑 API Key: ${apiKey.substring(0, 20)}...`);

  const stats = poolStats();
  logger.info(`📊 Pool: ${stats.total} gesamt | ${stats.available} verfügbar`);

  return { aliasEmail, apiKey, firstName, lastName };
}

async function main() {
  logger.info('🤖 SINator-Rotator gestartet [Chrome + CDP + stealth-suite flags]');
  logger.info(`📋 Modus: ${MODE} | Accounts pro Lauf: ${ACCOUNTS_PER_RUN}`);

  const stats = poolStats();
  logger.info(`📊 Aktueller Pool: ${stats.total} Accounts (${stats.available} verfügbar)`);

  if (MODE === 'loop') {
    while (true) {
      for (let i = 0; i < ACCOUNTS_PER_RUN; i++) {
        logger.info(`\n🔄 Account ${i + 1}/${ACCOUNTS_PER_RUN}`);
        try {
          await runRotationCycle();
        } catch (err) {
          logger.error(`❌ Zyklus ${i + 1} fehlgeschlagen: ${err.message}`);
        }
        if (i < ACCOUNTS_PER_RUN - 1) {
          const pause = 30000 + Math.random() * 30000;
          logger.info(`⏸️ Pause ${Math.round(pause / 1000)}s...`);
          await new Promise((r) => setTimeout(r, pause));
        }
      }
      const loopPause = 3600000;
      logger.info('💤 Nächster Lauf in 1 Stunde...');
      await new Promise((r) => setTimeout(r, loopPause));
    }
  } else {
    for (let i = 0; i < ACCOUNTS_PER_RUN; i++) {
      logger.info(`\n🔄 Account ${i + 1}/${ACCOUNTS_PER_RUN}`);
      try {
        await runRotationCycle();
      } catch (err) {
        logger.error(`❌ Zyklus ${i + 1} fehlgeschlagen: ${err.message}`);
      }
      if (i < ACCOUNTS_PER_RUN - 1) await randomDelay(15000, 30000);
    }
    logger.info('\n✅ Alle Zyklen abgeschlossen');
    process.exit(0);
  }
}

main().catch((err) => {
  logger.error(`💥 Fataler Fehler: ${err.message}`);
  process.exit(1);
});
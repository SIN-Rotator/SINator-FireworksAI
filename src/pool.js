const fs = require('fs');
const path = require('path');
const logger = require('./logger');

const POOL_FILE = process.env.POOL_FILE || './data/fireworksai-pool.json';

function ensurePoolFile() {
  const dir = path.dirname(POOL_FILE);
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
  if (!fs.existsSync(POOL_FILE)) {
    fs.writeFileSync(POOL_FILE, JSON.stringify({ accounts: [] }, null, 2));
  }
}

function readPool() {
  ensurePoolFile();
  try {
    return JSON.parse(fs.readFileSync(POOL_FILE, 'utf-8'));
  } catch {
    return { accounts: [] };
  }
}

function saveToPool(account) {
  const pool = readPool();
  pool.accounts.push({
    ...account,
    createdAt: account.createdAt || new Date().toISOString(),
    used: false,
  });
  fs.writeFileSync(POOL_FILE, JSON.stringify(pool, null, 2));
  logger.info(`✅ API Key gespeichert: ${account.alias} → ${(account.apiKey || '').substring(0, 12)}...`);
}

function getNextApiKey() {
  const pool = readPool();
  const unused = pool.accounts.find((a) => !a.used);
  if (!unused) return null;

  unused.used = true;
  unused.usedAt = new Date().toISOString();
  fs.writeFileSync(POOL_FILE, JSON.stringify(pool, null, 2));
  return unused;
}

function listPool() {
  return readPool().accounts;
}

function poolStats() {
  const pool = readPool();
  const total = pool.accounts.length;
  const used = pool.accounts.filter((a) => a.used).length;
  return { total, used, available: total - used };
}

module.exports = { saveToPool, getNextApiKey, listPool, poolStats };
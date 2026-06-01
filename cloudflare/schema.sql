-- ╔══════════════════════════════════════════════════════════════════════════╗
-- ║  SINator Cloudflare D1 — Pool Key Database                                 ║
-- ║  Ersetzt data/fireworksai-pool.json im Fallback-Betrieb (Mac offline)      ║
-- ║  Issue #24 — Hybrid Deployment: Mac Primary + Cloudflare Workers Fallback  ║
-- ╚══════════════════════════════════════════════════════════════════════════╝
--
-- Apply:  wrangler d1 execute sinator-pool --remote --file=cloudflare/schema.sql
-- Local:  wrangler d1 execute sinator-pool --local  --file=cloudflare/schema.sql

CREATE TABLE IF NOT EXISTS pool_keys (
  id                TEXT PRIMARY KEY,
  api_key           TEXT NOT NULL,
  alias_email       TEXT NOT NULL,
  key_name          TEXT,
  status            TEXT NOT NULL DEFAULT 'active',   -- active | suspended | used
  created_at        TEXT,
  suspended_at      TEXT,
  suspended_reason  TEXT,
  credits_initial   REAL DEFAULT 6.0,
  credits_remaining REAL,
  -- rotation bookkeeping for round-robin fairness inside the Worker
  last_used_at      TEXT,
  use_count         INTEGER NOT NULL DEFAULT 0,
  synced_at         TEXT
);

-- Hot path: "give me the next usable key". Index keeps the SELECT cheap so we
-- stay well inside the D1 free-tier read budget (5M reads/day).
CREATE INDEX IF NOT EXISTS idx_pool_keys_status   ON pool_keys (status);
CREATE INDEX IF NOT EXISTS idx_pool_keys_rotation ON pool_keys (status, use_count, last_used_at);

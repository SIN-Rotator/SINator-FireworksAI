# SINator — Cloudflare Workers Fallback (Issue #24)

Hybrid deployment: **Mac primary** (10× local proxy + pool-router) with a
**Cloudflare Worker + D1 fallback** for when the Mac is offline.

```
Client → sinatorpool-router.delqhi.com
            │
   ┌────────┴─────────┐
   │  Smart Router    │  (client-side health-check on :9998/health)
   └───┬──────────┬───┘
   Mac up        Mac down
       │              │
  local pool      CF Worker  ── D1 (pool_keys)  ── Fireworks
  :9998           (this dir)
```

The local `scripts/pool-router.py` now also forwards to this Worker
automatically when every local pool is dead/in-cooldown (set `CF_WORKER_URL`).

## Files

| File           | Purpose                                            |
|----------------|----------------------------------------------------|
| `worker.js`    | The fallback proxy. One Worker, key-rotation in D1 |
| `schema.sql`   | D1 `pool_keys` table (replaces `fireworksai-pool.json`) |
| `wrangler.toml`| Bindings (D1 + KV) + custom-domain notes           |
| `package.json` | npm scripts for deploy / db init                   |

The Mac→CF sync lives in `../scripts/sync_to_cf.py`.

## Setup

```bash
cd cloudflare
npm install                       # installs wrangler
npx wrangler login

# 1. D1 database
npx wrangler d1 create sinator-pool          # paste database_id into wrangler.toml
npm run db:init                              # apply schema.sql (remote)

# 2. KV (optional model cache)
npx wrangler kv namespace create MODEL_CACHE # paste id into wrangler.toml

# 3. Secrets (NOT in wrangler.toml)
npx wrangler secret put SINATOR_AUTH_TOKEN   # same Bearer token clients already use
npx wrangler secret put SYNC_TOKEN           # separate token for Mac → /pool/push

# 4. Deploy
npm run deploy
```

## Mac → CF sync

Run after each rotation (or on a timer). Uses env vars, no hardcoded URL/token:

```bash
export CF_WORKER_URL=https://sinatorpool-router.delqhi.com
export CF_SYNC_TOKEN=...            # == SYNC_TOKEN secret above
python3 scripts/sync_to_cf.py          # one-shot
python3 scripts/sync_to_cf.py --watch 60   # every 60s
```

Keychain `STORED_IN_KEYCHAIN` sentinels are hydrated to real keys before push;
keys that can't be hydrated are skipped (never pushed as a sentinel).

## Free-tier budget

| Resource        | Free        | This design                                  |
|-----------------|-------------|----------------------------------------------|
| Worker requests | 100k/day    | 1 request = 1 chat call (no fan-out)         |
| Worker CPU      | 10 ms/req   | Streaming = network I/O, not CPU → fits SSE  |
| D1 reads        | 5M/day      | 1 indexed `SELECT` per attempt               |
| D1 writes       | 100k/day    | 1 `UPDATE` per call + batched sync           |
| KV reads        | 10M/day     | model-id cache only                          |

---

## Answers to the 5 open questions

1. **Auth** — Yes. The Worker uses the same Bearer scheme as the local proxy
   (`SINATOR_AUTH_TOKEN`). `/health` and `/v1/models` stay public, matching the
   local proxy's `PUBLIC_PROXY_PATHS`. `/pool/push` uses a *separate* `SYNC_TOKEN`.

2. **Rate limiting / SSE on free tier** — Works. The 10 ms CPU limit counts
   *compute*, not wall-clock. Streaming the upstream `Response.body` straight
   through is network I/O and does not burn CPU time, so SSE responses of any
   duration are fine. We only `await upstream.text()` on the error path.

3. **Key-sync** — Via env vars (`CF_WORKER_URL`, `CF_SYNC_TOKEN`) consumed by
   `scripts/sync_to_cf.py`. Nothing is hardcoded; the push endpoint is
   `POST /pool/push` guarded by `SYNC_TOKEN`.

4. **DNS** — `sinatorpool-router.delqhi.com` is **primary = fallback** (points at
   the Worker), but the failover decision is made *client-side*: the Smart Router
   probes `http://<mac-ip>:9998/health` first and only uses the Worker when the
   Mac doesn't answer within ~2s. This keeps the Mac as primary without a
   Cloudflare Load Balancer (paid). Alternatively use a CF Load Balancer health
   monitor if you prefer server-side failover.

5. **Mac return** — Automatic. Because failover is health-check driven, the
   moment `:9998/health` responds again the client routes back to the Mac. The
   Worker stays warm as a passive fallback; the periodic `sync_to_cf.py` keeps
   D1 current so a future failover is seamless.

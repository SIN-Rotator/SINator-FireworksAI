# Cloudflare Worker (`worker.js`)

Single Cloudflare Worker that replaces the 10 local pool proxies when the Mac is
offline (**Issue #24**). OpenAI-compatible proxy to Fireworks AI with D1-backed
key rotation and silent dead-key swap.

## Dependencies

- **Runtime:** Cloudflare Workers (ES modules, `export default { fetch }`)
- **Bindings:** `DB` (D1 database, see `schema.sql`), optional `MODELS` (KV namespace for `/v1/models` cache)
- **Secrets:** `SINATOR_AUTH_TOKEN` (client bearer), `SYNC_TOKEN` (Mac→D1 push)

## Endpoints

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| `GET` | `/health` | public | Liveness + active/total key counts |
| `GET` | `/v1/models` | public | Fireworks model list (KV-cached) |
| `*` | `/v1/*`, `/inference/v1/*` | client | Proxy to Fireworks with key rotation |
| `POST` | `/pool/push` | sync | Upsert keys from the Mac into D1 |
| `GET` | `/pool/stats` | client | Pool counts by status |

## Key Functions

| Symbol | Purpose |
|--------|---------|
| `fetch(request, env)` | Router — dispatches by path, enforces auth |
| `nextKey(env, exclude)` | Pick least-used `active` key from D1 (excludes already-tried IDs) |
| `normalizeBody(env, body)` | Expand short model aliases (e.g., `"glm-5p1"` → `"accounts/fireworks/routers/glm-5p1-fast"`); matches against FALLBACK_MODELS + KV cache |
| `markKey(env, id, status)` | Set key status (`active` / `suspended` / `used`) + bump `use_count` |
| `proxyToFireworks(...)` | Forward request with current key; rotate on dead-key statuses |
| `pushKeys(env, keys)` | Batched D1 upsert for Mac sync |
| `requireAuth(request, token)` | Bearer-token check |

## Rotation Logic

1. `nextKey` selects the least-used `active` key.
2. Request body is normalized: short model aliases (e.g. `"glm-5p1"`) are expanded to full paths matching OpenCode config (e.g. `"accounts/fireworks/routers/glm-5p1-fast"`).
3. Request is forwarded to Fireworks with `Authorization: Bearer <key>`.
3. On `401/402/403/412` or a **permanent** `429` (spending limit) → `markKey(..., 'suspended')`, retry with next key.
4. SSE streams are passed through unchanged (network I/O only — no Worker CPU-limit issue on the free tier).
5. If all keys are exhausted → return the last upstream error.

## Important Config/Limits

| Item | Value |
|------|-------|
| Free Tier | 100k req/day (~10 users) |
| Models list | FALLBACK_MODELS (hardcoded) + KV cache hit = OpenCode config model IDs |
| Model alias expansion | Short form (`"glm-5p1"`) → full path matching FALLBACK_MODELS suffix |
| Models cache TTL | 1h (KV) |
| Dead-key statuses | `401, 402, 403, 412`, permanent `429` |

## Known Caveats

- Worker deploy (`wrangler deploy`) and D1 migration must be run by the maintainer with real Cloudflare credentials — see `README.md`.
- The Mac remains the source of truth; D1 is hydrated via push only (no pull-back).

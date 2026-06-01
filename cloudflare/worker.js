/**
 * ╔════════════════════════════════════════════════════════════════════════╗
 * ║  SINator Cloudflare Worker — Fallback Pool Proxy                         ║
 * ║  Issue #24 — Hybrid Deployment: Mac Primary + Cloudflare Workers Fallback ║
 * ╠════════════════════════════════════════════════════════════════════════╣
 * ║  EIN Worker ersetzt die 10 lokalen Proxys. Key-Rotation passiert hier    ║
 * ║  gegen die D1-Datenbank (pool_keys). SSE-Streaming wird durchgereicht.   ║
 * ║                                                                          ║
 * ║  Endpoints:                                                              ║
 * ║    GET  /health                  → Liveness + Pool-Zähler                ║
 * ║    GET  /v1/models               → Modell-Liste (KV-cached)              ║
 * ║    GET  /inference/v1/models     → Alias                                 ║
 * ║    *    /v1/*                     → Proxy zu Fireworks (mit Rotation)     ║
 * ║    *    /inference/v1/*           → Proxy zu Fireworks (mit Rotation)     ║
 * ║    POST /pool/push               → Mac → D1 Sync (neue/rotierte Keys)    ║
 * ║    GET  /pool/stats              → Pool-Statistik                        ║
 * ║                                                                          ║
 * ║  Bindings (siehe wrangler.toml):                                         ║
 * ║    env.DB           → D1 Database (pool_keys)                            ║
 * ║    env.MODEL_CACHE  → KV Namespace (optional, Modell-Cache)             ║
 * ║  Secrets (wrangler secret put ...):                                      ║
 * ║    env.SINATOR_AUTH_TOKEN  → Bearer-Token für Clients (= lokaler Proxy) ║
 * ║    env.SYNC_TOKEN          → Bearer-Token für Mac → /pool/push          ║
 * ╚════════════════════════════════════════════════════════════════════════╝
 */

const FIREWORKS_BASE = "https://api.fireworks.ai/inference/v1";

// HTTP-Codes die einen Key-Swap auslösen (Key tot / rate-limited).
const DEAD_KEY_CODES = new Set([401, 402, 403, 412]);
// Body-Keywords die einen 429 als *permanent* (Spending-Limit) markieren.
const PERMANENT_429_KEYWORDS = [
  "account.*suspended",
  "monthly spending limit",
  "spending limit",
  "suspended due to",
];
const PERMANENT_ERROR_KEYWORDS = [
  "suspended",
  "deactivated",
  "disabled",
  "invalid api key",
  "revoked",
  "expired",
  "payment required",
];

const MAX_SWAPS = 4; // wie viele tote Keys wir pro Request überspringen

const FALLBACK_MODELS = [
  // Exakt wie in der OpenCode-Config (SIN-Code-FireworksAI-OpenCode-Config)
  "fireworks/deepseek-v4-pro",
  "accounts/fireworks/models/deepseek-v4-flash",
  "fireworks/glm-5p1",
  "accounts/fireworks/routers/glm-5p1-fast",
  "fireworks/kimi-k2p6",
  "accounts/fireworks/routers/kimi-k2p6-turbo",
  "accounts/fireworks/models/kimi-k2p5",
  "accounts/fireworks/models/qwen3p6-plus",
  "fireworks/minimax-m2p7",
  "accounts/fireworks/models/minimax-m2p5",
  "accounts/fireworks/models/gpt-oss-120b",
  "accounts/fireworks/models/gpt-oss-20b",
];

const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, POST, PUT, PATCH, DELETE, OPTIONS",
  "Access-Control-Allow-Headers": "Authorization, Content-Type, Accept, Origin",
  "Access-Control-Max-Age": "86400",
};

function json(data, status = 200, extraHeaders = {}) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json", ...CORS_HEADERS, ...extraHeaders },
  });
}

function unauthorized(message = "Invalid or missing auth token") {
  return json({ error: "unauthorized", message }, 401);
}

/** Constant-time-ish bearer check. Returns true when token matches. */
function checkBearer(request, expected) {
  if (!expected) return true; // no token configured → open (mirrors local proxy)
  const auth = request.headers.get("Authorization") || "";
  return auth === `Bearer ${expected}`;
}

// ── D1 pool helpers ────────────────────────────────────────────────────────

/**
 * Pick the next usable key using least-recently / least-used round robin.
 * Keeps the read cheap (single indexed SELECT) for the D1 free tier.
 */
async function nextKey(env, exclude = []) {
  const placeholders = exclude.map(() => "?").join(",");
  const where =
    exclude.length > 0
      ? `status = 'active' AND id NOT IN (${placeholders})`
      : `status = 'active'`;
  const stmt = env.DB.prepare(
    `SELECT id, api_key, alias_email, key_name, use_count
       FROM pool_keys
      WHERE ${where}
      ORDER BY use_count ASC, COALESCE(last_used_at, '') ASC
      LIMIT 1`
  );
  const bound = exclude.length > 0 ? stmt.bind(...exclude) : stmt;
  return await bound.first();
}

async function markKeyUsed(env, id) {
  await env.DB.prepare(
    `UPDATE pool_keys
        SET use_count = use_count + 1, last_used_at = ?
      WHERE id = ?`
  )
    .bind(new Date().toISOString(), id)
    .run();
}

async function suspendKey(env, id, reason) {
  await env.DB.prepare(
    `UPDATE pool_keys
        SET status = 'suspended', suspended_at = ?, suspended_reason = ?
      WHERE id = ?`
  )
    .bind(new Date().toISOString(), reason || "swap", id)
    .run();
}

async function poolStats(env) {
  const row = await env.DB.prepare(
    `SELECT
        COUNT(*) AS total,
        SUM(CASE WHEN status = 'active'    THEN 1 ELSE 0 END) AS active,
        SUM(CASE WHEN status = 'suspended' THEN 1 ELSE 0 END) AS suspended,
        SUM(CASE WHEN status = 'used'      THEN 1 ELSE 0 END) AS used
       FROM pool_keys`
  ).first();
  return {
    total: row?.total ?? 0,
    active: row?.active ?? 0,
    suspended: row?.suspended ?? 0,
    used: row?.used ?? 0,
  };
}

function matchesKeyword(text, keywords) {
  const lower = (text || "").toLowerCase();
  return keywords.some((kw) => new RegExp(kw).test(lower));
}

// ── Request handlers ────────────────────────────────────────────────────────

async function handleModels(env) {
  // Try KV cache first (10M reads/day free) to avoid bundling a static list.
  if (env.MODEL_CACHE) {
    try {
      const cached = await env.MODEL_CACHE.get("model_ids", { type: "json" });
      if (Array.isArray(cached) && cached.length > 0) {
        return json({ object: "list", data: toModelList(cached) });
      }
    } catch (_) {
      /* fall through to static list */
    }
  }
  return json({ object: "list", data: toModelList(FALLBACK_MODELS) });
}

function toModelList(ids) {
  const now = Math.floor(Date.now() / 1000);
  return [...ids]
    .sort()
    .map((id) => ({ id, object: "model", created: now, owned_by: "fireworks" }));
}

/** Expand a short model alias ("glm-5p1") to its full path if possible. */
async function normalizeBody(env, body) {
  if (!body) return body;
  let parsed;
  try {
    parsed = JSON.parse(body);
  } catch {
    return body;
  }
  const model = parsed.model || "";
  if (!model || model.includes("/")) return body;

  let ids = FALLBACK_MODELS;
  if (env.MODEL_CACHE) {
    try {
      const cached = await env.MODEL_CACHE.get("model_ids", { type: "json" });
      if (Array.isArray(cached) && cached.length) ids = cached;
    } catch (_) {
      /* keep fallback */
    }
  }
  const full = ids.find((id) => id.split("/").pop() === model);
  if (full && full !== model) {
    parsed.model = full;
    return JSON.stringify(parsed);
  }
  return body;
}

/**
 * Proxy a request to Fireworks, rotating through D1 keys on dead-key codes.
 * SSE streaming works on the free tier because piping the upstream body back
 * to the client is network I/O — it does not consume Worker CPU time.
 */
async function handleProxy(request, env, fwPath) {
  const fwUrl = `${FIREWORKS_BASE}/${fwPath}`;
  const method = request.method;

  // Read the body once; reuse across retries.
  let body = null;
  if (["POST", "PUT", "PATCH"].includes(method)) {
    body = await request.text();
    body = await normalizeBody(env, body);
  }

  const tried = [];
  let lastErrBody = '{"error":"no_api_key","message":"Pool empty in D1"}';
  let lastStatus = 503;

  for (let attempt = 0; attempt < MAX_SWAPS; attempt++) {
    const key = await nextKey(env, tried);
    if (!key) break; // pool exhausted
    tried.push(key.id);

    const fwHeaders = new Headers();
    fwHeaders.set("Authorization", `Bearer ${key.api_key}`);
    fwHeaders.set("Content-Type", request.headers.get("Content-Type") || "application/json");
    const accept = request.headers.get("Accept");
    if (accept) fwHeaders.set("Accept", accept);

    let upstream;
    try {
      upstream = await fetch(fwUrl, { method, headers: fwHeaders, body });
    } catch (e) {
      lastErrBody = JSON.stringify({ error: "upstream_unreachable", message: String(e) });
      lastStatus = 502;
      continue;
    }

    const status = upstream.status;

    // Happy path → stream straight back (works for SSE and JSON alike).
    if (status < 400) {
      await markKeyUsed(env, key.id);
      const headers = new Headers(upstream.headers);
      for (const [k, v] of Object.entries(CORS_HEADERS)) headers.set(k, v);
      headers.delete("content-encoding");
      return new Response(upstream.body, { status, headers });
    }

    // Error path — peek at the body to decide swap vs. pass-through.
    const errText = await upstream.text();

    if (DEAD_KEY_CODES.has(status)) {
      const confirmedDead =
        status !== 402 ? true : matchesKeyword(errText, PERMANENT_ERROR_KEYWORDS);
      if (confirmedDead) {
        await suspendKey(env, key.id, `http_${status}`);
        lastErrBody = errText;
        lastStatus = status;
        continue; // try next key
      }
    }

    if (status === 429 && matchesKeyword(errText, PERMANENT_429_KEYWORDS)) {
      await suspendKey(env, key.id, "rate_limited_permanent");
      lastErrBody = errText;
      lastStatus = status;
      continue; // try next key
    }

    // Any other error (incl. transient 429, 400, 500) → return to client as-is.
    return new Response(errText, {
      status,
      headers: { "Content-Type": "application/json", ...CORS_HEADERS },
    });
  }

  return new Response(lastErrBody, {
    status: lastStatus,
    headers: { "Content-Type": "application/json", ...CORS_HEADERS },
  });
}

/**
 * Mac → CF sync. Upserts pool keys into D1 after each rotation.
 * Body: { keys: [{ id, api_key, alias_email, key_name, status, created_at,
 *                  suspended_at, suspended_reason, credits_initial,
 *                  credits_remaining }] }
 * A key marked suspended/used on the Mac is reflected here too.
 */
async function handlePush(request, env) {
  let payload;
  try {
    payload = await request.json();
  } catch {
    return json({ error: "bad_request", message: "Invalid JSON" }, 400);
  }
  const keys = Array.isArray(payload?.keys) ? payload.keys : null;
  if (!keys) return json({ error: "bad_request", message: "Missing 'keys' array" }, 400);

  const now = new Date().toISOString();
  const stmt = env.DB.prepare(
    `INSERT INTO pool_keys
       (id, api_key, alias_email, key_name, status, created_at,
        suspended_at, suspended_reason, credits_initial, credits_remaining, synced_at)
     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
     ON CONFLICT(id) DO UPDATE SET
       api_key           = excluded.api_key,
       alias_email       = excluded.alias_email,
       key_name          = excluded.key_name,
       status            = excluded.status,
       suspended_at      = excluded.suspended_at,
       suspended_reason  = excluded.suspended_reason,
       credits_initial   = excluded.credits_initial,
       credits_remaining = excluded.credits_remaining,
       synced_at         = excluded.synced_at`
  );

  const batch = keys.map((k) => {
    let status = k.status;
    if (!status) status = k.suspended ? "suspended" : k.used ? "used" : "active";
    return stmt.bind(
      k.id,
      k.api_key,
      k.alias_email || "",
      k.key_name || null,
      status,
      k.created_at || now,
      k.suspended_at || null,
      k.suspended_reason || null,
      k.credits_initial ?? 6.0,
      k.credits_remaining ?? null,
      now
    );
  });

  // D1 batch = one write op against the 100k writes/day budget per chunk.
  await env.DB.batch(batch);

  return json({ status: "success", synced: keys.length, at: now });
}

// ── Router ───────────────────────────────────────────────────────────────────

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const path = url.pathname;

    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: CORS_HEADERS });
    }

    // Public liveness — used by the Smart Router health-check.
    if (path === "/health" || path === "/") {
      const stats = await poolStats(env);
      return json({ status: "ok", role: "cloudflare-fallback", pool: stats });
    }

    // Mac → D1 sync (separate token from client auth).
    if (path === "/pool/push" && request.method === "POST") {
      if (!checkBearer(request, env.SYNC_TOKEN)) return unauthorized("Invalid sync token");
      return handlePush(request, env);
    }

    if (path === "/pool/stats") {
      if (!checkBearer(request, env.SINATOR_AUTH_TOKEN)) return unauthorized();
      return json({ status: "success", pool: await poolStats(env) });
    }

    // Models list is public (mirrors local proxy PUBLIC_PROXY_PATHS).
    if (path === "/v1/models" || path === "/inference/v1/models") {
      return handleModels(env);
    }

    // Everything else under /v1 or /inference/v1 is an authenticated proxy.
    const proxyMatch =
      path.match(/^\/inference\/v1\/(.*)$/) || path.match(/^\/v1\/(.*)$/);
    if (proxyMatch) {
      if (!checkBearer(request, env.SINATOR_AUTH_TOKEN)) return unauthorized();
      return handleProxy(request, env, proxyMatch[1]);
    }

    return json({ error: "not_found", path }, 404);
  },
};

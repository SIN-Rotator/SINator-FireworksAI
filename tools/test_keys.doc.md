# test_keys.py — Minimal-Token API Key Verification

## Purpose

Iterate the pool, send a 1-token probe (`{"messages": [{"content": "."}], "max_tokens": 1}`) to Fireworks for each key, and update the `suspended` flag based on the response.

- **Re-activates false-positive suspensions** — keys marked `suspended: true` from a past transient error but actually still alive
- **Pre-emptively detects exhausted credits** — keys with $0 balance get 412 *before* the next real chat request hits them

## Cost

`deepseek-v4-flash` at ~$0.60/M tokens. A 1-char prompt + 1 completion token = ~3 tokens/key.

| Pool size | Tokens | USD cost | Wall time (concurrency 8) |
|-----------|--------|----------|---------------------------|
| 50        | 150    | $0.0001  | ~6s                      |
| 100       | 300    | $0.0002  | ~12s                     |
| 256       | 768    | $0.0005  | ~30s                     |
| 1000      | 3000   | $0.0018  | ~2min                    |

Negligible — safe to run daily or on a cron.

## Usage

```bash
# Full scan (default — tests every key)
python3 tools/test_keys.py

# Re-verify suspended keys only (find false positives)
python3 tools/test_keys.py --only-suspended

# Verify available keys aren't actually dead
python3 tools/test_keys.py --only-available

# Test single key by ID
python3 tools/test_keys.py --key 3534b094-f929-403e-834e-62a94617e930

# Dry run — report what WOULD change without saving
python3 tools/test_keys.py --dry-run

# Fast scan
python3 tools/test_keys.py --concurrency 32
```

## Status Classification

| HTTP Status | Classification | Action                                  |
|-------------|----------------|-----------------------------------------|
| 200 / 204   | `alive`        | If was suspended → reactivate           |
| 401/402/403/412 | `dead`     | If was alive → mark `suspended: true`   |
| 429         | `rate_limited` | No change (transient)                   |
| 5xx         | `transient`    | No change (retry next scan)             |
| Timeout     | `timeout`      | No change (network/load)                |

## Dependencies

- `aiohttp` (in `requirements.txt`)
- `core/pool_manager.PoolManager` (loads from `data/fireworksai-pool.json`)
- `core/keychain_store.KeychainStore` (hydrates `STORED_IN_KEYCHAIN` sentinels)

## Why not just use the proxy's auto-swap?

The proxy does swap on 401/402/403/412/429 (see `proxy/server.py:67` `DEAD_KEY_CODES`). But:

1. **Reactive, not proactive** — Keys are only marked dead *after* a real chat request hits them
2. **No false-positive recovery** — A key that got 412 once stays suspended forever, even if Fireworks resets its state
3. **No scan coverage** — Unused keys stay in their initial state forever

`test_keys.py` complements the proxy by being the explicit "is this key actually alive" probe.

## Cron / Automation

Add to crontab for daily pool hygiene:

```cron
0 4 * * * cd /Users/jeremy/dev/SINator-fireworksai && python3 tools/test_keys.py --only-suspended >> logs/test_keys.log 2>&1
```

Re-verify suspended keys at 4am daily — picks up any Fireworks-side reactivation (e.g., new free credits).

## See Also

- `tools/recover_pool.py` — Reconstruct pool from macOS Keychain
- `proxy/server.py` — Live auto-swap on errors
- `agent_toolbox/core/pool_manager.py:213` — `mark_suspended()`

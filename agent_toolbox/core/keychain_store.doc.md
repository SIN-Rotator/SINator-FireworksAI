# File: `keychain_store.py`

macOS Keychain-backed secret store for Fireworks API keys. Pool JSON stores metadata only; actual key values live in the system Keychain as generic passwords under service `com.sinator.pool`.

## Dependencies

- **Imported by:** `agent_toolbox/core/pool_manager.py`, `agent_toolbox/api/routes/pool.py`
- **Imports:** `subprocess`, `json`, `pathlib`, `logging`

## Key Functions

| Symbol | Purpose |
|--------|---------|
| `store_key()` | Store an API key in macOS Keychain as generic password |
| `retrieve_key()` | Retrieve an API key from Keychain by key ID |
| `delete_key()` | Delete a Keychain entry by key ID |
| `migrate_pool()` | One-shot migration: move all plaintext keys from pool JSON into Keychain |
| `hydrate_keys()` | Replace `STORED_IN_KEYCHAIN` sentinel values with real keys from Keychain |
| `hydrate_single()` | Hydrate a single key dict |

## Important Config/Limits

- Keychain service name: `com.sinator.pool`
- Sentinel value: `STORED_IN_KEYCHAIN` (replaces api_key in JSON after migration)
- `hydrate_keys(include_api_key=False)` returns stats-safe list (all api_key = "")

## Known Caveats

- Keychain access fails if macOS asks for permission interactively — `security` CLI may prompt
- `retrieve_key()` returns `None` silently if the entry doesn't exist
- Migration is one-shot, not incremental — re-running skips already-migrated keys

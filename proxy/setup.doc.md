# proxy/setup.sh + start-multi.sh + update-installed.sh

Service management scripts for SINator Pool Proxy.

## Issue #26 Context

The installed version (`~/.sin-pool/`) was getting out of sync with the repo.
LaunchAgents with `KeepAlive: true` would respawn stale code even after
`start-multi.sh` killed the processes.

## Scripts

| Script | Purpose |
|--------|---------|
| `setup.sh [tunnel_url]` | Initial install: copies proxy files to `~/.sin-pool/`, creates LaunchAgent, patches opencode config |
| `start-multi.sh` | Development: kills LaunchAgents, syncs from repo, starts 10 proxys + router from repo |
| `update-installed.sh` | Production: syncs `~/.sin-pool/` and `~/.hermes/scripts/` from repo without reconfiguring |

## Paths

| Path | Purpose |
|------|---------|
| `~/.sin-pool/` | Installed proxy code (for LaunchAgent) |
| `~/.sin-pool/.version` | Git SHA + timestamp of last sync |
| `~/.hermes/scripts/pool-router.py` | Installed pool-router (for LaunchAgent) |
| `~/Library/LaunchAgents/com.sin.pool-proxy.plist` | Proxy LaunchAgent |
| `~/Library/LaunchAgents/com.sin.pool-router.plist` | Router LaunchAgent |

## Workflow

### Development (run from repo)
```bash
./proxy/start-multi.sh
# Stops LaunchAgents, syncs ~/.sin-pool/, starts from repo
# Changes take effect immediately
```

### Production (run installed version)
```bash
# After git pull:
./proxy/update-installed.sh
launchctl load ~/Library/LaunchAgents/com.sin.pool-proxy.plist
launchctl load ~/Library/LaunchAgents/com.sin.pool-router.plist
```

### Fresh install
```bash
./proxy/setup.sh https://your-tunnel.trycloudflare.com
```

## Debugging Stale Code (Issue #26)

```bash
# Check which version is running:
ps aux | grep -E "sin-pool|pool-router" | grep -v grep
# Should show ~/dev/SINator-fireworksai/... NOT ~/.sin-pool/

# Check installed version:
cat ~/.sin-pool/.version

# Force sync:
./proxy/update-installed.sh
```

## Known Caveats

- LaunchAgents run from `~/.sin-pool/`, not the repo. Use `update-installed.sh` after `git pull`.
- `start-multi.sh` disables LaunchAgents to prevent respawn conflicts during development.
- The router LaunchAgent may be at `~/.hermes/scripts/` (legacy path) — `update-installed.sh` handles both.

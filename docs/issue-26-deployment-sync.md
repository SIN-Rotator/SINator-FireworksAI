## Issue #26 + #27: Deployed Version Mismatch (RESOLVED)

**Problem:** The installed proxy/router versions in `~/.sin-pool/` and `~/.hermes/scripts/` were stale and never updated after code changes in the repo. LaunchAgents with `KeepAlive: true` would respawn them immediately even after `start-multi.sh` killed them.

**Issue #27 Addition:** The pool-router LaunchAgent uses a different plist name (`com.sinator.pool-router` or `com.sinhermes.poolrouter`) than expected, so it wasn't being unloaded properly.

**Root Causes:**
1. No sync mechanism from repo to installed directories
2. LaunchAgents running before kill could re-spawn stale processes
3. No version tracking to detect skew
4. `start-multi.sh` didn't unload LaunchAgents before starting development instances

**Resolution (v3):**

### For Users Running from Installed Version (~/.sin-pool/)

1. **Update the installed code:**
   ```bash
   cd ~/dev/SINator-fireworksai
   git pull
   ./proxy/update-installed.sh
   ```
   This syncs `~/.sin-pool/` and `~/.hermes/scripts/` from the repo without reconfiguring.

2. **Restart LaunchAgents:**
   ```bash
   launchctl load ~/Library/LaunchAgents/com.sin.pool-proxy.plist
   launchctl load ~/Library/LaunchAgents/com.sin.pool-router.plist
   ```

3. **Verify version is current:**
   ```bash
   cat ~/.sin-pool/.version
   # Should show recent Git SHA + timestamp
   ```

### For Development (Run from Repo)

```bash
cd ~/dev/SINator-fireworksai
./proxy/start-multi.sh
```

This:
- Unloads LaunchAgents first (prevents respawn)
- Kills old processes
- Syncs `~/.sin-pool/` from repo
- Starts 10 proxys + router from **repo** (not installed)
- Takes effect immediately

### Changes Made

| File | Change | Issue |
|------|--------|-------|
| `proxy/start-multi.sh` | LaunchAgent unload before kill; sync before start; all plist variants | #26, #27 |
| `proxy/setup.sh` | Write `.version` marker; always copy fresh | #26 |
| `proxy/update-installed.sh` | New script to sync installed versions; all plist variants | #26, #27 |
| `proxy/setup.doc.md` | New: document workflows + debugging stale code | #26 |

### Debugging Stale Code

If proxys are still running old code:

```bash
# Check what's running:
ps aux | grep -E "\.sin-pool|\.hermes" | grep -v grep
# Should NOT show ~/.sin-pool/ or ~/.hermes/ paths (run from repo instead)
# OR should show v3 timestamp (if running from installed)

# Force sync to latest:
./proxy/update-installed.sh

# Check installed version:
cat ~/.sin-pool/.version
git -C ~/dev/SINator-fireworksai rev-parse --short HEAD
# Should match
```

### Technical Details

**Version Marker:** Every sync writes `~/.sin-pool/.version` with the git SHA and timestamp.

**LaunchAgent Unload (Issue #27):** Multiple plist names exist for the pool-router:
- `com.sin.pool-router.plist`
- `com.sinator.pool-router.plist`
- `com.sinhermes.poolrouter.plist`

All three are now unloaded by `start-multi.sh` and `update-installed.sh`.

**Sync Mechanism:** `setup.sh` and `update-installed.sh` copy from repo to `~/.sin-pool/` (proxy) and `~/.hermes/scripts/` (router).

**No Reconfig on Update:** `update-installed.sh` updates code only, preserves `config.json` and `pool.json`.

### After Next `git pull`

Always run **one** of these:

```bash
# For production (LaunchAgent-based):
./proxy/update-installed.sh && \
  launchctl load ~/Library/LaunchAgents/com.sin.pool-proxy.plist && \
  launchctl load ~/Library/LaunchAgents/com.sin.pool-router.plist

# OR for development (run from repo):
./proxy/start-multi.sh
```

This ensures deployed code matches repo code.

### Known Limitations

- The pool-router LaunchAgent may still be at `~/.hermes/scripts/` (legacy path). Both `setup.sh` and `update-installed.sh` handle it.
- On Mac reboot, LaunchAgents run from `~/.sin-pool/` automatically. To run repo version, you must call `start-multi.sh` manually.
- OpenCode config patching (in `setup.sh`) only handles the first run — if you change it manually, `update-installed.sh` won't touch it.

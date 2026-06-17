# Tasks: Workflow

Docs: ../SKILL.md

## Pre-flight

- [ ] Confirm which operation the user needs: generate keys, check pool, fix config, restart services, or troubleshoot.
- [ ] Load `context/triggers.md` and `frameworks/standards.md`.
- [ ] If generating keys: verify Playwright chromium is installed.

## Task: Generate N New Keys

- [ ] Check current pool stats
  - `curl -s http://localhost:8100/api/v1/pool/stats`
  - Verify backend is running (if not, start it)
- [ ] Ensure Playwright chromium installed
  - `python3 -m playwright install chromium`
- [ ] Run rotation N times
  - `cd ~/dev/SINator-Fireworks-Rotator-v2 && python3 tools/rotate.py --debug`
  - Each rotation takes ~3 minutes (GMX + Fireworks signup + OTP + onboarding)
  - Log output for debugging
  - Onboarding flow: Page 1 (Account ID + First/Last Name + Terms → Continue) → Page 2 (Skip button)
- [ ] Add each new key to v3 pool (REQUIRED — dashboard reads v3)
  - `cd ~/dev/SIN-Rotator-SINator-FireworksAI && python3 -c "from agent_toolbox.core.pool_manager import PoolManager; PoolManager().add_key(api_key='fw_XXX', alias_email='alias@gmx.de', key_name='fw-XXX')"`
  - rotate.py saves to v2 pool automatically, but v3 pool is what the dashboard reads
- [ ] Verify keys in pool
  - Check pool stats show increased available count
  - E2E test through proxy

## Task: Check Pool Health

- [ ] Get pool stats
  - `curl -s http://localhost:8100/api/v1/pool/stats | python3 -m json.tool`
- [ ] Check available count (>5 healthy, 0 critical)
- [ ] Check suspended count (trend indicator)
- [ ] Check public tunnel
  - `curl -s -o /dev/null -w "%{http_code}" https://sinatorpool-router.delqhi.com/inference/v1/models`
- [ ] Report status with recommendation

## Task: Fix ProviderInitError

- [ ] Identify broken models in opencode.json
  - Search for `reasoning_effort` in model options/variants
- [ ] Replace with `thinking: {type: "enabled"}` (or `disabled` for off-variant)
- [ ] Sync to repo config (`SIN-Code-FireworksAI-OpenCode-Config/opencode.json`)
- [ ] Commit and push
- [ ] Tell user to restart opencode

## Task: Restart Services

- [ ] Stop all: `./tools/manage_services.sh stop`
- [ ] Start all: `./tools/manage_services.sh start`
- [ ] Verify: `./tools/manage_services.sh status`
- [ ] Check backend health: `curl http://localhost:8100/`
- [ ] Check tunnel: `curl -s -o /dev/null -w "%{http_code}" https://sinatorpool-router.delqhi.com/inference/v1/models`

## Task: Restart Cloudflare Tunnel Only

- [ ] Unload: `launchctl unload ~/Library/LaunchAgents/com.cloudflared.sinator.plist`
- [ ] Load: `launchctl load ~/Library/LaunchAgents/com.cloudflared.sinator.plist`
- [ ] Wait 3s
- [ ] Verify: `curl -s -o /dev/null -w "%{http_code}" https://sinatorpool-router.delqhi.com/inference/v1/models`
- [ ] E2E test through public URL

## Post-flight

- [ ] Pool stats verified
- [ ] E2E test passed (if applicable)
- [ ] Changes committed to relevant repos (if any)
- [ ] User informed of result + next steps

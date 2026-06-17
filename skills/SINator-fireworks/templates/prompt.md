# Template: Prompt Reference

Docs: ../SKILL.md

## For Key Generation

```
Task: Generate N new Fireworks API keys.

Steps:
1. Check pool stats (curl localhost:8100/api/v1/pool/stats)
2. Ensure Playwright installed (python3 -m playwright install chromium)
3. For each key (1..N):
   a. Run: cd ~/dev/SINator-Fireworks-Rotator-v2 && python3 tools/rotate.py --debug
   b. Extract API key from output ("API Key: fw_XXX")
   c. Add to pool: curl -X POST http://localhost:8100/api/v1/pool/add -d '{"api_key":"fw_XXX","key_name":"batch-N"}'
4. Verify pool stats show increased available count
5. E2E test through public proxy
```

## For ProviderInitError Fix

```
Task: Fix ProviderInitError for Fireworks models in opencode.json.

Root cause: @ai-sdk/fireworks v2.x only supports thinking:{type:enabled|disabled},
not reasoning_effort.

Steps:
1. Find all models with reasoning_effort in options or variants
2. Replace options: {reasoning_effort:"low"} → {thinking:{type:"enabled"}}
3. Replace variant "off": {reasoning_effort:"..."} → {thinking:{type:"disabled"}}
4. Replace other variants: {reasoning_effort:"..."} → {thinking:{type:"enabled"}}
5. Write to ~/.config/opencode/opencode.json + repo config
6. Commit + push
7. Tell user to restart opencode
```

## For Pool Health Check

```
Task: Check SINator Fireworks pool health.

Steps:
1. curl -s http://localhost:8100/api/v1/pool/stats | python3 -m json.tool
2. Check available count
3. curl -s -o /dev/null -w "%{http_code}" https://sinatorpool-router.delqhi.com/inference/v1/models
4. If available < 5: recommend key generation
5. If tunnel down: restart cloudflared
6. Report: total/available/suspended + tunnel status + recommendation
```

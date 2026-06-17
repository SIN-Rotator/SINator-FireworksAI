# Context: Examples

Docs: ../SKILL.md

## Example 1: Generate 20 New Keys

```bash
# 1. Check current pool
curl -s http://localhost:8100/api/v1/pool/stats | python3 -m json.tool

# 2. Ensure Playwright is installed
python3 -m playwright install chromium

# 3. Run batch generation
cd ~/dev/SINator-Fireworks-Rotator-v2
for i in $(seq 1 20); do
  echo "=== Rotation #$i ==="
  python3 tools/rotate.py --debug 2>&1 | tee -a /tmp/sinator-batch.log
  sleep 5
done

# 4. Sync v2 pool to v3 pool (if needed)
cp ~/dev/SINator-Fireworks-Rotator-v2/data/fireworksai-pool.json \
   ~/dev/SIN-Rotator-SINator-FireworksAI/data/fireworksai-pool.json

# 5. Verify
curl -s http://localhost:8100/api/v1/pool/stats | python3 -m json.tool
```

## Example 2: Fix ProviderInitError

```bash
# Check which models have reasoning_effort (unsupported by @ai-sdk/fireworks v2.x)
python3 -c "
import json
with open('$HOME/.config/opencode/opencode.json') as f:
    cfg = json.load(f)
for k, m in cfg['provider']['fireworks-ai']['models'].items():
    if 'reasoning_effort' in m.get('options', {}):
        print(f'  BROKEN: {k}')
    for vn, vo in m.get('variants', {}).items():
        if 'reasoning_effort' in vo:
            print(f'  BROKEN: {k} variant={vn}')
"

# Fix: replace reasoning_effort with thinking
python3 -c "
import json
from pathlib import Path
p = Path.home() / '.config/opencode/opencode.json'
with open(p) as f: cfg = json.load(f)
models = cfg['provider']['fireworks-ai']['models']
for k, m in models.items():
    if 'reasoning_effort' in m.get('options', {}):
        m['options'] = {'thinking': {'type': 'enabled'}}
    for vn, vo in m.get('variants', {}).items():
        if 'reasoning_effort' in vo:
            vo.clear()
            vo['thinking'] = {'type': 'disabled' if vn == 'off' else 'enabled'}
with open(p, 'w') as f:
    json.dump(cfg, f, indent=2, ensure_ascii=False)
    f.write('\n')
print('Fixed.')
"
```

## Example 3: Restart Tunnel + Verify Public Pool

```bash
# Restart Cloudflare tunnel
launchctl unload ~/Library/LaunchAgents/com.cloudflared.sinator.plist 2>/dev/null
launchctl load ~/Library/LaunchAgents/com.cloudflared.sinator.plist
sleep 3

# Verify public URL
curl -s -o /dev/null -w "%{http_code}" https://sinatorpool-router.delqhi.com/inference/v1/models

# E2E test
curl -s -X POST https://sinatorpool-router.delqhi.com/inference/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer 7avN1KkfInNqcOMn2CtwLTvx" \
  -d '{"model":"accounts/fireworks/models/glm-5p1","messages":[{"role":"user","content":"Say hi"}],"max_tokens":20}'
```

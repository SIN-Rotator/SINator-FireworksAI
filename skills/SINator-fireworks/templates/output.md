# Template: Expected Output

Docs: ../SKILL.md

## Pool Stats Output

```json
{
  "total": 359,
  "available": 12,
  "used": 10,
  "suspended": 337
}
```

**Interpretation:**
- `available > 5`: healthy
- `available 1-5`: low — plan key generation
- `available = 0`: critical — generate keys immediately
- `suspended` trending up: keys being rate-limited/banned, need fresh keys

## Key Generation Success Output

```
✅ #N/M — Key: fw_X8fV... — Pool resp: {"status":"ok"}
```

## Key Generation Failure Output

```
❌ #N FAILED — last 20 lines:
  [error traceback]
```

## Service Status Output

```
com.sinator.backend        ✓ loaded (pid 12345)
com.sinator.pool-router    ✓ loaded (pid 12346)
com.sinator.pool-proxy-8888 ✓ loaded (pid 12347)
...
com.cloudflared.sinator    ✓ loaded (pid 12350)
```

## E2E Test Success

```json
{
  "id": "chatcmpl-xxx",
  "choices": [{"message": {"content": "..."}}],
  "usage": {"total_tokens": 21}
}
```

## Config Fix Output

```
Fixed N models: model1, model2, model3
Commit: abc1234 on main
```

# BUILDING PLAN — SINator Fireworks AI v5 (2026-05-21)

## Status Summary — COMPLETE FLOW VERIFIED ✅

```
GMX Rotation (19.8s) → Fireworks Signup → GMX Email Verify → Login
→ Onboarding (CUA) → Use-Case + $5 → API Key: fw_8d1PLFjvQMdgJFzjDZSTRx
```

| Flow | Name | Status | Details |
|------|------|--------|---------|
| #0 | GMX Session | ✅ | Cookie-based, click "E-Mail" for SID |
| #1 | GMX Alias Rotate | ✅ 3/3 | Playwright delete + create in iframe, CUA OK |
| #2 | Fireworks Signup | ✅ | Via GMX OTP email → verify URL |
| #3 | Fireworks Login | ✅ | `/login` → "Email Login" → `input[name="email"]` |
| #4 | Onboarding | ✅ | CUA: names + Terms-CB + Continue |
| #5 | Use-Case + $5 | ✅ | CUA: checkboxes + Submit |
| #6 | API Key | ✅ | `/settings/users/api-keys` → PopUpButton → menuitem |

## Current Architecture (v5, 2026-05-21)

### Hybrid Approach: CUA + Playwright + CDP

| Tool | Used For |
|------|----------|
| **CUA** | Navigation clicks, Dialog OK, React-Checkbox toggle, type_text for names |
| **Playwright** | Form fill (email, password, alias name), Button clicks, Iframe interaction, Verification |
| **CDP** | OOPIF extraction (mailbody-ui.de), Cookie management (clear for Fireworks), Session detection |

### Key Learnings

- **React Checkbox**: Playwright `check()` + JS `click()` ignored → CUA `AXPress` only
- **Fireworks email input**: `name="email"` NOT `type="email"` 
- **API Keys URL**: `/settings/users/api-keys` NOT `/settings/workspace/api-keys`
- **GMX Delete**: `.table_field:has-text()` hover(force=True) → `[title*="löschen"]` click(force=True)
- **Cookie Banner**: Must dismiss before ANY form interaction on Fireworks
- **Onboarding order**: Fill ALL fields → THEN Terms checkbox → THEN Continue

## Next Steps

### Done ✅
- [x] GMX alias rotation works (3/3, 19.8s)
- [x] Fireworks login works (email + password)
- [x] Onboarding via CUA (names, Terms, use-cases)
- [x] API key creation via PopUpButton + menuitem
- [x] Full flow documented in README, AGENTS.md, knowledge-base.md

### Todo
- [ ] Integrate into single automated flow: `python tools/rotate.py` → returns API key
- [ ] Pool management: store API keys in `data/fireworksai-pool.json`
- [ ] Error recovery: retry on session expiry, IAC detection
- [ ] Clean up deprecated CDP methods in fireworks_service.py

## Verification

```bash
# Full rotation
python tools/gmx_alias_tool.py rotate

# Standalone API
cd ~/dev/gmx-alias-tool && python3 server.py &
curl http://localhost:8001/alias/rotate -X POST
```

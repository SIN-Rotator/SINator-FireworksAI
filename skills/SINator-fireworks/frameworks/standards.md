# Frameworks: Standards & Constraints

Docs: ../SKILL.md

## Technology Stack

- **Python 3.14** (system) — rotator, backend, pool manager
- **Playwright** — browser automation (Chromium for Testing)
- **FastAPI** — backend API server
- **aiohttp** — proxy servers + pool router
- **SQLite** — pool state (v3 has keychain_store backup)
- **JSON** — pool storage (`data/fireworksai-pool.json`)
- **Cloudflare Tunnel** — public exposure
- **LaunchAgents (macOS)** — service persistence
- **OpenCode / @ai-sdk/fireworks** — consumer config

## Repos

| Repo | GitHub | Purpose |
|---|---|---|
| `~/dev/SINator-Fireworks-Rotator-v2` | `SIN-Rotator/SINator-Fireworks-Rotator-v2` | Working rotator (rotate.py) |
| `~/dev/SIN-Rotator-SINator-FireworksAI` | `SIN-Rotator/SINator-FireworksAI` | Backend + pool + proxy (production) |
| `~/dev/SIN-Code-FireworksAI-OpenCode-Config` | `OpenSIN-Code/SIN-Code-FireworksAI-OpenCode-Config` | OpenCode config repo |

## Config Standards

- `data/config.json` format:
  ```json
  {
    "gmx_email": "nemotronv3@gmx.de",
    "gmx_password": "<password>",
    "fireworks_password": "ZOE.jerry2024!"
  }
  ```
- Pool JSON format: `[{"key": "fw_XXX", "status": "available", "alias": "...", ...}]`
- Config can also be set via env vars: `GMX_EMAIL`, `GMX_PASSWORD`, `FIREWORKS_PASSWORD`

## OpenCode Config Rules

- `@ai-sdk/fireworks` v2.x: only `thinking: {type: "enabled"|"disabled"}` is supported
- NEVER use `reasoning_effort` in Fireworks model options — causes `ProviderInitError`
- `baseURL` must point to pool proxy: `https://sinatorpool-router.delqhi.com/inference/v1`
- `apiKey` is the pool auth token, NOT a real Fireworks key: `7avN1KkfInNqcOMn2CtwLTvx`
- Model `id` must match exact Fireworks API model ID (e.g. `accounts/fireworks/models/glm-5p1`)

## Security Constraints

- Never commit `data/config.json` or `data/fireworksai-pool.json` (both .gitignored)
- Never echo real Fireworks API keys (`fw_XXX`) in logs/chat
- Never paste GMX password in chat
- Pool auth token (`7avN1KkfInNqcOMn2CtwLTvx`) is semi-public (used in opencode.json) but should not be in git
- GMX account `delqhi@gmx.de` is BANNED — always use `nemotronv3@gmx.de`

## Quality Gates

- Pool stats must show >0 available keys after generation
- E2E test through proxy must return valid JSON response
- `opencode debug config` must not show errors after config changes
- All LaunchAgents must be loaded (`launchctl list | grep com.sinator`)

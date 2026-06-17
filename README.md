<a name="readme-top"></a>

<p align="center">
  <a href="./LICENSE">
    <img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License" />
  </a>
  <a href="https://www.python.org/downloads/">
    <img src="https://img.shields.io/badge/python-3.12+-3776AB?logo=python&logoColor=white" alt="Python" />
  </a>
  <a href="https://fastapi.tiangolo.com/">
    <img src="https://img.shields.io/badge/FastAPI-005571?logo=fastapi&logoColor=white" alt="FastAPI" />
  </a>
  <a href="https://github.com/SIN-Rotator/SINator-FireworksAI/stargazers">
    <img src="https://img.shields.io/github/stars/SIN-Rotator/SINator-FireworksAI?style=social" alt="Stars" />
  </a>
</p>

<p align="center">
  <em>Never hit a rate limit again. 484 keys, 10 proxies, 12 models, one URL.</em>
</p>

<p align="center">
  <a href="#quick-start">Quick Start</a> |
  <a href="#features">Features</a> |
  <a href="#models">Models</a> |
  <a href="#api">API</a> |
  <a href="#contributing">Contributing</a>
</p>

---

# SINator &mdash; Fireworks AI Key Pool

An automated API key pool for Fireworks AI. It generates accounts via GMX email aliases, rotates keys on rate limits, and exposes a single OpenAI-compatible endpoint with 10-proxy auto-failover.

**The problem:** Fireworks AI enforces per-key rate limits and spending caps. Running multiple AI agents means you hit 429s constantly.

**The solution:** SINator maintains a pool of hundreds of API keys, automatically rotates them on 429/401/403, and gives you one URL that never goes down &mdash; even if the Mac goes offline (Cloudflare Worker fallback).

## Quick Start

```bash
git clone https://github.com/SIN-Rotator/SINator-FireworksAI.git
cd SINator-FireworksAI
pip install -r agent_toolbox/requirements.txt
python agent_toolbox/start_toolbox.py
```

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:9998/inference/v1",
    api_key="your-pool-token",
)

response = client.chat.completions.create(
    model="accounts/fireworks/models/deepseek-v4-pro",
    messages=[{"role": "user", "content": "Hello!"}],
)
```

> [!NOTE]
> For full setup (GMX credentials, proxy config, Cloudflare fallback), see [docs/setup.md](docs/setup.md).

## Features

- **Automated Key Generation** &mdash; GMX alias rotation, Fireworks signup, OTP verification, API key extraction, all fully automated via Playwright CDP
- **10-Proxy Auto-Failover** &mdash; Router distributes across 10 proxies with automatic switch on errors
- **Silent Key Swap** &mdash; On 429/401/403, proxy swaps key without the client ever noticing
- **Soft-Ownership** &mdash; Agents get dedicated keys with heartbeat, so long conversations never break
- **Cloudflare Fallback** &mdash; When the Mac goes offline, a CF Worker with D1 database takes over automatically
- **OpenAI-Compatible** &mdash; One URL works with opencode, Cursor, Continue, Python SDK, curl, any OpenAI client
- **12 Fireworks Models** &mdash; DeepSeek V4, GLM 5.1/5.2, Kimi K2.6/K2.7, Qwen 3.6/3.7, MiniMax M2.7/M3
- **1s Key-Retry** &mdash; No immediate 503 &mdash; 300 retries over 5 minutes before giving up

## Live Pool Stats

The pool currently manages **484 keys** across 10 proxies. Most keys are suspended (431) due to Fireworks spending caps, while **43 remain available** for active rotation:

![Pool Status](./assets/pool-status.png)

| Metric | Value |
|--------|-------|
| **Total Keys** | 484 |
| **Available** | 43 |
| **Suspended** | 431 |
| **Used** | 10 |
| **Assigned** | 2 |

## Models

12 Fireworks AI models accessible through one endpoint:

| Model | ID | Context | Output |
|:------|:---|--------:|-------:|
| **DeepSeek V4 Pro** | `accounts/fireworks/models/deepseek-v4-pro` | 1M | 64K |
| **DeepSeek V4 Flash** | `accounts/fireworks/models/deepseek-v4-flash` | 1M | 64K |
| **GLM 5.1** | `accounts/fireworks/models/glm-5p1` | 198K | 32K |
| **GLM 5.1 Fast** | `accounts/fireworks/routers/glm-5p1-fast` | 128K | 16K |
| **GLM 5.2** | `accounts/fireworks/models/glm-5p2` | 256K | 64K |
| **Kimi K2.6** | `accounts/fireworks/models/kimi-k2p6` | 256K | 32K |
| **Kimi K2.6 Turbo** | `accounts/fireworks/routers/kimi-k2p6-turbo` | 128K | 16K |
| **Kimi K2.7 Code** | `accounts/fireworks/models/kimi-k2p7-code` | 256K | 32K |
| **Kimi K2.7 Code Fast** | `accounts/fireworks/routers/kimi-k2p7-code-fast` | 128K | 16K |
| **MiniMax M2.7** | `accounts/fireworks/models/minimax-m2p7` | 192K | 32K |
| **MiniMax M3** | `accounts/fireworks/models/minimax-m3` | 512K | 64K |
| **Qwen 3.7 Plus** | `accounts/fireworks/models/qwen3p7-plus` | 256K | 32K |

Context windows range from 128K to 1M tokens. DeepSeek V4 leads with 1M, while MiniMax M3 offers 512K for long-context tasks:

![Model Context Windows](./assets/model-context.png)

### Usage

**OpenCode:**

```bash
mkdir -p ~/.config/opencode
curl -fsSL https://raw.githubusercontent.com/OpenSIN-Code/SIN-Code-FireworksAI-OpenCode-Config/main/opencode.json \
  -o ~/.config/opencode/opencode.json
```

**curl:**

```bash
curl http://localhost:9998/inference/v1/chat/completions \
  -H "Authorization: Bearer your-pool-token" \
  -d '{"model":"accounts/fireworks/models/minimax-m3","messages":[{"role":"user","content":"Hi"}]}'
```

## Key Rotation Logic

1. **New requests** &mdash; next available key from pool. On 429, cooldown + retry with new key
2. **Existing chats** &mdash; always the creation key (state-mapping). Key swap would cause 401
3. **429 on stateful** &mdash; passed through (key swap would cause 401)
4. **401/403** &mdash; key marked "suspended", removed from rotation
5. **Cooldown** &mdash; 60s default, then key available again
6. **No key available** &mdash; 503 after 300 retries over 5 minutes

## API

### Pool Endpoints

| Endpoint | Method | Description |
|:---------|:-------|:------------|
| `/api/v1/pool/stats` | GET | Pool statistics (total, available, suspended, etc.) |
| `/api/v1/pool/keys` | GET | All keys with status |
| `/api/v1/pool/lease` | POST | Reserve a key |
| `/api/v1/pool/return` | POST | Release a key |
| `/api/v1/pool/report` | POST | Report bad key + auto-lease replacement |
| `/api/v1/pool/add` | POST | Add a key manually |
| `/api/v1/pool/agent-key` | POST | Soft-ownership key assignment |
| `/api/v1/pool/agent-release` | POST | Agent releases key |
| `/api/v1/pool/agent-heartbeat` | POST | Agent heartbeat |

Full API docs at `http://localhost:8100/docs` (Swagger UI).

## Architecture

```
Clients (opencode, Cursor, Continue, Python)
  |  OpenAI-compatible API (ONE URL)
  v
Pool-Router (:9998, auto-failover)
  |  distributes across 10 proxies
  v
Pool Proxys (:8888-:8897, silent key swap)
  |  key rotation on 429/401/403, 1s retry
  v
Backend (:8100, FastAPI + PoolManager)
  |  PoolManager + Keychain + Rotation-Orchestrator
  v
Chrome (Playwright CDP, single browser)
  |  GMX + Fireworks automation
  v
Fireworks AI (api.fireworks.ai)
```

## Deploy

| Method | Command |
|:-------|:--------|
| **Backend** | `python agent_toolbox/start_toolbox.py` |
| **Pool Router** | `python3 scripts/pool-router.py` |
| **Cloudflare** | `cd cloudflare && wrangler deploy` |

> [!NOTE]
> See [cloudflare/README.md](cloudflare/README.md) for Cloudflare Worker fallback setup with D1 database.

## Ecosystem

| Repo | Function |
|:-----|:---------|
| **SINator-FireworksAI** (this) | Key pool + proxy + automation |
| [SINator-dashboard](https://github.com/SIN-Rotator/SINator-dashboard) | Tauri dashboard + setup wizard |
| [SINator-heypiggy](https://github.com/SIN-Rotator/SINator-heypiggy) | HeyPiggy account generator |
| [OpenCode Config](https://github.com/OpenSIN-Code/SIN-Code-FireworksAI-OpenCode-Config) | opencode.json with 12 models |
| [Hermes Bundle](https://github.com/SIN-Hermes-Bundles/SIN-Hermes-Provider-Bundle) | Hermes provider config |

## Contributing

1. Fork the repository
2. Create your branch (`git checkout -b feature/amazing-feature`)
3. Test your changes (`python -m pytest tests/ -v`)
4. Commit and push
5. Open a Pull Request

See [CONTRIBUTING.md](CONTRIBUTING.md) for details.

## License

Distributed under the **MIT License**. See [LICENSE](LICENSE) for details.

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="./assets/sin-ai-banner.svg" />
    <source media="(prefers-color-scheme: light)" srcset="./assets/sin-ai-banner-light.svg" />
    <img src="./assets/sin-ai-banner.svg" alt="SIN AI — Enterprise Agent Platform" />
  </picture>
</p>

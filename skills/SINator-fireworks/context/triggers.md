# Context: Triggers & Boundaries

Docs: ../SKILL.md

## Trigger Phrases

- "fireworks key" / "fireworks api key"
- "generate fireworks keys" / "gen fireworks keys"
- "pool stats" / "pool status"
- "key rotation" / "rotate keys"
- "sinator pool" / "fireworks pool"
- "add fireworks key" / "add key to pool"
- "sinator backend" / "pool backend"
- "pool proxy" / "fireworks proxy"
- "sinator tunnel" / "cloudflare sinator"
- "opencode fireworks config" / "fireworks provider"
- "ProviderInitError fireworks"
- "429 fireworks" / "rate limit fireworks"

## Boundaries

- **In scope:** Fireworks AI key generation, pool management, proxy/router service management, Cloudflare tunnel for Fireworks pool, OpenCode Fireworks provider config, troubleshooting pool exhaustion / 429 storms / ProviderInitError
- **Out of scope:** Vercel AI Gateway pool (separate stack at `~/dev/SINator-Vercel`), v0.dev pool (separate stack at `~/dev/SINator-v0`), GMX account creation (only alias rotation within existing account), Fireworks model training/fine-tuning

## Tone & Style

- Technical, concise, German/English mixed (user speaks German, code/docs are English)
- Use tables for structured data (ports, services, endpoints, pitfall→fix)
- Show exact commands with full paths — never assume cwd
- Always show verification step after any action

## Examples of Good Input

```text
User: "generiere 20 neue fireworks api keys"
→ Check pool stats, run batch rotation, add to pool, verify

User: "pool stats"
→ curl localhost:8100/api/v1/pool/stats, display formatted

User: "ProviderInitError bei Qwen 3.7 Plus"
→ Check opencode.json for reasoning_effort, replace with thinking option

User: "sinator tunnel ist down"
→ Check cloudflared LaunchAgent, restart, verify public URL
```

## Examples of Bad Input

```text
User: "generate Vercel API keys"
→ "That's the SINator-Vercel stack, not Fireworks. Use the SINator-Vercel repo."

User: "create a new GMX account"
→ "GMX account creation is out of scope. This skill only rotates aliases within an existing GMX account."
```

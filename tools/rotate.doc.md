# rotate.py — Full Rotation Orchestrator

## Purpose
End-to-end Fireworks account rotation: GMX alias creation → Fireworks signup → OTP verify → login → onboarding → API key → pool save.

## Dependencies
- **Imports from:** `agent_toolbox.core.fireworks_service` (Bot Chrome flow)
- **Imports from:** `agent_toolbox.core.gmx_service` (GMX alias rotation)
- **Imports from:** `agent_toolbox.core.pool_manager` (key persistence)
- **Imports from:** `agent_toolbox.core.config_manager` (credentials)
- **Imported by:** CLI (`python tools/rotate.py`)

## Flow
```
Step 0: GMX Login (User Chrome, Profile 73)
Step 1: GMX Alias Rotation (delete old → create new)
Step 2: Fireworks Signup (Bot Chrome, ephemeral)
Step 3: OTP Poll (User Chrome, GMX inbox)
Step 4: Verify Account (Bot Chrome, open OTP URL)
Step 5: Login + Onboarding (Bot Chrome)
Step 6: API Key Generation (Bot Chrome)
Step 7: Save to Pool (JSON + macOS Keychain)
```

## Two Chrome Instances
- **User Chrome** (`--cdp-port 9222`): GMX ops, OTP reading. Profile 73, never killed.
- **Bot Chrome** (ephemeral `chromium.launch()`): Fireworks ops. Created per rotation, closed after API key.

## CLI Arguments
| Arg | Required | Default | Description |
|-----|----------|---------|-------------|
| `alias` | No | auto-generated | GMX alias name |
| `--gmx-email` | Yes* | config | GMX account email |
| `--gmx-password` | Yes* | config | GMX account password |
| `--password` | Yes* | config | Fireworks account password |
| `--cdp-port` | No | 0 (launch new) | CDP port for User Chrome |
| `--save` | No | True | Save API key to pool |
| `--debug` | No | False | Enable DEBUG logging |

*Required unless set in `data/config.json` or environment variables.

## Key Design Decisions
- Bot Chrome uses `launch()` (not `connect_over_cdp`) to avoid killing User Chrome
- OTP polling reads from User Chrome's GMX session (not Bot Chrome)
- `signup_fireworks()` validates `passwords_filled` + `create_clicked` before proceeding
- API key name derived from alias prefix (e.g., `pulse-runner-931` → `pulse`)

# SINator-FireworksAI — Agent Toolbox

**Purpose:** Automated GMX email alias rotation → Fireworks AI account registration → API key pool management.

**Architecture:** FastAPI backend with raw CDP websocket for GMX SPA automation. No Playwright for GMX (crashes on iframe detach).

---

## Quick Start

```bash
cd agent_toolbox
pip install -r requirements.txt
python3 start_toolbox.py
```

Server starts on `http://localhost:8000` — Swagger UI at `/docs`.

---

## API Endpoints

### Browser Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/browser/start` | Start Chrome with copied profile |
| POST | `/api/v1/browser/stop` | Stop Chrome |
| GET | `/api/v1/browser/status` | Get browser status |

### GMX Services

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/gmx/session/check` | Check GMX session active |
| POST | `/api/v1/gmx/session/ensure` | **Flow 0** — Login or recover GMX session |
| POST | `/api/v1/gmx/email-addresses` | Navigate to alias settings page |
| POST | `/api/v1/gmx/alias/delete` | Delete existing alias |
| POST | `/api/v1/gmx/alias/create` | Create new alias |
| POST | `/api/v1/gmx/alias/rotate` | **ATOMIC** — delete + create in one call |
| POST | `/api/v1/gmx/inbox/open` | Open GMX inbox |
| POST | `/api/v1/gmx/otp/read` | Poll inbox for OTP/confirm URL |

### Fireworks AI (Phase 2 — in progress)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/fireworks/register` | Register new Fireworks account |
| POST | `/api/v1/fireworks/confirm` | Confirm account via OTP URL |
| POST | `/api/v1/fireworks/apikey` | Create API key |

---

## Core Endpoints Detail

### `POST /api/v1/gmx/alias/rotate`

**Atomically rotates GMX alias — delete existing + create new in one call.**

```bash
curl -X POST http://localhost:8000/api/v1/gmx/alias/rotate \
  -H "Content-Type: application/json" \
  -d '{"new_alias_name": "turbo-mantis"}'
```

**Response:**
```json
{
  "status": "success",
  "deleted_alias": "blaze-runner@gmx.de",
  "created_alias": "turbo-mantis@gmx.de",
  "created_alias_name": "turbo-mantis",
  "steps_completed": [
    "session_active",
    "settings_page_loaded",
    "email_addresses_opened",
    "isolated_world_created",
    "alias_deleted",
    "form_filled",
    "add_button_clicked",
    "alias_created"
  ],
  "steps_failed": [],
  "execution_time": "42.40s",
  "error": null
}
```

### `POST /api/v1/browser/start`

**Start Chrome with COPY-based profile handling (never symlink — breaks macOS Keychain).**

```bash
curl -X POST http://localhost:8000/api/v1/browser/start \
  -H "Content-Type: application/json" \
  -d '{"cdp_port": 9222}'
```

---

## Architecture

```
agent_toolbox/
├── core/
│   ├── browser_manager.py   # Chrome subprocess singleton (COPY profile)
│   ├── cdp_client.py        # Raw CDP websocket client
│   ├── gmx_service.py       # GMX automation via CDP + isolated world
│   └── fireworks_service.py # Fireworks registration (Phase 2)
├── api/
│   ├── routes/
│   │   ├── gmx.py           # GMX endpoints
│   │   ├── fireworks.py     # Fireworks endpoints
│   │   ├── browser.py       # Browser management
│   │   ├── pool.py          # API key pool
│   │   └── cookies.py       # Cookie management
│   └── schemas.py           # Pydantic models
├── start_toolbox.py         # FastAPI entry point
└── requirements.txt
```

### GMX Automation Architecture

**Problem:** GMX email addresses page lives in a **cross-origin iframe** (`3c-bap.gmx.net`) inside `bap.navigator.gmx.net`. Playwright crashes on frame detach. Direct DOM access throws cross-origin errors.

**Solution:** CDP `Page.createIsolatedWorld` — creates a JS execution context inside the iframe with full DOM access.

```
Main Page: bap.navigator.gmx.net/mail_settings?sid=...
  └─ iframe#thirdPartyFrame_mail_settings
       url: 3c-bap.gmx.net/mail/client/settings/allEmailAddresses
       (cross-origin → needs isolated world)

Automation flow:
1. CDP connect to Chrome
2. Page.getFrameTree → find iframe frameId
3. Page.createIsolatedWorld(frameId) → get contextId
4. Runtime.evaluate(contextId) → query iframe DOM
5. getBoundingClientRect() → element coords
6. DOM.getBoxModel(iframe) → iframe offset
7. Input.dispatchMouseEvent at (element_x + iframe_offset_x, ...)
```

### Profile Handling

**BANNED:** `os.symlink` for user-data-dir — breaks macOS Keychain cookie encryption.

**REQUIRED:** Copy `Local State` + profile folder to `/tmp` before Chrome startup.

```python
TEMP_DIR = f"/tmp/sinator-chrome-{timestamp}"
shutil.copy(LocalState_path, TEMP_DIR)
shutil.copytree(Profile73_path, f"{TEMP_DIR}/Profile 901")
Chrome --user-data-dir=TEMP_DIR --profile-directory="Profile 901" --remote-debugging-port=9222
```

---

## Full Pipeline (4 Flows)

### `POST /api/v1/rotation/full` — Complete Account Rotation

**Atomically rotates GMX alias → Fireworks registration → API key extraction.**

```bash
curl -X POST http://localhost:8000/api/v1/rotation/full \
  -H "Content-Type: application/json" \
  -d '{"fireworks_password": "YourPassword123!"}'
```

**Flow 0 (Session):** Check GMX session → Login if needed (Profile Icon → Logout → Login → Login → Email → Password)

**Flow 1 (GMX Alias):** Delete existing alias → Create new alias (`{adj}-{noun}-{3digits}@gmx.de`)

**Flow 2 (Fireworks Registration):** Navigate to /signup → Cookie Banner dismiss → Email → Password → Create Account → OTP polling

**Flow 3 (OTP & Setup):** Read OTP URL from GMX email (via `detail-body-iframe` mailbody-ui.de) → Confirm account → Sign In → Setup profile → Submit for $5 credits → Create API key

**Response:**
```json
{
  "status": "success",
  "gmx_alias": "swift-hawk-842@gmx.de",
  "fireworks_account": "swift-hawk-842@gmx.de",
  "api_key": "fw_2KY4b8C2d1E9f0G3h...",
  "api_key_name": "swift-hawk",
  "steps_completed": ["gmx_session_active", "gmx_alias_rotated", "fw_registered", "fw_otp_received", "fw_setup_complete", "api_key_created"],
  "steps_failed": [],
  "execution_time": "187.32s"
}
```

---

## Status

- ✅ Chrome startup with profile copy
- ✅ **Flow 0:** GMX session ensure / login recovery
- ✅ GMX session check
- ✅ GMX email-addresses page navigation
- ✅ GMX alias deletion
- ✅ GMX alias creation
- ✅ GMX alias rotation (atomic delete+create)
- ✅ **Flow 3:** OTP polling via `detail-body-iframe` (mailbody-ui.de)
- ✅ Fireworks AI registration + OTP
- ✅ API key pool management
- ✅ Full pipeline: `POST /rotation/full`

---

## Environment Variables

```bash
GMX_EMAIL=opensin@gmx.de
GMX_PASSWORD=your_password
FIREWORKS_PASSWORD=your_password
CDP_PORT=9222
```
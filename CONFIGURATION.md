# SINator Fireworks AI — Konfiguration

*Alle Konfigurationsmöglichkeiten für Backend, Proxy und Rotation.*

---

## 1. Environment Variables

| Variable | Standard | Beschreibung |
|----------|----------|-------------|
| `SINATOR_AUTH_TOKEN` | — | Auth-Token für API-Zugriff (optional, wenn gesetzt muss jeder Request `Authorization: Bearer <token>` mitsenden) |
| `PORT` | `8000` | Backend-HTTP-Port |

---

## 2. Config File (`data/config.json`)

Wird via Dashboard-Setup-Seite (`/setup`) oder direkt bearbeitet:

```json
{
  "gmx_email": "deinname@gmx.de",
  "gmx_password": "DEIN_GMX_PASSWORT",
  "fireworks_password": "DEIN_FIREWORKS_PASSWORT"
}
```

**API Endpoints:**
- `GET /api/v1/config` — Aktuelle Config lesen
- `POST /api/v1/config` — Config speichern (public, kein Auth)

**Felder:**
| Feld | Pflicht | Beschreibung |
|------|---------|-------------|
| `gmx_email` | ✅ | GMX Login Email |
| `gmx_password` | ✅ | GMX Login Passwort (wird für Chrome Session verwendet) |
| `fireworks_password` | ✅ | Passwort für neu erstellte Fireworks Accounts |

---

## 3. GMX Credentials

Im Chrome Profil 73 (simoneschulze) gespeichert. Bei Session-Verlust:
- GMX manuell im Browser öffnen und einloggen
- Oder Session-Recovery-Protokoll aus AGENTS.md

**Backup:** `backup/session/gmx-cookies-master.json` (read-only, chmod 444)

---

## 4. Pool-Manager

**Datei:** `data/fireworksai-pool.json`

```json
{
  "keys": [
    {
      "id": "uuid",
      "api_key": "fw_abc123...",
      "email": "foo-bar-123@gmx.de",
      "status": "available",
      "created_at": "2026-05-25T12:00:00Z"
    }
  ]
}
```

**Key Status:**
| Status | Bedeutung |
|--------|-----------|
| `available` | Nutzbar |
| `used` | Verbraucht (Spending Limit erreicht) |
| `suspended` | Von Fireworks gesperrt |

**Pool-API:**
| Endpoint | Methode | Beschreibung |
|----------|---------|-------------|
| `/api/v1/pool/stats` | GET | Pool Statistiken |
| `/api/v1/pool/keys` | GET | Alle Keys mit Status |
| `/api/v1/pool/lease` | POST | Nächsten verfügbaren Key holen |
| `/api/v1/pool/report` | POST | Key Status melden (suspended/used) |
| `/api/v1/pool/credential/{id}` | DELETE | Key löschen |

---

## 5. Pool-Router (`:9998`)

**Start:** `proxy/start-multi.sh`
**Status:** `launchctl list | grep pool`

**Auto-Failover Strategie:**
| Status | Reaktion |
|--------|----------|
| 413 Payload Too Large | Nächster Proxy |
| 429 Rate Limit | Nächster Proxy |
| 412 Account Suspended | Nächster Proxy |
| 500/502/503/504 | Nächster Proxy |
| 3 Fehler in 60s | Cooldown 60s |

---

## 6. Proxy-Instanzen (`:8888-:8897`)

Jeder Proxy ist eine aiohttp-Instanz:
- OpenAI-compatible API
- Eigener API-Key aus dem Pool
- Silent Key Swap bei Fehlern
- launchd-Autostart via `com.sinator.pool-proxy-{port}`

---

## 7. Port-Übersicht

| Port | Service | Beschreibung |
|------|---------|-------------|
| `8000` | FastAPI Backend | Pool-Manager + GMX/Fireworks Automation |
| `8888-8897` | Pool-Proxys | 10× OpenAI-compatible Proxy-Instanzen |
| `9998` | Pool-Router | Auto-Failover über alle Proxys |
| `9222` | Chrome CDP | Remote Debugging Port |

---

*Stand: 2026-05-30*

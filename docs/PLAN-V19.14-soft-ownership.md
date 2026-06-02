# V19.14 PLAN — Soft Ownership Multi-Agent Key Distribution

> **Issue:** [#29](https://github.com/SIN-Rotator/SINator-FireworksAI/issues/29)
> **Status:** PLAN ONLY — KEINE Code-Änderungen
> **Erstellt:** 2026-06-02
> **Betrifft:** `pool_manager.py`, `proxy/pool_client.py`, `proxy/key_cache.py`, `proxy/server.py`, `agent_toolbox/api/routes/pool.py`

---

## 1. Problem

### Symptom
Mehrere OpenCode-Agents (Main-Agent + Subagents + parallele Sessions) teilen sich aktuell wenige verfügbare Firebase-Keys. Sobald Agent A einen Key least, ist er für 30min exklusiv geblockt. Agent B muss `_ensure_key_with_retry()` 300×1s warten (5min Timeout) → 503 wenn nichts frei wird.

### Root Cause
Das aktuelle Lease-System ist **exklusiv** — ein Key wird durch `leased_until` + `leased_to` für genau einen Consumer reserviert. Der Pool hat aktuell nur **5 verfügbare Keys** (259 total, 244 suspended). 10 Proxies + N Agents konkurrieren darum.

### User-Anforderung
> "jeder soll seinen eigenen token bekommen aber wenn keiner verfügbar ist darf auch einer genutzt werden der bereits in verwendung ist"

→ **Soft Ownership** mit Fallback-Sharing. Nie blockieren, immer einen Key zurückgeben.

---

## 2. Research Findings

### Fireworks API Key-Verhalten

| Eigenschaft | Fundstelle |
|---|---|
| Rate-Limits sind **pro Account / pro API-Key** | `docs.fireworks.ai/serverless/rate-limits` |
| Free Accounts: 10 RPM, 3.6M Prompt TPM | `docs.fireworks.ai/guides/quotas_usage/account-quotas` |
| Paid Accounts: 6.000 RPM, adaptive TPM | selbe Quelle |
| Jeder Key = eigener Account = eigene Rate-Limits | Implizit durch Account-Struktur |
| Sharing eines Keys = alle Consumer teilen EIN Rate-Limit | Schlussfolgerung aus obigem |
| Serverless 429: adaptiv, wächst mit Usage | `serverless/rate-limits` |
| Account-Suspension: $5 Credits aufgebraucht → Key tot | Proxy-Code `PERMANENT_429_KEYWORDS` |

### Wichtige Erkenntnis

**Jeder Fireworks API-Key ist ein eigener Account mit EIGENEN Rate-Limits.**
→ Agent-1 mit Key A und Agent-2 mit Key B haben getrennte 10 RPM Budgets.
→ Agent-1 und Agent-2 mit dem GLEICHEN Key A teilen sich EIN 10 RPM Budget.
→ **Mehr Keys = mehr parallele Kapazität.**

### Proxy 429-Handling (aktuell)

```python
# proxy/server.py:60
PERMANENT_429_KEYWORDS = (
    "account.*suspended",
    "monthly spending limit",
    "reached.*limit",
    "suspended due to",
    "spending limit",
)
# Bei transientem 429: sofort an Client zurück mit Retry-After
# Bei permanentem 429 (spending limit): Key swappen
```

---

## 3. Current Architecture (Ist-Zustand)

```
┌──────────┐  ┌──────────┐  ┌──────────┐
│ Agent A  │  │ Agent B  │  │ Agent C  │    3 OpenCode-Agents
└────┬─────┘  └────┬─────┘  └────┬─────┘
     │              │              │
     ▼              ▼              ▼
┌──────────────────────────────────────────┐
│  Pool-Proxy :8888                        │
│  KeyCache: primary_key, backup_key       │
│  _ensure_key() → PoolClient.lease()      │
│  → lease(leased_to="proxy-8888-8191")    │
└──────────────┬───────────────────────────┘
               │ POST /pool/lease {"leased_to":"proxy-8888-..."}
               ▼
┌──────────────────────────────────────────┐
│  Backend :8100                            │
│  PoolManager.lease_key():                 │
│    for key in keys:                       │
│      if leased_until > now: continue  ←─ BLOCKIERT
│      key["leased_until"] = now + 1800     │
│      key["leased_to"] = "proxy-8888-..."  │
│      return key                           │
│  → return None wenn alle geleast          │
└──────────────────────────────────────────┘

PROBLEM: Agent A least Key-1 → 30min gesperrt
         Agent B fragt an → Key-1 ist blockiert → wartet
         Nur 5 Keys verfügbar → nach 5 Agents ist Ende
```

### Lease-Felder (aktuell)

| Feld | Typ | Beschreibung |
|---|---|---|
| `leased_until` | float (epoch) | Exklusiv-Sperre bis Zeitstempel |
| `leased_to` | string | Consumer-Identifier (z.B. "proxy-8888-8191") |
| `lease_id` | string (12 hex) | Eindeutige Lease-ID |
| `leased_at` | float (epoch) | Zeitpunkt der Lease-Erteilung |

### Blockierende Stellen

1. **`PoolManager.lease_key()`** (pool_manager.py:393-445): Lineare Suche, skip wenn `leased_until > now`
2. **`PoolClient.lease()`** (pool_client.py:36-75): `r.status_code == 404 → return None`
3. **`_ensure_key_with_retry()`** (server.py:381-393): 300×1s Retry-Loop → 5min Timeout

---

## 4. Proposed Solution: Soft Ownership + Sticky Assignment

### Konzept

```
Statt EXKLUSIVEM Lease → STICKY ZUWEISUNG mit Fallback-Sharing.

┌─ Key A ── assigned_to: agent-1 ── active_consumers: [agent-1] ─────────┐
├─ Key B ── assigned_to: agent-2 ── active_consumers: [agent-2, agent-4]─┤
├─ Key C ── assigned_to: agent-3 ── active_consumers: [agent-3] ─────────┤
├─ Key D ── assigned_to: None ───── active_consumers: [] ───────────────┤
└─ Key E ── assigned_to: None ───── active_consumers: [agent-1] ─────────┘

Agent-1 fragt an:
  1. Hat Agent-1 einen assigned Key mit keinem/geringem active_consumers?
     → Key A (assigned_to=agent-1, nur 1 Consumer) → SOFORT zurück

Agent-5 fragt an (neu, kein assigned Key):
  1. Hat Agent-5 einen assigned Key? → Nein
  2. Gibt es unassigned Keys? → Key D (assigned_to=None, empty)
     → assign Key D an agent-5, zurück
  3. Wenn nichts unassigned: least-loaded assigned Key
     → Key E (nur 1 Consumer) → SHARED zurück

KEY INSIGHT: Ein Fireworks-Key KANN von mehreren Agents gleichzeitig
genutzt werden (Fireworks API prüft nur den Key-Wert, nicht den Consumer).
Rate-Limits teilen sich dann, aber das ist besser als gar kein Key.
```

### Neue Pool-Felder

```json
{
  "assigned_to": "agent-1",           // Sticky-Owner (bleibt permanent)
  "active_consumers": ["agent-1"],    // Wer nutzt aktuell? (dynamisch)
  "last_heartbeat": 1780398054.1,     // Letzter Heartbeat (für Timeout-Cleanup)
  "shared_count": 0,                  // Wie oft wurde dieser Key geteilt?
  "leased_until": null,               // DEPRECATED → ersetzt durch assigned_to + active_consumers
  "leased_to": null,                  // DEPRECATED
  "lease_id": null,                   // DEPRECATED
  "leased_at": null                   // DEPRECATED
}
```

### Lease-Logik (neu)

```python
def get_key_for_agent(agent_id: str, preferred_key_id: str = None) -> dict | None:
    """
    Soft-Ownership Key-Zuweisung.
    
    Priorität:
      1. Sticky: Agent hat einen assigned Key → SOFORT zurück
      2. Unassigned: Nimm freien Key, assigne ihn dem Agent
      3. Least-shared: Nimm assigned Key mit wenigsten active_consumers
      4. None: Kein Key verfügbar (alle suspended/used)
    
    KEINE Wartezeit. KEIN Blocking.
    """
    self.reload()
    
    # Filter: nur nicht-suspended, nicht-used Keys
    active = [k for k in self.keys if not k.get("used") and not k.get("suspended")]
    
    if not active:
        return None
    
    # 1. Sticky: Agent hat schon einen assigned Key
    if preferred_key_id:
        for k in active:
            if k["id"] == preferred_key_id:
                return _hydrate_and_register(k, agent_id)
    
    # 2. Agent-eigener assigned Key
    for k in active:
        if k.get("assigned_to") == agent_id:
            return _hydrate_and_register(k, agent_id)
    
    # 3. Unassigned Key
    for k in active:
        if not k.get("assigned_to"):
            k["assigned_to"] = agent_id
            self.save()
            return _hydrate_and_register(k, agent_id)
    
    # 4. Least-shared: Key mit minimalen active_consumers
    best = min(active, key=lambda k: len(k.get("active_consumers", [])))
    best.setdefault("shared_count", 0)
    best["shared_count"] += 1
    logger.info(f"Key {best['id'][:8]} SHARED (consumer {agent_id} joins {best['active_consumers']})")
    return _hydrate_and_register(best, agent_id)
```

### Release-Logik (neu)

```python
def release_key_for_agent(agent_id: str, key_id: str):
    """
    Agent meldet: "Ich bin fertig mit diesem Key".
    Entfernt agent aus active_consumers. Löscht nicht den assigned_to.
    """
    for k in self.keys:
        if k["id"] == key_id:
            consumers = k.get("active_consumers", [])
            if agent_id in consumers:
                consumers.remove(agent_id)
            k["active_consumers"] = consumers
            self.save()
            return True
    return False
```

### Heartbeat + Cleanup (neu)

```python
# Im Backend-Lifespan (alle 60s):
async def _cleanup_stale_consumers():
    """Entfernt Consumer die länger als 5min keinen Heartbeat gesendet haben."""
    now = time.time()
    for key in pool.keys:
        if key.get("last_heartbeat") and now - key["last_heartbeat"] > 300:
            key["active_consumers"] = []  # Alle Consumer raus
            # assigned_to bleibt erhalten (Sticky)
```

---

## 5. Identität: Wer ist "ein Agent"?

### Problem
OpenCode hat keine eingebaute Agent-ID. Ein Main-Agent, der einen Subagent delegiert, sieht für den Proxy aus wie dieselbe Session (gleiche IP, gleicher Port).

### Lösungsansätze

**A. Session-basierte ID (x-agent-id Header)**
```python
# In opencode Config (~/.config/opencode/opencode.json):
{
  "provider": {
    "fireworks-ai": {
      "options": {
        "headers": {
          "x-agent-id": "opencode-main-{uuid}"
        }
      }
    }
  }
}
```
→ Jeder opencode-Client setzt eine persistente UUID im Header.
→ Subagents erben den Header vom Parent → zählen als EIN Agent (teilen sich einen Key).

**B. Proxy-level Session-Affinity**
```python
# proxy/server.py: Der Proxy tracked welche x-agent-id 
# zu welchem key_id in seiner Session gemappt ist.
# Kein neuer Lease nötig solange der Agent noch connected ist.
```

**Empfehlung: A (x-agent-id Header)** — einfachste Integration, keine Proxy-Änderung nötig außer Header-Weiterleitung.

---

## 6. API Änderungen

### Neuer Endpoint: `POST /api/v1/pool/agent-key`

```json
// Request
{
  "agent_id": "opencode-main-a3f8b2c1",
  "preferred_key_id": "0d0e7a85-3b50-..."  // optional, für Sticky
}

// Response (200)
{
  "status": "success",
  "api_key": "fw_6XMEii8wuL6FftAwmfQNex",
  "key_id": "0d0e7a85-3b50-...",
  "alias_email": "nexus-badger-842@gmx.de",
  "shared": false,
  "active_consumers": 1
}

// Response (409) — kein Key verfügbar
{
  "status": "error",
  "detail": "No keys available (all suspended/used)"
}
```

### Neuer Endpoint: `POST /api/v1/pool/agent-release`

```json
// Request
{
  "agent_id": "opencode-main-a3f8b2c1",
  "key_id": "0d0e7a85-3b50-..."
}

// Response (200)
{
  "status": "success",
  "released": true
}
```

### Neuer Endpoint: `POST /api/v1/pool/agent-heartbeat`

```json
// Request
{
  "agent_id": "opencode-main-a3f8b2c1",
  "key_id": "0d0e7a85-3b50-..."
}
```

### Deprecated (keep for backward-compat):
- `POST /pool/lease` — leitet auf `agent-key` um mit `agent_id = leased_to`
- `POST /pool/return` — leitet auf `agent-release` um

---

## 7. Proxy-Änderungen

### KeyCache → AgentKeyCache

```python
class AgentKeyCache:
    """Pro-Agent Key-Caching statt Proxy-weitem Singleton."""
    
    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self.primary = None       # Aktuell genutzter Key
        self.preferred_key_id = None  # Sticky Key-ID (survives restarts)
        self._load()              # Lädt aus ~/.sin-pool/agent-{id}.json
    
    def get_primary(self):
        if self.primary and not self.primary.get("shared"):
            # Unser exklusiver Key, kein Expiry-Check nötig
            return self.primary
        if self.primary and self.primary.get("shared"):
            # Shared Key → wir müssen prüfen ob er noch "unser" ist
            # (Heartbeat-basiert)
            return self.primary
        return None
```

### _ensure_key() → kein Retry-Loop mehr

```python
async def _ensure_key(self, agent_id: str):
    # 1. Cache check
    key = self.cache.get_primary()
    if key:
        return key
    
    # 2. Sofort vom Backend holen (kein Retry!)
    return await self.pool_client.get_agent_key(
        agent_id=agent_id,
        preferred_key_id=self.cache.preferred_key_id
    )
    # Wenn None → 503 (kein Retry, der Pool ist einfach leer)
```

### Header-Weiterleitung

```python
# proxy/server.py: _do_proxy()
# x-agent-id vom Client-Request extrahieren und merken
agent_id = request.headers.get("x-agent-id", self.proxy_id)
```

---

## 8. Migration Path

### Phase 1: Neue Felder + API (backward-compat)
- `pool_manager.py`: Neue Felder `assigned_to`, `active_consumers`, `shared_count`, `last_heartbeat`
- `pool_manager.py`: Neue Methoden `get_key_for_agent()`, `release_key_for_agent()`
- `routes/pool.py`: Neue Endpoints `/agent-key`, `/agent-release`, `/agent-heartbeat`
- **Alte Endpoints bleiben** (`/lease`, `/return` → leiten um)
- **Test:** Rotation läuft weiter, alte Proxies nutzen `/lease` wie bisher

### Phase 2: Proxy-Migration
- `pool_client.py`: Neue Methode `get_agent_key()` parallel zu `lease()`
- `key_cache.py` → `agent_key_cache.py`: Pro-Agent Caching
- `server.py`: `_ensure_key()` ohne Retry-Loop, `x-agent-id` Header
- `config.py`: Neues Feld `agent_id`
- LaunchAgents: `SIN_AGENT_ID=opencode-main` env-var
- **Test:** opencode Chat mit 2 parallelen Sessions → jeder kriegt eigenen Key

### Phase 3: Cleanup
- Entferne `leased_until`, `leased_to`, `lease_id`, `leased_at` aus neuen Keys
- Entferne `_ensure_key_with_retry()` 300×1s Loop
- Entferne `KeyCache` → nur noch `AgentKeyCache`
- **Test:** Alte Pool-Einträge ohne `assigned_to` funktionieren als Fallback (least-shared)

---

## 9. Edge Cases

| Fall | Verhalten |
|---|---|
| Agent crashed (kein Release) | Heartbeat-Cleanup nach 5min → `active_consumers` geleert |
| Proxy crashed | `AgentKeyCache` persistiert in `~/.sin-pool/agent-{id}.json` → nach Restart wieder da |
| Key wird von Fireworks suspended | `report_key()` → `suspended=True` → fällt aus `get_key_for_agent()` |
| Alle 259 Keys suspended | `get_key_for_agent()` → None → Proxy 503 → Rotation nötig |
| Agent hat assigned Key aber der ist shared | Sticky greift trotzdem (es ist SEIN Key) |
| Zwei Agents gleicher `agent_id` | Sie teilen sich NATÜRLICH den assigned Key (gewollt: Subagent = gleiche ID) |
| Key-Rotation läuft, neue Keys kommen rein | `assigned_to=None` → werden beim nächsten `agent-key`-Call assigniert |
| Alter Key (ohne `assigned_to` Feld) | Fällt in least-shared Fallback |
| 429 transient von Fireworks | Proxy gibt an Client weiter mit Retry-After (wie bisher) |
| 429 permanent (spending limit) | Key wird suspended, neuer Key via Agent-Key (kein Warten) |

---

## 10. Betroffene Dateien

| Datei | Änderung |
|---|---|
| `agent_toolbox/core/pool_manager.py` | Neue Methoden: `get_key_for_agent()`, `release_key_for_agent()`, `_register_consumer()`, `_cleanup_stale_consumers()`. Neue Felder in `_key_schema`. |
| `agent_toolbox/api/routes/pool.py` | Neue Endpoints: `/agent-key`, `/agent-release`, `/agent-heartbeat`. Backward-Compat-Wrapper für `/lease`, `/return`. |
| `agent_toolbox/api/schemas.py` | Neue Pydantic-Models: `AgentKeyRequest`, `AgentReleaseRequest`, `AgentHeartbeatRequest`. |
| `proxy/pool_client.py` | Neue Methode: `get_agent_key()`, `release_agent_key()`, `agent_heartbeat()`. |
| `proxy/server.py` | `_ensure_key()` ohne Retry-Loop. `x-agent-id` Header-Weiterleitung. `_do_proxy()` nutzt `AgentKeyCache`. |
| `proxy/key_cache.py` | Umbenannt/ersetzt durch `AgentKeyCache` mit `agent_id` + `preferred_key_id` Persistenz. |
| `proxy/config.py` | Neues Feld: `agent_id`. |
| `~/Library/LaunchAgents/com.sinator.pool-proxy-*.plist` | `SIN_AGENT_ID` env-var. |
| `~/.config/opencode/opencode.json` | `x-agent-id` Header für opencode Provider. |

---

## 11. Test-Kriterien

- [ ] 2 parallele opencode Sessions → jeder kriegt eigenen Key (kein Sharing)
- [ ] 3. Session wenn nur 2 Keys verfügbar → 3. kriegt least-shared Key (Sharing)
- [ ] Rotation erzeugt neuen Key → `assigned_to=None` → nächster Agent kriegt ihn
- [ ] Agent-Release → `active_consumers` verringert, Key bleibt `assigned_to`
- [ ] Proxy-Crash → Restart lädt `agent-{id}.json` → Key ist noch da
- [ ] Heartbeat-Cleanup nach 5min Stale → `active_consumers` geleert
- [ ] Alter `/pool/lease` Endpoint funktioniert weiter (Backward-Compat)
- [ ] Key-Suspension (Fireworks 429 permanent) → Agent kriegt sofort Ersatz
- [ ] Kein 5min-Timeout mehr bei vollen Pool
- [ ] Dashboard zeigt neue Metriken: `assigned`, `shared`, `active_consumers`

"""
╔══════════════════════════════════════════════════════════════════════════════╗
║              SINATOR AGENT-TOOLBOX — FastAPI Automation Box                  ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  ZWECK:                                                                      ║
║  Zentrale FastAPI-App die alle SINator-Automatisierungen als REST-Endpunkte   ║
║  bereitstellt. Konsumierbar von anderen Agenten (A2A, MCP, etc.)             ║
║                                                                              ║
║  ARCHITEKTUR:                                                                 ║
║  ┌─────────────────────────────────────────────────────────────────────┐    ║
║  │ FastAPI App (start_toolbox.py)                                      │    ║
║  │ ├── /api/v1/browser/start     → Chrome starten mit Profil-Kopie     │    ║
║  │ ├── /api/v1/browser/stop      → Chrome beenden & Cleanup            │    ║
║  │ ├── /api/v1/browser/status    → Browser-Status prüfen               │    ║
║  │ ├── /api/v1/gmx/session/check → GMX Session prüfen                  │    ║
║  │ ├── /api/v1/gmx/alias/create  → GMX Alias erstellen                 │    ║
║  │ ├── /api/v1/gmx/otp/read      → OTP aus GMX Inbox lesen             │    ║
║  │ ├── /api/v1/fireworks/register → Fireworks Account erstellen        │    ║
║  │ ├── /api/v1/fireworks/confirm  → Fireworks Account bestätigen       │    ║
║  │ ├── /api/v1/fireworks/apikey   → Fireworks API-Key generieren       │    ║
║  │ ├── /api/v1/cookies/extract   → GMX-Cookies extrahieren             │    ║
║  │ ├── /api/v1/cookies/inject    → Cookies in Browser injecten         │    ║
║  │ ├── /api/v1/pool/stats        → API-Key-Pool Status                 │    ║
║  │ ├── /api/v1/pool/add          → API-Key zum Pool hinzufügen         │    ║
║  │ ├── /api/v1/pool/use          → API-Key als verwendet markieren     │    ║
║  │ └── /api/v1/pool/{key_id}     → API-Key aus Pool löschen            │    ║
║  └─────────────────────────────────────────────────────────────────────┘    ║
║                                                                              ║
║  SPEED-OPTIMIERUNG:                                                           ║
║  • Warm Browser Singleton — Browser wird EINMAL gestartet und wiederverwendet ║
║  • Profil-Caching — Kopierte Profile werden gepoolt (kein erneutes Kopieren)  ║
║  • CDP-Connection-Pool — WebSocket-Verbindungen werden gehalten               ║
║                                                                              ║
║  SICHERHEIT:                                                                  ║
║  • Keine Hardcodierten Credentials — alles aus .env oder API-Parametern       ║
║  • Profil-Pfade dynamisch gelöst über profile_name Parameter                  ║
║  • Cookies nur im Memory, nie in Logs                                         ║
║                                                                              ║
║  VORAUSSETZUNGEN:                                                             ║
║  • Python 3.10+                                                               ║
║  • FastAPI, Uvicorn, Playwright, python-dotenv, pydantic                      ║
║  • Google Chrome installiert                                                  ║
║  • GMX-Profil mit aktiver Session (Profile 73)                                ║
║                                                                              ║
║  START:                                                                       ║
║  1. pip install -r requirements.txt                                           ║
║  2. playwright install                                                       ║
║  3. python start_toolbox.py                                                   ║
║  4. Swagger UI: http://localhost:8000/docs                                    ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

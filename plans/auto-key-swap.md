# Auto-Key-Swap bei Rate-Limit — OpenCode Integration

> Issue: https://github.com/SIN-Rotator/SINator-FireworksAI/issues/17

## Flow

```
OpenCode macht API-Call zu Fireworks mit Key fw_xxx
  → Fireworks antwortet 402/429 "rate limit exceeded"
    → OpenCode ruft: POST /api/v1/pool/report {"key_id":"xxx"}
      → Backend markiert Key als used
      → Backend returned neuen Key fw_yyy
    → OpenCode updated ~/.local/share/opencode/auth.json
      → {"fireworks": "fw_yyy"}
    → Nächster API-Call verwendet neuen Key
    → KEIN Session-Neustart nötig
```

## Komponenten

### 1. Backend: POST /api/v1/pool/report
- Input: `{"key_id": "xxx"}` oder `{"api_key": "fw_xxx"}`
- Markiert Key als used
- Holt nächsten verfügbaren Key via get_available_key()
- Returns: `{"status":"success","new_key":"fw_yyy","key_id":"yyy"}`

### 2. CLI Tool: tools/swap_key.sh
- Liest aktuellen Key aus ~/.local/share/opencode/auth.json
- Ruft POST /api/v1/pool/report
- Updated auth.json mit neuem Key
- Kann von OpenCode als Shell-Command aufgerufen werden

### 3. OpenCode Konfiguration
- Provider "fireworks" nutzt @ai-sdk/openai-compatible
- baseURL: https://api.fireworks.ai/inference/v1
- Key wird aus auth.json gelesen

## Usage
```bash
# Manuell: Key tauschen
python tools/swap_key.py

# Auto: OpenCode ruft bei 402-Fehler auf
bash tools/swap_key.sh
```
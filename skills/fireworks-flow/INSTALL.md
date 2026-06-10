# sinator-fireworks-flow — Installation

## Voraussetzungen

- OpenCode (`~/.config/opencode/`)
- SINator-fireworksai Repo geklont unter `/Users/jeremy/dev/SINator-fireworksai/`
- Playwright Browser-Chromium (`playwright install chromium`)
- SIN-Browser-Tools (installiert via `npm i sin_browser_tools`)

## Installation

Keine separate Installation nötig — das Skill ist Teil des Repos.

**In `opencode.json` prüfen (bereits vorhanden):**
```json
{
  "skills": {
    "paths": ["/Users/jeremy/dev/SINator-fireworksai/skills"]
  }
}
```

## Aktivierung

```bash
# Im OpenCode-Chat:
/skill sinator-fireworks-flow
```

## Update

```bash
cd /Users/jeremy/dev/SINator-fireworksai && git pull
```

## Deinstallation

```json
// skills-Eintrag in opencode.json entfernen:
// "/Users/jeremy/dev/SINator-fireworksai/skills"
```

# sinator-gmx-flow — Installation

## Voraussetzungen

- OpenCode (`~/.config/opencode/`)
- SINator-fireworksai Repo geklont unter `/Users/jeremy/dev/SINator-fireworksai/`
- Chrome Profile 73 (simoneschulze) — `/Users/simoneschulze/Library/Application Support/Google Chrome`
- GMX Session-Backup unter `backup/session/gmx-cookies-master.json`

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
/skill sinator-gmx-flow
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

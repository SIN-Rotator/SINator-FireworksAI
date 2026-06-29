#!/bin/bash
# SINator Auto-Key-Generation — checkt Pool-Stats und generiert Keys bei Bedarf
# Wird alle 10 Minuten via LaunchAgent ausgeführt.
#
# Bedingung: available < THRESHOLD → generiere BATCH_SIZE Keys
# Fail-Safe: nur 1 Instanz gleichzeitig (Lockfile)
# Log: /tmp/sinator-auto-gen.log

THRESHOLD=${1:-5}
BATCH_SIZE=${2:-10}
ROTATOR_DIR="$HOME/dev/SINator-Fireworks-Rotator-v2"
LOCKFILE="/tmp/sinator-auto-gen.lock"
LOG="/tmp/sinator-auto-gen.log"

# Lock — nicht parallel ausführen
if [ -f "$LOCKFILE" ]; then
    pid=$(cat "$LOCKFILE" 2>/dev/null)
    if kill -0 "$pid" 2>/dev/null; then
        echo "$(date): Already running (PID $pid), skipping" >> "$LOG"
        exit 0
    fi
fi
echo $$ > "$LOCKFILE"
trap "rm -f $LOCKFILE" EXIT

# Pool-Stats abfragen
available=$(curl -s --max-time 5 http://localhost:8100/api/v1/pool/stats 2>/dev/null | \
    python3 -c "import sys,json; print(json.load(sys.stdin).get('available',0))" 2>/dev/null || echo "0")

echo "$(date): Pool available=$available threshold=$THRESHOLD" >> "$LOG"

if [ "$available" -lt "$THRESHOLD" ] 2>/dev/null; then
    echo "$(date): Below threshold → generating $BATCH_SIZE keys..." >> "$LOG"
    cd "$ROTATOR_DIR"
    python3 -u tools/rotate_sync.py "$BATCH_SIZE" >> "$LOG" 2>&1
    echo "$(date): Generation complete" >> "$LOG"
else
    echo "$(date): Sufficient keys, skipping" >> "$LOG"
fi

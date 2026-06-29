#!/bin/bash
# SINator Log Rotation — begrenzt .err/.log Dateien auf 10MB
# Wird stündlich via LaunchAgent ausgeführt.
set -e

MAX_BYTES=$((10 * 1024 * 1024))  # 10MB

for f in /tmp/pool-proxy-*.err /tmp/pool-proxy-*.log /tmp/sinator-*.log /tmp/sinator-*.err /tmp/pool-router-launchd.log; do
    [ -f "$f" ] || continue
    size=$(stat -f%z "$f" 2>/dev/null || echo 0)
    if [ "$size" -gt "$MAX_BYTES" ]; then
        # Behalte letzte 1000 Zeilen, kürze den Rest
        tmp=$(mktemp)
        tail -1000 "$f" > "$tmp"
        mv "$tmp" "$f"
    fi
done

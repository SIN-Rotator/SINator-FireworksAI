#!/bin/bash
# Restore GMX session cookies from backup
SRC=$(ls -t /opt/sinator-fireworks/backups/gmx-cookies-*.db 2>/dev/null | head -1)
DST="/root/snap/chromium/common/chromium/Default/Cookies"
if [ -z "$SRC" ]; then
    echo "No backup found"
    exit 1
fi
if [ -f "$DST" ]; then
    cp "$DST" "${DST}.bak"
fi
cp "$SRC" "$DST"
chown root:root "$DST"
echo "GMX session restored from $SRC"

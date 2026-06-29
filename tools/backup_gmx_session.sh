#!/bin/bash
# Backup GMX session cookies from Snap Chromium profile
SRC="/root/snap/chromium/common/chromium/Default/Cookies"
DST="/opt/sinator-fireworks/backups/gmx-cookies-$(date +%Y%m%d).db"
if [ -f "$SRC" ]; then
    cp "$SRC" "$DST"
    # Keep only last 3 backups
    ls -t /opt/sinator-fireworks/backups/gmx-cookies-*.db 2>/dev/null | tail -n +4 | xargs rm -f 2>/dev/null
    echo "GMX session backed up to $DST"
else
    echo "No cookies file found at $SRC"
fi

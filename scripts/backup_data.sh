#!/bin/bash
# Back up all git-tracked JSON data files to ~/Backups/hoopsipedia.
# These files embody weeks of rate-limited scraping — re-acquiring them from
# Sports-Reference takes far longer than restoring a tarball.
# Run before any risky pipeline change. Copy the tarball off-machine too.
set -e
cd "$(dirname "$0")/.."
DEST="$HOME/Backups/hoopsipedia"
mkdir -p "$DEST"
STAMP=$(date +%Y-%m-%d)
OUT="$DEST/hoopsipedia-data-$STAMP.tar.gz"
git ls-files '*.json' | tar -czf "$OUT" -T -
COUNT=$(git ls-files '*.json' | wc -l | tr -d ' ')
echo "✅ Backed up $COUNT JSON files to $OUT ($(du -h "$OUT" | cut -f1))"
echo "   Restore a file with: tar -xzf $OUT <file>"

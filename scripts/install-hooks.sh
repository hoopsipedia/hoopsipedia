#!/bin/bash
# Install the repo's git hooks into .git/hooks.
# Run once after cloning: ./scripts/install-hooks.sh
set -e
cd "$(dirname "$0")/.."
cp scripts/hooks/pre-push .git/hooks/pre-push
chmod +x .git/hooks/pre-push
echo "✅ Installed pre-push hook"

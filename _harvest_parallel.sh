#!/bin/zsh
# Parallel harvester: N programs concurrently (default 3 — the rate the domain
# census sustained against archive.org without throttling). Per-file politeness
# is unchanged inside each worker; the win is program-level concurrency.
# Resumable (skips already-harvested) and keeps full tail so tracebacks show.
# Usage: ./_harvest_parallel.sh <keysfile> [workers]
cd /Users/joshdavis/Projects/hoopsipedia
KEYS=${1:?usage: _harvest_parallel.sh <keysfile> [workers]}
W=${2:-3}
tr ' ' '\n' < $KEYS | grep -v '^$' | xargs -P $W -n 1 ./_harvest_worker.sh
echo "PARALLEL_HARVEST COMPLETE"

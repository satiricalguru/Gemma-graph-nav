#!/usr/bin/env bash
# Downloads the official competition data, file by file (disk-safe: only the
# task-named copies, not the hard-linked commit-named duplicates; wheels skipped).
# Competition rules forbid redistribution, so data/ is git-ignored.
#
# Prerequisites (human, once):
#   1. Accept the rules at https://www.kaggle.com/competitions/gemma-4-developer-agent/rules
#   2. Kaggle API token in ~/.kaggle/access_token (chmod 600)
#
# Usage: scripts/get_data.sh [--with-embeddings]
set -euo pipefail
COMP=gemma-4-developer-agent
DEST=data/official
mkdir -p "$DEST"
kg() { uvx --from kaggle kaggle competitions download -c "$COMP" -q "$@"; }

fetch() {  # fetch <remote path>  -> $DEST/<remote path>
  local f=$1 dir="$DEST/$(dirname "$1")"
  [ -s "$DEST/$f" ] && return 0
  mkdir -p "$dir"
  kg -f "$f" -p "$dir"
  local base; base=$(basename "$f")
  if [ -f "$dir/$base.zip" ]; then unzip -o -q "$dir/$base.zip" -d "$dir" && rm "$dir/$base.zip"; fi
}

for f in HARNESS_README.md tasks.jsonl sandbox/setup.py; do fetch "$f"; done
# remote graphs/embeddings are commit-named (<repo_short>_<base_commit>); snapshots are task-named
pairs=$(python3 -c "
import json
for l in open('$DEST/tasks.jsonl'):
    t=json.loads(l); print(t['instance_id'], t['instance_id'].rsplit('_',1)[0]+'_'+t['base_commit'])")
n=0
echo "$pairs" | while read -r id key; do
  fetch "graphs/$key.json"
  fetch "snapshots/$id.tgz" || echo "WARN no snapshot for $id"
  [ "${1:-}" = "--with-embeddings" ] && fetch "embeddings/$key.npz"
  n=$((n+1)); echo "[$n] $id"
done
(cd "$DEST" && shasum -a 256 tasks.jsonl graphs/*.json > SHA256SUMS)
du -sh "$DEST"

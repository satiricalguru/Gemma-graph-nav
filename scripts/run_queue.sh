#!/usr/bin/env bash
# Main LLM experiment queue (E1). Resumable: rerunning skips finished tasks.
set -u
cd "$(dirname "$0")/.."
export GGD_NUM_CTX=${GGD_NUM_CTX:-16384}
for MODEL in ${MODELS:-gemma4:e2b-it-qat gemma4:e4b-mlx gemma4:12b-it-qat}; do
  export GGD_MODEL=$MODEL
  for M in ${METHODS:-mdn gdn agentless no_retrieval}; do
    echo "=== $(date -u +%FT%TZ) $MODEL $M"
    python3 scripts/run_experiment.py --method $M --cv --budget $([ $M = gdn ] && echo 4 || echo 8)
  done
  ollama stop "$MODEL" >/dev/null 2>&1
done
echo "=== DONE $(date -u +%FT%TZ)"

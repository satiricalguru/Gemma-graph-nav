#!/usr/bin/env bash
# Keeps the local 12B queue alive: resumes after crashes, pauses on low disk. Runs are resumable.
cd "$(dirname "$0")/.."
LOG=results/queue_12b.log
for i in $(seq 1 200); do
  grep -q "=== DONE" "$LOG" && { echo "$(date -u +%T) supervisor: done"; exit 0; }
  free=$(df -g ~ | tail -1 | awk '{print $4}')
  if [ "$free" -lt 3 ]; then
    echo "$(date -u +%T) supervisor: low disk ${free}GB, pausing"
    pkill -f run_queue.sh; pkill -f run_experiment.py; ollama stop gemma4:12b-it-qat
    sleep 300; continue
  fi
  if ! pgrep -f "run_queue.sh" >/dev/null; then
    echo "$(date -u +%T) supervisor: (re)starting queue"
    nohup env MODELS="gemma4:12b-it-qat" METHODS="mdn gdn" scripts/run_queue.sh >> "$LOG" 2>&1 &
  fi
  sleep 120
done

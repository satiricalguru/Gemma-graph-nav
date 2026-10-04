#!/usr/bin/env bash
# Records the exact hardware/software environment for the experiment log.
set -euo pipefail
OUT=${1:-results/env/env_$(date -u +%Y%m%dT%H%M%SZ).txt}
mkdir -p "$(dirname "$OUT")"
MODEL=${GGD_MODEL:-gemma4:12b-it-qat}
{
  echo "date_utc: $(date -u +%FT%TZ)"
  echo "chip: $(sysctl -n machdep.cpu.brand_string)"
  echo "mem_bytes: $(sysctl -n hw.memsize)"
  echo "cpu_cores: $(sysctl -n hw.ncpu)"
  echo "gpu: $(system_profiler SPDisplaysDataType 2>/dev/null | awk -F': ' '/Chipset|Total Number of Cores/{printf "%s ", $2}')"
  echo "macos: $(sw_vers -productVersion) ($(sw_vers -buildVersion))"
  echo "python: $(python3 --version 2>&1)"
  echo "ollama_server: $(curl -s localhost:11434/api/version)"
  echo "--- ollama show $MODEL"
  ollama show "$MODEL"
  echo "--- ollama list"
  ollama list
  echo "--- ollama ps"
  ollama ps
} > "$OUT"
echo "wrote $OUT"

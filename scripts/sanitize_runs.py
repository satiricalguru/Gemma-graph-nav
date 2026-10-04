#!/usr/bin/env python3
"""Writes tasks_public.jsonl next to every tasks.jsonl: same per-task metrics/rankings, but
without model transcripts (which quote competition issue text). Only *_public files are committed."""
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
for f in (ROOT / "results/runs").glob("*/*/seed*/tasks.jsonl"):
    out = [json.dumps({k: v for k, v in json.loads(l).items() if k != "transcript"})
           for l in f.read_text().splitlines() if l.strip()]
    (f.parent / "tasks_public.jsonl").write_text("\n".join(out) + "\n")
    print(f.relative_to(ROOT), len(out))

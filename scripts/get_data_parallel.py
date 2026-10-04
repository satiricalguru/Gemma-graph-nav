#!/usr/bin/env python3
"""Parallel version of get_data.sh (same files, same layout). Run after tasks.jsonl exists."""

import json
import subprocess
import sys
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

DEST = Path(__file__).resolve().parents[1] / "data" / "official"
COMP = "gemma-4-developer-agent"


def fetch(rel: str) -> str:
    out = DEST / rel
    if out.exists() and out.stat().st_size > 0:
        return f"skip {rel}"
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.parent / f".tmp_{out.name}"
    tmp.mkdir(exist_ok=True)
    r = subprocess.run(["uvx", "--from", "kaggle", "kaggle", "competitions", "download", "-c", COMP,
                        "-q", "-f", rel, "-p", str(tmp)], capture_output=True, text=True)
    got = list(tmp.iterdir())
    for f in got:
        if f.suffix == ".zip" and f.name == out.name + ".zip":
            with zipfile.ZipFile(f) as z:
                z.extractall(tmp)
            f.unlink()
    src = tmp / out.name
    if src.exists():
        src.rename(out)
    for f in tmp.iterdir():
        f.unlink()
    tmp.rmdir()
    return f"{'ok' if out.exists() else 'FAIL'} {rel} {r.stderr.strip()[-120:] if not out.exists() else ''}"


def main():
    with_emb = "--with-embeddings" in sys.argv
    files = []
    for line in open(DEST / "tasks.jsonl"):
        t = json.loads(line)
        key = t["instance_id"].rsplit("_", 1)[0] + "_" + t["base_commit"]
        files.append(f"graphs/{key}.json")
        if "--with-snapshots" in sys.argv:   # 37-320 MB each; not needed for localization
            files.append(f"snapshots/{t['instance_id']}.tgz")
        if with_emb:
            files.append(f"embeddings/{key}.npz")
    files = list(dict.fromkeys(files))
    with ThreadPoolExecutor(8) as ex:
        for i, msg in enumerate(ex.map(fetch, files)):
            if not msg.startswith("skip"):
                print(f"[{i+1}/{len(files)}] {msg}", flush=True)


if __name__ == "__main__":
    main()

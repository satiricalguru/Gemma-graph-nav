#!/usr/bin/env python3
"""Generates kaggle/kernel_<name>/{run_<name>.py, kernel-metadata.json}: a private Kaggle script that
serves a google/gemma-4 "other" variation (default gemma-4-31b-it-qat-w4a16-ct) with vLLM on L4x4 (official wheelhouse + adk_submission) and
runs scripts/run_experiment.py with GGD_BACKEND=openai. The repo code, tuning files and the
derived label cache are embedded as a base64 tarball (the generated file is git-ignored because
labels derive from competition data).

Usage:
  scripts/make_kaggle_kernel.py --user <kaggle_username> --setup-from <official getting-started .ipynb> \
      [--slug gemma-4-12b-it-qat-w4a16-ct --ver 2 --name 12b]
  uvx --from kaggle kaggle kernels push -p kaggle/kernel_31b
  uvx --from kaggle kaggle kernels output <user>/ggd-delegation-gemma4-31b -p results/kaggle
"""

import argparse
import base64
import io
import json
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EMBED = ["src", "scripts/run_experiment.py", "configs", "results/tuning", "data/cache/labels.jsonl"]
METHODS = [("mdn", 8), ("gdn", 4), ("no_retrieval", 8), ("agentless", 8)]

BODY = '''
import base64, io, tarfile, json, time, urllib.request, os, subprocess, sys
from pathlib import Path
import torch
from adk_submission import VllmConfig, VllmServer

WORK = Path("/kaggle/working/ggd"); WORK.mkdir(parents=True, exist_ok=True)
tarfile.open(fileobj=io.BytesIO(base64.b64decode("{payload}")), mode="r:gz").extractall(WORK)
(WORK / "data").mkdir(exist_ok=True)
off = WORK / "data" / "official"
if not off.exists():
    off.symlink_to("/kaggle/input/competitions/gemma-4-developer-agent")

MODEL_PATH = Path("/kaggle/input/models/google/gemma-4/other/{slug}/{ver}")
gpu_count = torch.cuda.device_count()
cfg = VllmConfig(model=str(MODEL_PATH), port=8000, host="127.0.0.1", tool_call_parser="gemma4",
                 reasoning_parser="gemma4", max_model_len=32768, dtype="bfloat16",
                 gpu_memory_utilization=0.90, enable_auto_tool_choice=True,
                 tensor_parallel_size=4 if gpu_count >= 4 else max(gpu_count, 1), startup_timeout=60 * 20)
server = VllmServer(cfg, adapter_manifest=[])
server.start()
with urllib.request.urlopen("http://127.0.0.1:8000/v1/models") as r:
    served = json.loads(r.read())["data"][0]["id"]
print("served model:", served, "gpus:", gpu_count, flush=True)

env = dict(os.environ, GGD_BACKEND="openai", GGD_OLLAMA_HOST="http://127.0.0.1:8000",
           GGD_MODEL=served, GGD_THINK="false", PYTHONUNBUFFERED="1")
deadline = time.time() + 11 * 3600
for method, budget in {methods}:
    if time.time() > deadline:
        break
    subprocess.run([sys.executable, "scripts/run_experiment.py", "--method", method, "--cv",
                    "--budget", str(budget), "--tag", "{tag}"], cwd=WORK, env=env)
subprocess.run(["tar", "czf", "/kaggle/working/results_{tag}.tgz", "-C", str(WORK), "results/runs"])
print("done")
'''


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", required=True)
    ap.add_argument("--setup-from", required=True, help="official getting-started notebook (.ipynb)")
    ap.add_argument("--slug", default="gemma-4-31b-it-qat-w4a16-ct", help="google/gemma-4 'other' variation")
    ap.add_argument("--ver", default="2")
    ap.add_argument("--name", default="31b", help="short name used in kernel id, tag and output file")
    args = ap.parse_args()
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        for p in EMBED:
            tf.add(ROOT / p, arcname=p, filter=lambda ti: None if "__pycache__" in ti.name else ti)
    nb = json.loads(Path(args.setup_from).read_text())
    setup_cell = "".join(next(c for c in nb["cells"] if c["cell_type"] == "code")["source"])
    script = ("# Gemma 4 31B localization runs (E2) for 'Who Should Walk the Graph?'\n" + setup_cell +
              BODY.replace("{payload}", base64.b64encode(buf.getvalue()).decode())
                  .replace("{methods}", repr(METHODS))
                  .replace("{slug}", args.slug).replace("{ver}", args.ver)
                  .replace("{tag}", f"kaggle{args.name}"))
    out = ROOT / "kaggle" / f"kernel_{args.name}"
    out.mkdir(parents=True, exist_ok=True)
    (out / f"run_{args.name}.py").write_text(script)
    meta = {"id": f"{args.user}/ggd-delegation-gemma4-{args.name}", "title": f"ggd-delegation-gemma4-{args.name}",
            "code_file": f"run_{args.name}.py", "language": "python", "kernel_type": "script",
            "is_private": True, "enable_gpu": True, "enable_tpu": False, "enable_internet": False,
            "dataset_sources": ["metric/gemma-4-developer-agent-wheelhouse"],
            "competition_sources": ["gemma-4-developer-agent"],
            "model_sources": [f"google/gemma-4/Other/{args.slug}/{args.ver}"],
            "kernel_sources": [], "machine_shape": "NvidiaL4",
            # pinned like the official notebook: the wheelhouse is cp312; the latest image is py3.13
            "docker_image": "gcr.io/kaggle-private-byod/python@sha256:37c64f7dd9c54116ecd1bcc88817c5469b88387388fade02bfa8bf3fc647d461"}
    (out / "kernel-metadata.json").write_text(json.dumps(meta, indent=2))
    print(f"wrote {out}/run_{args.name}.py ({len(script)//1024} KB)")


if __name__ == "__main__":
    main()

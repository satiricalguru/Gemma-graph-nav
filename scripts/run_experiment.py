#!/usr/bin/env python3
"""Runs one localization method over the official tasks and logs everything.

  python scripts/run_experiment.py --method apn
  GGD_MODEL=gemma4:e4b-it-qat python scripts/run_experiment.py --method mdn --budget 8
  python scripts/run_experiment.py --method gdn --tau 0.85 --limit 10

Output: results/runs/<method>[_tag]/<model>/seed<seed>/{tasks.jsonl, meta.json}
Resumable: tasks already in tasks.jsonl are skipped.
"""

import argparse
import dataclasses
import json
import platform
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from ggd import methods as M  # noqa: E402
from ggd.apn import APNParams  # noqa: E402
from ggd.data import find, file_sha256, load_labels, load_tasks, official_embeddings, official_graph  # noqa: E402
from ggd.llm import ModelConfig, make_llm  # noqa: E402
from ggd.metrics import acc_at_k, recall_at_k  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
LLM_METHODS = {"mdn", "gdn", "agentless", "no_retrieval"}


def git_commit() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                              text=True).stdout.strip()
    except Exception:
        return "unknown"


def meta(args, cfg: ModelConfig | None) -> dict:
    m = {"method": args.method, "args": vars(args), "git_commit": git_commit(),
         "prompt_version": M.PROMPT_VERSION, "started_utc": time.strftime("%FT%TZ", time.gmtime()),
         "platform": platform.platform(), "machine": platform.machine(),
         "tasks_sha256": file_sha256(find("tasks.jsonl"))}
    if cfg:
        m["model"] = dataclasses.asdict(cfg)
        try:
            with urllib.request.urlopen(f"{cfg.host}/api/version") as r:
                m["ollama_version"] = json.loads(r.read())["version"]
            req = urllib.request.Request(f"{cfg.host}/api/show",
                                         data=json.dumps({"model": cfg.name}).encode())
            with urllib.request.urlopen(req) as r:
                d = json.loads(r.read()).get("details", {})
            m["model_details"] = d
        except Exception as e:
            m["ollama_error"] = str(e)
    return m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--method", required=True,
                    choices=["bm25", "static_graph", "apn", "mdn", "gdn", "agentless", "no_retrieval"])
    ap.add_argument("--budget", type=int, default=8)
    ap.add_argument("--tau", type=float, default=0.85)
    ap.add_argument("--hops", type=int, default=1)
    ap.add_argument("--apn", default="{}", help="JSON overrides for APNParams")
    ap.add_argument("--no-containment", action="store_true")
    ap.add_argument("--repos", default="", help="comma-separated repo filter (owner/name)")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--bm25-search", action="store_true",
                    help="ablation: back search_similar_code with BM25 text search instead of official embeddings")
    ap.add_argument("--tag", default="")
    ap.add_argument("--cv", action="store_true",
                    help="use leave-one-repo-out APN params and gate tau (results/tuning/*.json)")
    args = ap.parse_args()

    cfg = ModelConfig.load() if args.method in LLM_METHODS else None
    llm = make_llm(cfg) if cfg else None
    labels = load_labels()
    tasks = load_tasks()
    if args.repos:
        keep = set(args.repos.split(","))
        tasks = [t for t in tasks if t["repo"] in keep]
    if args.limit:
        tasks = tasks[: args.limit]
    model_dir = cfg.name.replace(":", "_").replace("/", "_") if cfg else "no_llm"
    seed = cfg.seed if cfg else 0
    out_dir = ROOT / "results" / "runs" / (args.method + (f"_{args.tag}" if args.tag else "")) \
        / model_dir / f"seed{seed}"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "meta.json").write_text(json.dumps(meta(args, cfg), indent=2))
    out = out_dir / "tasks.jsonl"
    done = {json.loads(l)["instance_id"] for l in out.read_text().splitlines()} if out.exists() else set()
    params = APNParams(**json.loads(args.apn))
    FOLD = {"fastapi/fastapi": "fastapi", "Textualize/rich": "rich",
            "psf/requests": "requests+httpx", "encode/httpx": "requests+httpx"}
    if args.cv:
        apn_cv = json.loads((ROOT / "results/tuning/apn_cv.json").read_text())
        gate_cv = json.loads((ROOT / "results/tuning/gate_cv.json").read_text())["tau"]

    for i, t in enumerate(tasks):
        iid = t["instance_id"]
        if iid in done:
            continue
        lab = labels[iid]
        gold = lab["gold_symbols"]
        if not gold:            # module-level-only tasks are excluded from scoring
            continue
        g = official_graph(iid)
        if not args.no_containment:
            g.add_containment()
        tau = args.tau
        if args.cv:
            f = FOLD[t["repo"]]
            params = APNParams(**{**json.loads(args.apn), **apn_cv[f]["params"]})
            tau = gate_cv[f]["tau"]
        apn = M.make_apn(g, params)
        emb = official_embeddings(iid) if args.method in ("mdn", "gdn") and not args.bm25_search else None
        issue = t["problem_statement"] + ("\n\nHints:\n" + t["hints_text"] if t.get("hints_text") else "")
        run = {"bm25": lambda: M.run_bm25(g, issue, apn),
               "static_graph": lambda: M.run_static_graph(g, issue, apn, hops=args.hops),
               "apn": lambda: M.run_apn(g, issue, apn),
               "mdn": lambda: M.run_mdn(g, issue, apn, llm, budget=args.budget, emb=emb),
               "gdn": lambda: M.run_gdn(g, issue, apn, llm, tau=tau, budget=args.budget, emb=emb),
               "agentless": lambda: M.run_agentless(g, issue, apn, llm),
               "no_retrieval": lambda: M.run_no_retrieval(g, issue, apn, llm)}[args.method]
        try:
            r = run()
            err = None
        except Exception as e:  # logged, never silently dropped
            r, err = M.Result(args.method, []), repr(e)
        rec = dataclasses.asdict(r)
        rec.update({"instance_id": iid, "repo": t["repo"], "gold": gold, "error": err,
                    "gold_in_graph": lab["gold_in_official_graph"]})
        for k in (1, 3, 5, 10):
            rec[f"R@{k}"] = recall_at_k(r.ranked, gold, k)
            rec[f"Acc@{k}"] = acc_at_k(r.ranked, gold, k)
        rec["ranked"] = r.ranked[:50]
        with open(out, "a") as f:
            f.write(json.dumps(rec) + "\n")
        print(f"[{i+1}/{len(tasks)}] {iid} R@5={rec['R@5']} calls={r.llm_calls} "
              f"tools={r.tool_calls} stop={r.stop} {r.wall_s:.1f}s" + (f" ERR {err}" if err else ""),
              flush=True)


if __name__ == "__main__":
    main()

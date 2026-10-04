#!/usr/bin/env python3
"""Leave-one-repo-out CV for APN parameters (alpha, beta, lam) and the gate threshold input.

Folds: fastapi | rich | requests+httpx. For each fold the grid point with the best mean R@5
on the OTHER folds is applied to the held-out fold. Outputs:
  results/tuning/apn_cv.json        chosen params per fold + held-out R@5
  results/runs/apn_cv/no_llm/seed0/tasks.jsonl   held-out rankings (used as the APN of record)
"""

import itertools
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from ggd.apn import APN, APNParams  # noqa: E402
from ggd.data import load_labels, load_tasks, official_graph  # noqa: E402
from ggd.metrics import acc_at_k, recall_at_k  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
FOLD = {"fastapi/fastapi": "fastapi", "Textualize/rich": "rich",
        "psf/requests": "requests+httpx", "encode/httpx": "requests+httpx"}
GRID = {"alpha": [0.15, 0.3, 0.5], "beta": [0.25, 0.5, 1.0, 2.0], "lam": [0.2, 0.35, 0.5, 0.7, 0.85]}


def issue_of(t):
    return t["problem_statement"] + ("\n\nHints:\n" + t["hints_text"] if t.get("hints_text") else "")


def main():
    labels = load_labels()
    tasks = [t for t in load_tasks() if labels[t["instance_id"]]["gold_symbols"]]
    combos = list(itertools.product(GRID["alpha"], GRID["beta"], GRID["lam"]))
    score = {c: {} for c in combos}          # combo -> iid -> R@5
    rank_store = {c: {} for c in combos}
    t0 = time.time()
    for i, t in enumerate(tasks):
        iid = t["instance_id"]
        g = official_graph(iid)
        g.add_containment()
        apn = APN(g)
        gold = labels[iid]["gold_symbols"]
        for c in combos:
            apn.p.alpha, apn.p.beta, apn.p.lam = c
            r = apn.rank(issue_of(t))
            score[c][iid] = recall_at_k(r.ranked, gold, 5)
            rank_store[c][iid] = (r.ranked, r.uncertainty, r.n_anchors)
        print(f"[{i+1}/{len(tasks)}] {iid} {time.time()-t0:.0f}s", flush=True)

    folds = sorted(set(FOLD.values()))
    out, held = {}, []
    for f in folds:
        train = [t["instance_id"] for t in tasks if FOLD[t["repo"]] != f]
        test = [t for t in tasks if FOLD[t["repo"]] == f]
        best = max(combos, key=lambda c: sum(score[c][k] for k in train) / len(train))
        out[f] = {"params": dict(zip(GRID, best)),
                  "train_R@5": sum(score[best][k] for k in train) / len(train),
                  "heldout_R@5": sum(score[best][t["instance_id"]] for t in test) / len(test),
                  "n_test": len(test)}
        for t in test:
            iid = t["instance_id"]
            ranked, u, na = rank_store[best][iid]
            gold = labels[iid]["gold_symbols"]
            rec = {"method": "apn_cv", "instance_id": iid, "repo": t["repo"], "gold": gold,
                   "ranked": ranked[:50], "uncertainty": u, "n_anchors": na, "fold": f,
                   "params": out[f]["params"], "llm_calls": 0, "tool_calls": 0,
                   "invalid_tool_calls": 0, "prompt_tokens": 0, "context_chars": 0,
                   "wall_s": 0.0, "gate_open": None, "error": None}
            for k in (1, 3, 5, 10):
                rec[f"R@{k}"] = recall_at_k(ranked, gold, k)
                rec[f"Acc@{k}"] = acc_at_k(ranked, gold, k)
            held.append(rec)
    allc = {f"{a}/{b}/{l}": sum(score[(a, b, l)].values()) / len(tasks) for a, b, l in combos}
    out["grid_mean_R@5_all_tasks(in-sample, for sensitivity only)"] = allc
    (ROOT / "results" / "tuning").mkdir(parents=True, exist_ok=True)
    (ROOT / "results" / "tuning" / "apn_cv.json").write_text(json.dumps(out, indent=2))
    d = ROOT / "results" / "runs" / "apn_cv" / "no_llm" / "seed0"
    d.mkdir(parents=True, exist_ok=True)
    (d / "tasks.jsonl").write_text("\n".join(json.dumps(r) for r in held) + "\n")
    print(json.dumps({k: v for k, v in out.items() if not k.startswith("grid")}, indent=2))
    print("CV R@5 overall:", sum(r["R@5"] for r in held) / len(held))


if __name__ == "__main__":
    main()

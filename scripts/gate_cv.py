#!/usr/bin/env python3
"""H3 (does APN uncertainty predict APN failure?) and per-fold gate threshold tau.

Failure := APN held-out R@5 == 0. tau for fold f maximises Youden's J (TPR - FPR) of
`u >= tau` as a failure detector on the other folds. AUROC reported on all held-out tasks
(u is computed with each task's held-out APN params, so no tuning leakage into u itself).
Also reports AUROC of a simpler signal (no anchor matched) for comparison.
"""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from ggd.stats import auroc  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
recs = [json.loads(l) for l in (ROOT / "results/runs/apn_cv/no_llm/seed0/tasks.jsonl").read_text().splitlines()]
fail = [int(r["R@5"] == 0) for r in recs]
u = [r["uncertainty"] for r in recs]
out = {"n": len(recs), "apn_failure_rate": sum(fail) / len(fail),
       "auroc_uncertainty": auroc(u, fail),
       "auroc_no_anchor": auroc([float(r["n_anchors"] == 0) for r in recs], fail), "tau": {}}
for f in sorted({r["fold"] for r in recs}):
    tr = [(x, y) for x, y, r in zip(u, fail, recs) if r["fold"] != f]
    def j(t):
        tp = sum(1 for x, y in tr if y and x >= t); fn = sum(1 for x, y in tr if y and x < t)
        fp = sum(1 for x, y in tr if not y and x >= t); tn = sum(1 for x, y in tr if not y and x < t)
        return tp / max(tp + fn, 1) - fp / max(fp + tn, 1)
    cands = sorted({x for x, _ in tr})
    best = max(cands, key=j)
    te = [(x, y) for x, y, r in zip(u, fail, recs) if r["fold"] == f]
    out["tau"][f] = {"tau": best, "train_J": j(best),
                     "heldout_gate_open_rate": sum(x >= best for x, _ in te) / len(te)}
(ROOT / "results/tuning/gate_cv.json").write_text(json.dumps(out, indent=2))
print(json.dumps(out, indent=2))

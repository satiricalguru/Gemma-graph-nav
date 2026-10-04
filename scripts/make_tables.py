#!/usr/bin/env python3
"""Regenerates every results table from results/runs/**/tasks.jsonl.

Writes results/tables/main.csv and results/tables/main.md, plus paired comparisons
against APN (bootstrap clustered by repo, McNemar on Acc@5, Holm-corrected).
Only tasks with at least one gold symbol are scored; the count is printed.
"""

import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from ggd.stats import holm, mcnemar, mean, paired_bootstrap  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def load_runs():
    runs = {}
    for f in sorted((ROOT / "results" / "runs").glob("*/*/seed*/tasks*.jsonl")):
        method, model, seed = f.parts[-4], f.parts[-3], f.parts[-2]
        recs = [json.loads(l) for l in f.read_text().splitlines() if l.strip()]
        runs[(method, model, seed)] = {r["instance_id"]: r for r in recs if r["gold"]}
    return runs


def main():
    runs = load_runs()
    if not runs:
        sys.exit("no runs found")
    rows = []
    for (method, model, seed), recs in runs.items():
        rs = list(recs.values())
        rows.append({
            "method": method, "model": model, "seed": seed, "n": len(rs),
            **{m: round(mean(r[m] for r in rs), 4) for m in ("R@1", "R@5", "R@10", "Acc@5")},
            "llm_calls": round(mean(r["llm_calls"] for r in rs), 2),
            "tool_calls": round(mean(r["tool_calls"] for r in rs), 2),
            "invalid_tool_calls": round(mean(r["invalid_tool_calls"] for r in rs), 2),
            "prefill_tokens": round(mean(r["prompt_tokens"] for r in rs)),
            "context_chars": round(mean(r.get("context_chars", 0) for r in rs)),
            "wall_s": round(mean(r["wall_s"] for r in rs), 1),
            "gate_open_rate": (round(mean(float(r["gate_open"]) for r in rs if r["gate_open"] is not None), 3)
                               if any(r["gate_open"] is not None for r in rs) else ""),
            "errors": sum(1 for r in rs if r.get("error")),
        })
    out = ROOT / "results" / "tables"
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "main.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    cols = list(rows[0])
    md = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    md += ["| " + " | ".join(str(r[c]) for c in cols) + " |" for r in rows]

    # paired comparisons vs APN (APN is LLM-free, so one run serves every model)
    # reference = leave-one-repo-out tuned APN (falls back to default-parameter APN)
    apn = next((v for (m, _, _), v in runs.items() if m == "apn_cv"), None) or \
        next((v for (m, _, _), v in runs.items() if m == "apn"), None)
    if apn:
        comps, pv = [], {}
        for (method, model, seed), recs in runs.items():
            if method in ("apn", "apn_cv"):
                continue
            a = {k: r["R@5"] for k, r in apn.items()}
            b = {k: r["R@5"] for k, r in recs.items()}
            grp = {k: r["repo"] for k, r in recs.items()}
            bs = paired_bootstrap(a, b, grp)
            mc = mcnemar({k: r["Acc@5"] for k, r in apn.items()}, {k: r["Acc@5"] for k, r in recs.items()})
            key = f"{method}|{model}|{seed}"
            pv[key] = bs["p_two_sided"]
            comps.append((key, bs, mc))
        adj = holm(pv)
        md += ["", "Paired vs APN-CV on R@5 (method − APN-CV; 95% CI from repo-clustered bootstrap; Holm-adjusted p)",
               "| comparison | n | ΔR@5 | 95% CI | p_holm | McNemar Acc@5 (wins/losses, p) |", "|---|---|---|---|---|---|"]
        for key, bs, mc in comps:
            md.append(f"| {key} | {bs['n']} | {bs['delta']:+.3f} | [{bs['ci95'][0]:+.3f}, {bs['ci95'][1]:+.3f}] "
                      f"| {adj[key]:.3g} | {mc['b_wins']}/{mc['a_wins']}, p={mc['p_exact']:.3g} |")
    (out / "main.md").write_text("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()

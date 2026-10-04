#!/usr/bin/env python3
"""Failure taxonomy + navigation behaviour for LLM runs, and per-anchor-status slices.
Writes results/tables/analysis.json and analysis.md. Auto-labelled from logs (no hand labels)."""
import json, sys
from collections import Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from ggd.stats import mean, paired_bootstrap  # noqa: E402
ROOT = Path(__file__).resolve().parents[1]
lab = {d["instance_id"]: d for d in map(json.loads, (ROOT / "data/cache/labels.jsonl").read_text().splitlines())}
apn = {r["instance_id"]: r for r in map(json.loads, (ROOT / "results/runs/apn_cv/no_llm/seed0/tasks_public.jsonl").read_text().splitlines())}
out, md = {}, []
for f in sorted((ROOT / "results/runs").glob("*/gemma4_*/seed*/tasks_public.jsonl")):
    m, model = f.parts[-4], f.parts[-3]
    rs = [json.loads(l) for l in f.read_text().splitlines() if l.strip()]
    rs = [r for r in rs if r["gold"]]
    if not rs:
        continue
    fail = Counter()
    for r in rs:
        if r["R@5"] and r["R@5"] > 0:
            continue
        L = lab[r["instance_id"]]
        gold = r["gold"]
        if not any(g in L["gold_in_official_graph"] for g in gold):
            fail["gold_not_in_graph"] += 1
        elif r.get("stop") in ("invalid_calls",) or (r["invalid_tool_calls"] and r["tool_calls"] and r["invalid_tool_calls"] >= r["tool_calls"] / 2):
            fail["tool_misuse"] += 1
        elif r.get("stop") in ("budget", "final_empty"):
            fail["budget_or_empty_final"] += 1
        elif any(g in r.get("visited", []) for g in gold):
            fail["visited_gold_but_not_ranked"] += 1
        elif L["n_anchors"] == 0:
            fail["no_anchor_wrong_start"] += 1
        else:
            fail["never_reached_gold"] += 1
    anch = [r for r in rs if lab[r["instance_id"]]["n_anchors"] > 0]
    noan = [r for r in rs if lab[r["instance_id"]]["n_anchors"] == 0]
    sl = {}
    for name, sub in (("anchored", anch), ("no_anchor", noan)):
        ks = {r["instance_id"] for r in sub}
        bs = paired_bootstrap({k: apn[k]["R@5"] for k in ks}, {r["instance_id"]: r["R@5"] for r in sub})
        sl[name] = {"n": len(sub), "R@5": mean(r["R@5"] for r in sub),
                    "APN_R@5": mean(apn[k]["R@5"] for k in ks), "delta_vs_apn": bs["delta"], "ci95": bs["ci95"]}
    beh = {"zero_tool_call_rate": mean(float(r["tool_calls"] == 0) for r in rs),
           "mean_tool_calls": mean(r["tool_calls"] for r in rs),
           "invalid_call_rate": sum(r["invalid_tool_calls"] for r in rs) / max(sum(r["tool_calls"] for r in rs), 1),
           "stop_reasons": dict(Counter(r.get("stop") for r in rs)),
           "tool_mix": dict(Counter(c["function"]["name"] for r in rs for t in r.get("transcript", []) for c in t.get("tool_calls", []) or [])) or "see private logs"}
    out[f"{m}|{model}"] = {"failures_R@5=0": dict(fail), "n_fail": sum(fail.values()), "behaviour": beh, "slices": sl}
(ROOT / "results/tables/analysis.json").write_text(json.dumps(out, indent=2))
for k, v in out.items():
    md.append(f"## {k}\n- failures: {v['failures_R@5=0']}\n- behaviour: {json.dumps(v['behaviour'])}\n- slices: {json.dumps(v['slices'])}\n")
(ROOT / "results/tables/analysis.md").write_text("\n".join(md))
print("\n".join(md))

#!/usr/bin/env python3
"""Builds gold labels + the official-graph audit (experiment E7). No LLM calls.

For every task:
  * extract the snapshot, derive gold symbols from `patch` (ggd.labels)
  * check which gold symbols exist as nodes in the official graph
  * hop distance (undirected, official edges only) from issue anchors to gold
  * rebuild the graph with our builder and measure node/edge agreement with the official one
Writes data/cache/labels.jsonl (derived from competition data: not committed) and
results/audit/graph_audit.json (aggregate statistics only).
"""

import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from ggd.data import CACHE, labels_path, load_tasks, official_graph, snapshot  # noqa: E402
from ggd.graph import CodeGraph  # noqa: E402
from ggd.labels import gold_symbols  # noqa: E402
from ggd.lexical import anchors  # noqa: E402
from ggd.metrics import hop_distances  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def main():
    tasks = load_tasks()
    CACHE.mkdir(parents=True, exist_ok=True)
    rows, agg = [], Counter()
    for i, t in enumerate(tasks):
        iid = t["instance_id"]
        og = official_graph(iid)
        with snapshot(iid) as root:
            gold = gold_symbols(t["patch"], root)
            rg = CodeGraph.from_repo(root)
            files = {n.file for n in rg.nodes.values()}
            node_file = {nid: n.file for nid, n in rg.nodes.items()}
        sym = gold["functions"] + gold["classes"]
        in_official = [s for s in sym if s in og.nodes]
        issue = t["problem_statement"] + "\n" + (t.get("hints_text") or "")
        s0 = anchors(og, issue)
        d = hop_distances(og, list(s0), max_hops=8)
        on, rn = set(og.nodes), set(rg.nodes)
        oe = {(a, b) for a, es in og.out.items() for b, _ in es}
        re_ = {(a, b) for a, es in rg.out.items() for b, _ in es}
        row = {
            "instance_id": iid, "repo": t["repo"], "created_at": t.get("created_at"),
            "gold": gold, "gold_symbols": sym, "gold_in_official_graph": in_official,
            "gold_files_in_rebuilt": [f for f in gold["files"] if f in files],
            "node_file": {s: node_file.get(s) for s in sym},
            "n_anchors": len(s0), "hops_anchor_to_gold": {s: d.get(s) for s in in_official},
            "official": {"nodes": len(on), "edges": og.n_edges(), "edge_types": og.edge_types()},
            "rebuilt_vs_official": {
                "node_jaccard": len(on & rn) / max(len(on | rn), 1),
                "official_nodes_recovered": len(on & rn) / max(len(on), 1),
                "official_edges_recovered": len(oe & re_) / max(len(oe), 1)},
        }
        rows.append(row)
        agg["tasks"] += 1
        agg["module_only"] += int(not sym)
        agg["gold_syms"] += len(sym)
        agg["gold_syms_in_graph"] += len(in_official)
        print(f"[{i+1}/{len(tasks)}] {iid}: gold={len(sym)} in_graph={len(in_official)} "
              f"anchors={len(s0)} hops={list(row['hops_anchor_to_gold'].values())}", flush=True)
    labels_path().write_text("\n".join(json.dumps(r) for r in rows) + "\n")

    hops = Counter()
    for r in rows:
        for h in r["hops_anchor_to_gold"].values():
            hops["unreachable(>8) or no anchor" if h is None else str(h)] += 1
    edge_types = Counter()
    for r in rows:
        edge_types.update(r["official"]["edge_types"])
    summary = {
        "n_tasks": agg["tasks"], "tasks_module_level_only": agg["module_only"],
        "gold_symbols": agg["gold_syms"],
        "gold_symbols_present_in_official_graph": agg["gold_syms_in_graph"],
        "tasks_with_no_anchor": sum(r["n_anchors"] == 0 for r in rows),
        "hop_distance_histogram": dict(sorted(hops.items())),
        "official_edge_types_total": dict(edge_types),
        "rebuilt_mean_node_jaccard": sum(r["rebuilt_vs_official"]["node_jaccard"] for r in rows) / len(rows),
        "rebuilt_mean_edge_recovery": sum(r["rebuilt_vs_official"]["official_edges_recovered"] for r in rows) / len(rows),
        "per_repo_tasks": dict(Counter(r["repo"] for r in rows)),
    }
    out = ROOT / "results" / "audit" / "graph_audit.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

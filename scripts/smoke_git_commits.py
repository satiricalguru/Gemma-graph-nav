#!/usr/bin/env python3
"""Pipeline smoke test on public git history (NOT an experiment).

For each commit: check out its parent, build the graph, derive gold symbols from the
commit's source diff, rank with APN/BM25 using the commit message as a stand-in issue.
Commit messages are much more informative than real issues, so these numbers say
nothing about method quality. They only check that the pipeline runs end to end.

Usage: scripts/smoke_git_commits.py <repo_dir> <sha> [<sha> ...]
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from ggd.apn import APN  # noqa: E402
from ggd.graph import CodeGraph  # noqa: E402
from ggd.labels import gold_symbols  # noqa: E402
from ggd.metrics import hop_distances, recall_at_k  # noqa: E402


def sh(cmd, cwd):
    return subprocess.run(cmd, cwd=cwd, shell=True, check=True, capture_output=True,
                          text=True).stdout


def main():
    repo, shas = Path(sys.argv[1]), sys.argv[2:]
    for sha in shas:
        msg = sh(f"git log -1 --format=%B {sha}", repo)
        patch = sh(f"git diff {sha}^ {sha} -- . ':(exclude)tests'", repo)
        with tempfile.TemporaryDirectory() as wt:
            sh(f"git worktree add -q --detach {wt} {sha}^", repo)
            try:
                g = CodeGraph.from_repo(wt)
                g.add_containment()
                gold = gold_symbols(patch, wt)
                apn = APN(g)
                r = apn.rank(msg)
                bm = sorted(apn.bm25.scores(msg).items(), key=lambda x: -x[1])
                bm_rank = [n for n, _ in bm if g.nodes[n].kind != "module"]
                d = hop_distances(g, r.debug["anchors"])
                print(json.dumps({
                    "sha": sha[:8], "subject": msg.splitlines()[0][:70],
                    "nodes": len(g.nodes), "edges": g.edge_types(),
                    "gold": gold["functions"] + gold["classes"],
                    "gold_modules": gold["modules"],
                    "anchors": r.debug["anchors"][:5],
                    "apn_top5": r.ranked[:5], "u": round(r.uncertainty, 3),
                    "apn_R@5": recall_at_k(r.ranked, gold["functions"] + gold["classes"], 5),
                    "bm25_R@5": recall_at_k(bm_rank, gold["functions"] + gold["classes"], 5),
                    "hops_anchor_to_gold": {x: d.get(x) for x in gold["functions"]},
                }, indent=1))
            finally:
                sh(f"git worktree remove --force {wt}", repo)


if __name__ == "__main__":
    main()

"""APN: algorithmic navigation = lexically anchored personalized PageRank.

  pi = alpha * s + (1 - alpha) * W^T pi        (W: row-normalised, symmetrised, type-weighted)
  s  = normalize(s0 + beta * bm25_topM)
  r(v) = lam * z(pi_v) + (1 - lam) * z(bm25_v)

Zero LLM calls. Also exposes the uncertainty u used by the delegation gate.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field

from .graph import CodeGraph
from .lexical import BM25, anchors, node_doc

CANDIDATE_KINDS = {"function", "method", "class", "unknown"}


def is_test_id(nid: str) -> bool:
    parts = nid.split(".")
    return any(p in ("tests", "test", "testing", "conftest") or p.startswith("test_")
               or p.endswith("_test") for p in parts)


def is_candidate(g: CodeGraph, nid: str) -> bool:
    return g.nodes[nid].kind in CANDIDATE_KINDS and not is_test_id(nid)


@dataclass
class APNParams:
    alpha: float = 0.25                 # restart probability
    beta: float = 0.5                   # weight of BM25 seeds relative to identifier anchors
    lam: float = 0.5                    # PPR vs BM25 in the final score
    bm25_seed_top: int = 20
    iters: int = 50
    edge_w: dict[str, float] = field(default_factory=lambda: {
        "calls": 1.0, "imports": 0.3, "inherits": 1.0, "contains": 0.7})
    default_edge_w: float = 0.5
    gate_k: int = 10                    # K used for the uncertainty statistic


@dataclass
class Ranking:
    ranked: list[str]
    scores: dict[str, float]
    uncertainty: float
    n_anchors: int
    debug: dict = field(default_factory=dict)


class APN:
    def __init__(self, g: CodeGraph, params: APNParams | None = None):
        self.g, self.p = g, params or APNParams()
        self.bm25 = BM25({nid: node_doc(g, nid) for nid in g.nodes})
        self.adj = self._adjacency()

    def _adjacency(self):
        adj: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
        for s, es in self.g.out.items():
            for d, t in es:
                w = self.p.edge_w.get(t, self.p.default_edge_w)
                adj[s][d] += w
                adj[d][s] += w
        norm = {}
        for s, nb in adj.items():
            tot = sum(nb.values())
            norm[s] = {d: w / tot for d, w in nb.items()}
        return norm

    def ppr(self, seed: dict[str, float]) -> dict[str, float]:
        z = sum(seed.values())
        if z <= 0:
            return {}
        s = {k: v / z for k, v in seed.items()}
        pi = dict(s)
        a = self.p.alpha
        for _ in range(self.p.iters):
            nxt: dict[str, float] = defaultdict(float)
            dangling = 0.0
            for u, m in pi.items():
                nb = self.adj.get(u)
                if not nb:
                    dangling += m
                    continue
                for v, w in nb.items():
                    nxt[v] += (1 - a) * m * w
            for k, v in s.items():
                nxt[k] += (a + (1 - a) * dangling) * v
            pi = nxt
        return pi

    def rank(self, issue: str, k: int = 50) -> Ranking:
        s0 = anchors(self.g, issue)
        bm = self.bm25.scores(issue)
        top_bm = sorted(bm.items(), key=lambda x: -x[1])[: self.p.bm25_seed_top]
        seed: dict[str, float] = defaultdict(float)
        z0 = sum(s0.values()) or 1.0
        for nid, w in s0.items():
            seed[nid] += w / z0
        zb = sum(w for _, w in top_bm) or 1.0
        for nid, w in top_bm:
            seed[nid] += self.p.beta * w / zb
        pi = self.ppr(seed)
        cands = [n for n in self.g.nodes if is_candidate(self.g, n)]
        zp, zb2 = _zscore({c: pi.get(c, 0.0) for c in cands}), _zscore({c: bm.get(c, 0.0) for c in cands})
        r = {c: self.p.lam * zp[c] + (1 - self.p.lam) * zb2[c] for c in cands}
        ranked = sorted(cands, key=lambda c: -r[c])[:k]
        u = normalized_entropy([r[c] for c in ranked[: self.p.gate_k]])
        if not s0:
            u = 1.0
        return Ranking(ranked, {c: r[c] for c in ranked}, u, len(s0),
                       {"anchors": sorted(s0, key=lambda x: -s0[x])[:10]})


def _zscore(d: dict[str, float]) -> dict[str, float]:
    if not d:
        return {}
    vals = list(d.values())
    mu = sum(vals) / len(vals)
    sd = math.sqrt(sum((v - mu) ** 2 for v in vals) / len(vals)) or 1.0
    return {k: (v - mu) / sd for k, v in d.items()}


def normalized_entropy(scores: list[float]) -> float:
    """Entropy of the top-K score mass after shifting to be positive; 1 = flat, 0 = peaked."""
    if len(scores) < 2:
        return 0.0
    lo = min(scores)
    w = [s - lo + 1e-9 for s in scores]
    z = sum(w)
    p = [x / z for x in w]
    return -sum(x * math.log(x) for x in p if x > 0) / math.log(len(p))

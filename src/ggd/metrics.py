"""Localization metrics and graph-reachability audit."""

from __future__ import annotations

from collections import deque

from .graph import CodeGraph


def recall_at_k(ranked: list[str], gold: list[str], k: int) -> float | None:
    if not gold:
        return None
    top = set(ranked[:k])
    return sum(g in top for g in gold) / len(gold)


def acc_at_k(ranked: list[str], gold: list[str], k: int) -> float | None:
    if not gold:
        return None
    return float(set(gold) <= set(ranked[:k]))


def file_ranking(ranked_nodes: list[str], node_file: dict[str, str]) -> list[str]:
    out: list[str] = []
    for n in ranked_nodes:
        f = node_file.get(n)
        if f and f not in out:
            out.append(f)
    return out


def hop_distances(g: CodeGraph, sources: list[str], max_hops: int = 6,
                  types: set[str] | None = None) -> dict[str, int]:
    """Undirected BFS distance from any source node."""
    dist = {s: 0 for s in sources if s in g.nodes}
    q = deque(dist)
    while q:
        u = q.popleft()
        if dist[u] >= max_hops:
            continue
        for v, _, _ in g.neighbors(u, types):
            if v not in dist:
                dist[v] = dist[u] + 1
                q.append(v)
    return dist

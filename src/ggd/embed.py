"""Replica of the harness's `search_similar_code` over the official .npz embeddings.

The harness has no query encoder: it resolves the query string to an existing node key
(exact -> '.'/'/' suffix -> case-insensitive -> substring) and returns the nodes whose
embeddings have the highest cosine similarity to that node's embedding.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np


def resolve_name(query: str, keys: list[str]) -> str | None:
    q = (query or "").strip()
    if not q:
        return None
    if q in keys:
        return q
    suf = [k for k in keys if k.endswith("." + q) or k.endswith("/" + q)]
    if suf:
        return min(suf, key=len)
    ql = q.lower()
    ci = [k for k in keys if k.lower() == ql or k.lower().endswith("." + ql)]
    if ci:
        return min(ci, key=len)
    sub = [k for k in keys if ql in k.lower()]
    return min(sub, key=len) if sub else None


class EmbeddingIndex:
    def __init__(self, keys: list[str], mat: np.ndarray):
        self.keys = keys
        n = np.linalg.norm(mat, axis=1, keepdims=True)
        self.mat = mat / np.where(n == 0, 1, n)
        self.pos = {k: i for i, k in enumerate(keys)}

    @classmethod
    def load(cls, path: str | Path) -> "EmbeddingIndex":
        z = np.load(path)
        keys = list(z.files)
        return cls(keys, np.stack([z[k].astype(np.float32).ravel() for k in keys]))

    def similar(self, query: str, k: int = 10) -> list[tuple[str, float]]:
        key = resolve_name(query, self.keys)
        if key is None:
            return []
        sims = self.mat @ self.mat[self.pos[key]]
        order = np.argsort(-sims)
        return [(self.keys[i], float(sims[i])) for i in order[: k + 1] if self.keys[i] != key][:k]

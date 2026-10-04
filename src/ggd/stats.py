"""Paired statistics for task-level comparisons (stdlib only, seeded)."""

from __future__ import annotations

import math
import random
from collections import defaultdict


def mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else float("nan")


def paired_bootstrap(a: dict[str, float], b: dict[str, float], groups: dict[str, str] | None = None,
                     n: int = 10000, seed: int = 0) -> dict:
    """CI for mean(b - a) over shared tasks; resamples whole groups (repos) if given."""
    keys = sorted(k for k in a if k in b and a[k] is not None and b[k] is not None)
    diff = {k: b[k] - a[k] for k in keys}
    rng = random.Random(seed)
    if groups:
        by_g = defaultdict(list)
        for k in keys:
            by_g[groups[k]].append(k)
        gl = list(by_g.values())
        def draw():
            ks = [k for grp in (rng.choice(gl) for _ in gl) for k in rng.choices(grp, k=len(grp))]
            return mean(diff[k] for k in ks)
    else:
        def draw():
            return mean(diff[k] for k in rng.choices(keys, k=len(keys)))
    boots = sorted(draw() for _ in range(n))
    return {"n": len(keys), "delta": mean(diff.values()),
            "ci95": (boots[int(0.025 * n)], boots[int(0.975 * n) - 1]),
            "p_two_sided": min(1.0, 2 * min(sum(x <= 0 for x in boots), sum(x >= 0 for x in boots)) / n)}


def mcnemar(a: dict[str, float], b: dict[str, float]) -> dict:
    """Exact McNemar test on binary outcomes (e.g. Acc@5)."""
    keys = [k for k in a if k in b and a[k] is not None and b[k] is not None]
    n01 = sum(1 for k in keys if a[k] < 0.5 <= b[k])
    n10 = sum(1 for k in keys if b[k] < 0.5 <= a[k])
    m = n01 + n10
    p = 1.0 if m == 0 else min(1.0, 2 * sum(math.comb(m, i) for i in range(min(n01, n10) + 1)) / 2 ** m)
    return {"b_wins": n01, "a_wins": n10, "p_exact": p}


def holm(pvals: dict[str, float]) -> dict[str, float]:
    items = sorted(pvals.items(), key=lambda x: x[1])
    m, out, run = len(items), {}, 0.0
    for i, (k, p) in enumerate(items):
        run = max(run, min(1.0, (m - i) * p))
        out[k] = run
    return out


def auroc(scores: list[float], labels: list[int]) -> float:
    """P(score of a positive > score of a negative); ties count 1/2."""
    pos = [s for s, y in zip(scores, labels) if y]
    neg = [s for s, y in zip(scores, labels) if not y]
    if not pos or not neg:
        return float("nan")
    wins = sum((p > q) + 0.5 * (p == q) for p in pos for q in neg)
    return wins / (len(pos) * len(neg))

"""Identifier tokenisation, BM25 over node source, and issue-text anchors."""

from __future__ import annotations

import math
import re
from collections import Counter, defaultdict

from .graph import CodeGraph

_CAMEL = re.compile(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z]+|[A-Z]+|\d+")
_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*")
STOP = set("""a an and are as at be but by for from has have i if in is it its of on or
that the this to was were will with not no can should would when what which there their
self cls none true false return def class import none str int dict list get set""".split())


def subtokens(text: str) -> list[str]:
    toks = []
    for ident in re.findall(r"[A-Za-z0-9_]+", text):
        for part in ident.split("_"):
            toks += [t.lower() for t in _CAMEL.findall(part)]
    return [t for t in toks if len(t) > 1 and t not in STOP]


class BM25:
    def __init__(self, docs: dict[str, str], k1: float = 1.2, b: float = 0.75):
        self.k1, self.b = k1, b
        self.tf = {d: Counter(subtokens(t)) for d, t in docs.items()}
        self.len = {d: sum(c.values()) for d, c in self.tf.items()}
        self.avg = (sum(self.len.values()) / len(self.len)) if self.len else 1.0
        df: Counter = Counter()
        for c in self.tf.values():
            df.update(c.keys())
        n = len(docs)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}
        self.post: dict[str, list[str]] = defaultdict(list)
        for d, c in self.tf.items():
            for t in c:
                self.post[t].append(d)

    def scores(self, query: str) -> dict[str, float]:
        out: dict[str, float] = defaultdict(float)
        for t in set(subtokens(query)):
            idf = self.idf.get(t)
            if idf is None:
                continue
            for d in self.post[t]:
                f = self.tf[d][t]
                out[d] += idf * f * (self.k1 + 1) / (
                    f + self.k1 * (1 - self.b + self.b * self.len[d] / self.avg))
        return dict(out)


def node_doc(g: CodeGraph, nid: str) -> str:
    # id path is included so that module/class names count as evidence
    return nid.replace(".", " ") + " " + g.nodes[nid].text


def extract_identifiers(issue: str) -> list[str]:
    """Code-like identifiers mentioned in an issue (code spans, dotted, snake, Camel, frames)."""
    cands: list[str] = []
    spans = re.findall(r"`([^`]+)`", issue)
    frames = re.findall(r'File "([^"]+)", line \d+, in (\w+)', issue)
    for s in spans:
        cands += _IDENT.findall(s)
    for path, fn in frames:
        cands += [fn, path.replace("/", ".").removesuffix(".py")]
    for tok in _IDENT.findall(issue):
        if "." in tok or "_" in tok or re.search(r"[a-z][A-Z]", tok) or tok in cands:
            cands.append(tok)
    seen, out = set(), []
    for c in cands:
        c = c.strip(".")
        if len(c) > 2 and c.lower() not in STOP and c not in seen:
            seen.add(c)
            out.append(c)
    return out


def anchors(g: CodeGraph, issue: str) -> dict[str, float]:
    """Seed weights s0(v): issue identifiers matched to node ids, weighted by rarity."""
    by_short: dict[str, list[str]] = defaultdict(list)
    for nid in g.nodes:
        by_short[nid.rsplit(".", 1)[-1]].append(nid)
    n = max(len(g.nodes), 2)
    seeds: dict[str, float] = defaultdict(float)
    for ident in extract_identifiers(issue):
        parts = ident.split(".")
        # dotted suffix match first (most specific), then last component
        hits = [nid for nid in by_short.get(parts[-1], [])
                if len(parts) == 1 or nid.endswith(".".join(parts[-2:]))] \
            or by_short.get(parts[-1], [])
        if not hits:
            continue
        w = math.log(n / len(hits))
        for h in hits:
            seeds[h] += w / len(hits) ** 0.5
    return dict(seeds)

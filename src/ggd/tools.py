"""Graph tools with the same semantics as the competition harness.

`search_similar_code`, `get_code_neighbors`, `get_code_subgraph` mirror the official
signatures. `view_symbol` returns a node's source (the official graph stores it in
`nodes[*].text`); it stands in for `read_file` because official graph nodes carry no
file path. All LLM-driven methods get exactly this tool set.
"""

from __future__ import annotations

import difflib
import json
from dataclasses import dataclass, field
from typing import Callable

from .graph import CodeGraph
from .lexical import BM25, node_doc

MAX_VIEW_LINES = 60


def _sig(g: CodeGraph, nid: str) -> str:
    first = next((ln.strip() for ln in g.nodes[nid].text.splitlines()
                  if ln.strip() and not ln.strip().startswith("@")), "")
    return first[:100]


@dataclass
class ToolBox:
    g: CodeGraph
    search_backend: Callable[[str, int], list[tuple[str, float]]] | None = None
    visited: list[str] = field(default_factory=list)
    calls: list[dict] = field(default_factory=list)
    invalid: int = 0

    def __post_init__(self):
        if self.search_backend is None:
            bm = BM25({n: node_doc(self.g, n) for n in self.g.nodes})
            self.search_backend = lambda q, k: sorted(
                bm.scores(q).items(), key=lambda x: -x[1])[:k]

    # ------------------------------------------------------------ helpers
    def resolve(self, name: str) -> str | None:
        """Harness resolution order: exact -> suffix -> case-insensitive -> substring."""
        from .embed import resolve_name
        name = (name or "").strip().strip("`'\"()")
        if not hasattr(self, "_keys"):
            self._keys = list(self.g.nodes)
        return resolve_name(name, self._keys)

    def _unknown(self, name: str) -> str:
        self.invalid += 1
        sugg = difflib.get_close_matches(name, list(self.g.nodes), n=5, cutoff=0.5)
        return f"ERROR: unknown node '{name}'. Use full dotted ids. Close matches: {sugg}"

    # ------------------------------------------------------------ tools
    def search_similar_code(self, query: str, k: int = 10) -> str:
        k = max(1, min(int(k), 20))
        res = self.search_backend(query, k)
        self.visited += [n for n, _ in res]
        res = [(n, s) for n, s in res if n in self.g.nodes]
        return "\n".join(f"{n}  ({s:.2f})  {_sig(self.g, n)}" for n, s in res) or \
            "no results (pass a class/function/module name, e.g. 'parse_header')"

    def get_code_neighbors(self, node: str, edge_type: str | None = None,
                           max_neighbors: int = 50) -> str:
        nid = self.resolve(node)
        if nid is None:
            return self._unknown(node)
        self.visited.append(nid)
        types = None
        if edge_type:
            known = {t.lower(): t for t in self.g.edge_types()}
            if edge_type.lower() not in known:
                self.invalid += 1
                return (f"ERROR: unknown edge_type '{edge_type}'. Valid types: "
                        f"{sorted(known.values())} (or omit edge_type for all neighbors)")
            types = {known[edge_type.lower()]}
        rows = [f"{d} {t} {v}" for v, t, d in self.g.neighbors(nid, types)]
        rows = rows[: max(1, min(int(max_neighbors), 50))]
        self.visited += [r.split()[-1] for r in rows]
        return f"neighbors of {nid} (direction type node):\n" + ("\n".join(rows) or "none")

    def get_code_subgraph(self, nodes: list[str]) -> str:
        ids, errs = [], []
        for n in nodes[:20]:
            r = self.resolve(n)
            (ids.append(r) if r else errs.append(self._unknown(n)))
        s = set(ids)
        edges = [f"{a} -{t}-> {b}" for a in ids for b, t in self.g.out.get(a, ()) if b in s]
        self.visited += ids
        return "\n".join(errs + [f"nodes: {ids}", "edges:"] + (edges or ["none"]))

    def view_symbol(self, node: str) -> str:
        nid = self.resolve(node)
        if nid is None:
            return self._unknown(node)
        self.visited.append(nid)
        lines = self.g.nodes[nid].text.splitlines()
        more = f"\n... ({len(lines) - MAX_VIEW_LINES} more lines)" if len(lines) > MAX_VIEW_LINES else ""
        return f"# {nid}\n" + "\n".join(lines[:MAX_VIEW_LINES]) + more

    # ------------------------------------------------------------ dispatch
    def call(self, name: str, args: dict | str) -> str:
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except json.JSONDecodeError:
                args = {}
        fn = {"search_similar_code": self.search_similar_code,
              "get_code_neighbors": self.get_code_neighbors,
              "get_code_subgraph": self.get_code_subgraph,
              "view_symbol": self.view_symbol}.get(name)
        if fn is None:
            self.invalid += 1
            out = f"ERROR: unknown tool '{name}'"
        else:
            try:
                out = fn(**args)
            except TypeError as e:
                self.invalid += 1
                out = f"ERROR: bad arguments for {name}: {e}"
        self.calls.append({"tool": name, "args": args, "ok": not out.startswith("ERROR")})
        return out


TOOL_SCHEMAS = [
    {"type": "function", "function": {
        "name": "search_similar_code",
        "description": "Find the k symbols whose embeddings are most similar to a given symbol. Pass a class, function or module NAME (e.g. 'parse_header'), not a sentence.",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string"}, "k": {"type": "integer"}}, "required": ["query"]}}},
    {"type": "function", "function": {
        "name": "get_code_neighbors",
        "description": "Incoming and outgoing neighbors (callers, callees, imports, parents) of a symbol in the code graph.",
        "parameters": {"type": "object", "properties": {
            "node": {"type": "string", "description": "fully qualified symbol id"},
            "edge_type": {"type": "string"}, "max_neighbors": {"type": "integer"}},
            "required": ["node"]}}},
    {"type": "function", "function": {
        "name": "get_code_subgraph",
        "description": "Edges among a list of symbols (induced subgraph).",
        "parameters": {"type": "object", "properties": {
            "nodes": {"type": "array", "items": {"type": "string"}}}, "required": ["nodes"]}}},
    {"type": "function", "function": {
        "name": "view_symbol",
        "description": "Show the source code of a symbol (first 60 lines).",
        "parameters": {"type": "object", "properties": {
            "node": {"type": "string"}}, "required": ["node"]}}},
]

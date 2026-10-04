"""Repository code graph.

Two constructors:
  * `CodeGraph.from_official_json` loads the competition's NetworkX node-link JSON.
  * `CodeGraph.from_repo` rebuilds a graph with the same id scheme from source using
    `ast` (used for external benchmarks, and validated against the official graphs).

Node ids are fully-qualified dotted paths: `pkg.module`, `pkg.module.Class`,
`pkg.module.Class.method`, `pkg.module.func`.
"""

from __future__ import annotations

import ast
import json
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

SKIP_DIRS = {".git", "docs", "doc", "build", "dist", ".tox", ".venv", "venv", "node_modules"}


@dataclass
class Node:
    id: str
    kind: str = "unknown"      # module | class | function | method | unknown
    text: str = ""
    file: str = ""             # repo-relative path (only known for from_repo graphs)
    start: int = 0
    end: int = 0

    @property
    def short(self) -> str:
        return self.id.rsplit(".", 1)[-1]


@dataclass
class CodeGraph:
    nodes: dict[str, Node] = field(default_factory=dict)
    out: dict[str, list[tuple[str, str]]] = field(default_factory=lambda: defaultdict(list))
    inn: dict[str, list[tuple[str, str]]] = field(default_factory=lambda: defaultdict(list))

    # ------------------------------------------------------------ basics
    def add_node(self, node: Node) -> None:
        self.nodes.setdefault(node.id, node)

    def add_edge(self, src: str, dst: str, etype: str) -> None:
        if src == dst or src not in self.nodes or dst not in self.nodes:
            return
        if (dst, etype) in self.out[src]:
            return
        self.out[src].append((dst, etype))
        self.inn[dst].append((src, etype))

    def edge_types(self) -> dict[str, int]:
        c: dict[str, int] = defaultdict(int)
        for es in self.out.values():
            for _, t in es:
                c[t] += 1
        return dict(c)

    def n_edges(self) -> int:
        return sum(len(v) for v in self.out.values())

    def neighbors(self, v: str, types: set[str] | None = None):
        for d, t in self.out.get(v, ()):
            if types is None or t in types:
                yield d, t, "out"
        for s, t in self.inn.get(v, ()):
            if types is None or t in types:
                yield s, t, "in"

    def add_containment(self, etype: str = "contains") -> int:
        """Parent->child edges implied by dotted ids (module -> class -> method)."""
        added = 0
        for nid in list(self.nodes):
            parent = nid.rsplit(".", 1)[0] if "." in nid else None
            while parent and parent not in self.nodes:
                parent = parent.rsplit(".", 1)[0] if "." in parent else None
            if parent:
                before = len(self.out[parent])
                self.add_edge(parent, nid, etype)
                added += len(self.out[parent]) - before
        return added

    # ------------------------------------------------------------ official
    @classmethod
    def from_official_json(cls, path: str | Path) -> "CodeGraph":
        data = json.loads(Path(path).read_text())
        g = cls()
        for n in data["nodes"]:
            g.add_node(Node(id=n["id"], text=n.get("text", "") or "",
                            kind=n.get("kind") or n.get("type") or _guess_kind(n)))
        key = "edges" if "edges" in data else "links"
        for e in data[key]:
            g.add_edge(e["source"], e["target"], e.get("type", "unknown"))
        return g

    # ------------------------------------------------------------ rebuild
    @classmethod
    def from_repo(cls, root: str | Path, include_tests: bool = False) -> "CodeGraph":
        root = Path(root)
        g = cls()
        mods: dict[str, tuple[Path, ast.Module, str]] = {}
        for f in sorted(root.rglob("*.py")):
            rel = f.relative_to(root)
            if any(p in SKIP_DIRS or p.startswith(".") for p in rel.parts[:-1]):
                continue
            if not include_tests and _is_test_path(rel):
                continue
            try:
                src = f.read_text(encoding="utf-8", errors="replace")
                tree = ast.parse(src)
            except (SyntaxError, ValueError):
                continue
            mod = module_name(rel)
            if not mod:
                continue
            mods[mod] = (rel, tree, src)
            g.add_node(Node(mod, "module", "", str(rel), 1, len(src.splitlines())))
            for qual, kind, n in _walk_defs(tree):
                g.add_node(Node(f"{mod}.{qual}", kind, ast.get_source_segment(src, n) or "",
                                str(rel), n.lineno, n.end_lineno or n.lineno))
        by_short: dict[str, list[str]] = defaultdict(list)
        for nid, n in g.nodes.items():
            if n.kind != "module":
                by_short[n.short].append(nid)
        for mod, (_, tree, _) in mods.items():
            _Linker(g, mod, tree, by_short).run()
        return g

    # ------------------------------------------------------------ lookup
    def defs_in_file(self, rel: str) -> list[Node]:
        return [n for n in self.nodes.values() if n.file == rel]


def _guess_kind(n: dict) -> str:
    text = (n.get("text") or "").lstrip()
    if text.startswith("class "):
        return "class"
    if text.startswith(("def ", "async def ", "@")):
        return "function"
    return "unknown"


def _is_test_path(rel: Path) -> bool:
    parts = [p.lower() for p in rel.parts]
    name = parts[-1]
    return (any(p in ("tests", "test", "testing") for p in parts[:-1])
            or name.startswith("test_") or name.endswith("_test.py") or name == "conftest.py")


def module_name(rel: Path) -> str:
    parts = list(rel.with_suffix("").parts)
    if parts and parts[0] in ("src", "lib"):
        parts = parts[1:]
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _walk_defs(tree: ast.AST, prefix: str = "", in_class: bool = False):
    for n in ast.iter_child_nodes(tree):
        if isinstance(n, ast.ClassDef):
            q = f"{prefix}{n.name}"
            yield q, "class", n
            yield from _walk_defs(n, q + ".", True)
        elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            q = f"{prefix}{n.name}"
            yield q, "method" if in_class else "function", n
            # nested functions are folded into their parent (not separate nodes)


class _Linker:
    """Resolves calls / imports / inheritance to node ids, best-effort and static."""

    def __init__(self, g: CodeGraph, mod: str, tree: ast.Module, by_short):
        self.g, self.mod, self.tree, self.by_short = g, mod, tree, by_short
        self.alias: dict[str, str] = {}   # local name -> fully qualified target

    def run(self) -> None:
        pkg = self.mod.rsplit(".", 1)[0] if "." in self.mod else ""
        is_pkg = self.g.nodes[self.mod].file.endswith("__init__.py")
        base_pkg = self.mod if is_pkg else pkg
        for n in ast.walk(self.tree):
            if isinstance(n, ast.Import):
                for a in n.names:
                    self.alias[(a.asname or a.name).split(".")[0]] = \
                        a.name if a.asname else a.name.split(".")[0]
                    self._import_edge(a.name)
            elif isinstance(n, ast.ImportFrom):
                base = n.module or ""
                if n.level:
                    up = base_pkg.split(".")
                    up = up[: len(up) - (n.level - 1)] if n.level > 1 else up
                    base = ".".join([p for p in up if p] + ([n.module] if n.module else []))
                for a in n.names:
                    if a.name == "*":
                        continue
                    tgt = f"{base}.{a.name}" if base else a.name
                    self.alias[a.asname or a.name] = tgt
                    self._import_edge(tgt)
        for qual, kind, node in _walk_defs(self.tree):
            src = f"{self.mod}.{qual}"
            cls = f"{self.mod}.{qual.rsplit('.', 1)[0]}" if kind == "method" else None
            if kind == "class":
                for b in node.bases:
                    t = self._resolve(b, None)
                    if t:
                        self.g.add_edge(src, t, "inherits")
                body = [s for s in node.body if not isinstance(
                    s, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]
            else:
                body = [node]
            for stmt in body:
                for c in ast.walk(stmt):
                    if isinstance(c, ast.Call):
                        t = self._resolve(c.func, cls)
                        if t:
                            self.g.add_edge(src, t, "calls")

    def _import_edge(self, target: str) -> None:
        t = self._existing(target)
        if t:
            self.g.add_edge(self.mod, t, "imports")

    def _existing(self, dotted: str) -> str | None:
        # follow re-exports: pkg.Name may be defined in pkg.sub.Name
        if dotted in self.g.nodes:
            return dotted
        short = dotted.rsplit(".", 1)[-1]
        head = dotted.rsplit(".", 1)[0] if "." in dotted else ""
        cands = [c for c in self.by_short.get(short, []) if c.startswith(head + ".")] if head else []
        return cands[0] if len(cands) == 1 else None

    def _resolve(self, f: ast.AST, cls: str | None) -> str | None:
        if isinstance(f, ast.Name):
            local = f"{self.mod}.{f.id}"
            if local in self.g.nodes:
                return local
            if f.id in self.alias:
                return self._existing(self.alias[f.id])
            return None
        if isinstance(f, ast.Attribute):
            if isinstance(f.value, ast.Name) and f.value.id in ("self", "cls") and cls:
                m = f"{cls}.{f.attr}"
                return m if m in self.g.nodes else self._unique(f.attr)
            if isinstance(f.value, ast.Name) and f.value.id in self.alias:
                return self._existing(f"{self.alias[f.value.id]}.{f.attr}")
            return self._unique(f.attr)
        return None

    def _unique(self, short: str) -> str | None:
        c = self.by_short.get(short, [])
        return c[0] if len(c) == 1 else None

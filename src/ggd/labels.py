"""Gold localization labels from a reference patch.

Removed/modified lines are mapped (in base-file coordinates) to the innermost enclosing
definition in the base snapshot. Added lines are mapped (in post-patch coordinates) to
the innermost definition in the patched file; if that definition does not exist in the
base snapshot (e.g. a newly added method), the label climbs to the nearest enclosing
symbol that does exist (its class, else its module): that is where an agent must edit.
Test files are ignored. Fully automatic; no hand labels.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path

from .graph import _is_test_path, _walk_defs, module_name

HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


@dataclass
class Hunk:
    old_start: int
    lines: list[str] = field(default_factory=list)   # raw ' ', '-', '+' lines


@dataclass
class FileChange:
    path: str
    is_new_file: bool = False
    hunks: list[Hunk] = field(default_factory=list)


def parse_patch(patch: str) -> list[FileChange]:
    changes: list[FileChange] = []
    cur: FileChange | None = None
    for line in patch.splitlines():
        if line.startswith("diff --git"):
            cur = None
        elif line.startswith("--- "):
            src = line[4:].split("\t")[0].strip()
            cur = FileChange(path=src[2:] if src.startswith("a/") else src,
                             is_new_file=src == "/dev/null")
            changes.append(cur)
        elif line.startswith("+++ ") and cur is not None:
            dst = line[4:].split("\t")[0].strip()
            if cur.is_new_file:
                cur.path = dst[2:] if dst.startswith("b/") else dst
        elif (m := HUNK.match(line)) and cur is not None:
            cur.hunks.append(Hunk(int(m.group(1))))
        elif cur is not None and cur.hunks and line[:1] in ("-", "+", " ", ""):
            cur.hunks[-1].lines.append(line if line else " ")
    return changes


def apply_file(base: list[str], ch: FileChange) -> tuple[list[str], set[int], set[int]]:
    """Returns (new_lines, removed_base_lines, added_new_lines), lines 1-indexed."""
    new: list[str] = []
    removed, added = set(), set()
    pos = 1
    for h in ch.hunks:
        new.extend(base[pos - 1: h.old_start - 1])
        pos = h.old_start
        for ln in h.lines:
            tag, body = ln[0], ln[1:]
            if tag == " ":
                new.append(base[pos - 1] if pos - 1 < len(base) else body)
                pos += 1
            elif tag == "-":
                removed.add(pos)
                pos += 1
            elif tag == "+":
                new.append(body)
                added.add(len(new))
    new.extend(base[pos - 1:])
    return new, removed, added


def def_spans(src: str, mod: str) -> list[tuple[int, int, str, str]]:
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return []
    out = []
    for qual, kind, n in _walk_defs(tree):
        start = min([n.lineno] + [d.lineno for d in getattr(n, "decorator_list", [])])
        out.append((start, n.end_lineno or n.lineno, f"{mod}.{qual}", kind))
    return out


def _innermost(spans, ln):
    inner = [s for s in spans if s[0] <= ln <= s[1]]
    return max(inner, key=lambda s: s[0]) if inner else None


def gold_symbols(patch: str, repo_root: str | Path, include_tests: bool = False) -> dict:
    """Returns {'functions', 'classes', 'modules', 'files', 'new_symbols'} (ids in base space)."""
    root = Path(repo_root)
    funcs, classes, modules, files, new_syms = [], [], [], [], []
    for ch in parse_patch(patch):
        rel = Path(ch.path)
        if rel.suffix != ".py" or (not include_tests and _is_test_path(rel)):
            continue
        files.append(ch.path)
        mod = module_name(rel)
        f = root / rel
        if ch.is_new_file or not f.exists():
            modules.append(mod)
            continue
        base_src = f.read_text(encoding="utf-8", errors="replace")
        base_lines = base_src.splitlines()
        new_lines, removed, added = apply_file(base_lines, ch)
        base_spans = def_spans(base_src, mod)
        base_kind = {s[2]: s[3] for s in base_spans}
        new_spans = def_spans("\n".join(new_lines) + "\n", mod)

        def emit(sym_id: str | None):
            if sym_id is None:
                modules.append(mod)
            elif base_kind[sym_id] == "class":
                classes.append(sym_id)
            else:
                funcs.append(sym_id)

        for ln in sorted(removed):
            s = _innermost(base_spans, ln)
            emit(s[2] if s else None)
        for ln in sorted(added):
            if not new_lines[ln - 1].strip():
                continue                      # blank added lines carry no location
            s = _innermost(new_spans, ln)
            sym = s[2] if s else None
            if sym is not None and sym not in base_kind:
                new_syms.append(sym)
                while sym is not None and sym not in base_kind:
                    sym = sym.rsplit(".", 1)[0] if sym.count(".") > mod.count(".") + 1 else None
            emit(sym)
    uniq = lambda xs: list(dict.fromkeys(xs))  # noqa: E731
    return {"functions": uniq(funcs), "classes": uniq(classes), "modules": uniq(modules),
            "files": uniq(files), "new_symbols": uniq(new_syms)}

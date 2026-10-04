"""Official competition data access (data/official, never committed)."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import tempfile
from contextlib import contextmanager
from pathlib import Path

from .graph import CodeGraph

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "official"
CACHE = ROOT / "data" / "cache"


def find(name: str, base: Path = DATA) -> Path:
    """Locate a file/dir in the (possibly nested) extracted competition archive."""
    direct = base / name
    if direct.exists():
        return direct
    hits = sorted(base.rglob(name))
    if not hits:
        raise FileNotFoundError(f"{name} not found under {base}; run scripts/get_data.sh")
    return hits[0]


def load_tasks(base: Path = DATA) -> list[dict]:
    with open(find("tasks.jsonl", base)) as f:
        return [json.loads(line) for line in f if line.strip()]


def file_sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


_KEYS: dict[str, str] = {}


def data_key(instance_id: str, base: Path = DATA) -> str:
    """Graphs/embeddings are stored per commit: <repo_short>_<base_commit>."""
    if not _KEYS:
        for t in load_tasks(base):
            _KEYS[t["instance_id"]] = t["instance_id"].rsplit("_", 1)[0] + "_" + t["base_commit"]
    return _KEYS[instance_id]


def official_graph(instance_id: str, base: Path = DATA) -> CodeGraph:
    return CodeGraph.from_official_json(find("graphs", base) / f"{data_key(instance_id, base)}.json")


def official_embeddings(instance_id: str, base: Path = DATA):
    from .embed import EmbeddingIndex
    p = find("embeddings", base) / f"{data_key(instance_id, base)}.npz"
    return EmbeddingIndex.load(p) if p.exists() else None


REPOS = ROOT / "data" / "repos"


@contextmanager
def snapshot(instance_id: str, base: Path = DATA):
    """Checks out the task's base_commit from the public clone (data/repos/<name>) into a
    temporary worktree. Equivalent to the official snapshot tree, without 37-320 MB archives."""
    t = next(t for t in load_tasks(base) if t["instance_id"] == instance_id)
    repo = REPOS / t["repo"].split("/")[1]
    tmp = Path(tempfile.mkdtemp(prefix=f"ggd_{instance_id}_"))
    wt = tmp / "w"
    subprocess.run(["git", "worktree", "add", "-q", "--detach", str(wt), t["base_commit"]],
                   cwd=repo, check=True, capture_output=True)
    try:
        yield wt
    finally:
        subprocess.run(["git", "worktree", "remove", "--force", str(wt)], cwd=repo, capture_output=True)
        shutil.rmtree(tmp, ignore_errors=True)


def labels_path() -> Path:
    return CACHE / "labels.jsonl"


def load_labels() -> dict[str, dict]:
    p = labels_path()
    if not p.exists():
        raise FileNotFoundError("run scripts/prepare_tasks.py first")
    return {d["instance_id"]: d for d in map(json.loads, p.read_text().splitlines())}

"""Localization methods. Every method maps (graph, issue) -> ranked list of node ids.

  A  no_retrieval   LLM sees issue + module list only (memorisation/contamination probe)
  B  bm25           flat lexical retrieval over node source
  C  static_graph   anchors + BM25 seeds -> fixed k-hop ego graph, ranked by BM25
  D  apn            anchored personalized PageRank (0 LLM calls)
  E  mdn            model-driven navigation with graph tools (LocAgent-style)
  F  agentless      hierarchical LLM localization: modules -> symbols (no graph)
  G  gdn            gated delegation: APN, plus MDN only when APN is uncertain
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field

from .apn import APN, CANDIDATE_KINDS, APNParams, is_candidate
from .graph import CodeGraph
from .lexical import anchors
from .llm import LLM
from .metrics import hop_distances
from .tools import TOOL_SCHEMAS, ToolBox

K_OUT = 10
PROMPT_VERSION = "v1"


@dataclass
class Result:
    method: str
    ranked: list[str]
    llm_calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    context_chars: int = 0          # total characters presented to the model, summed over calls
    tool_calls: int = 0
    invalid_tool_calls: int = 0
    wall_s: float = 0.0
    stop: str = "done"
    gate_open: bool | None = None
    uncertainty: float | None = None
    visited: list[str] = field(default_factory=list)
    transcript: list[dict] = field(default_factory=list)


def _candidates(g: CodeGraph) -> list[str]:
    return [n for n in g.nodes if is_candidate(g, n)]


def _pad(ranked: list[str], backup: list[str], k: int = 50) -> list[str]:
    out = list(dict.fromkeys(ranked))
    for b in backup:
        if len(out) >= k:
            break
        if b not in out:
            out.append(b)
    return out


def _bm25_rank(apn: APN, g: CodeGraph, issue: str) -> list[str]:
    s = apn.bm25.scores(issue)
    cands = _candidates(g)
    return sorted(cands, key=lambda c: -s.get(c, 0.0))


def parse_final(text: str, tb: ToolBox) -> list[str] | None:
    m = re.search(r"FINAL\s*:?\s*(.*)", text, re.S)
    if not m:
        return None
    toks = re.findall(r"[A-Za-z_][\w]*(?:\.[A-Za-z_][\w]*)+|[A-Za-z_]\w{2,}", m.group(1))
    out = []
    for t in toks:
        r = tb.resolve(t)
        if r and r not in out:
            out.append(r)
    return out


# ---------------------------------------------------------------- B, C, D
def run_bm25(g, issue, apn: APN) -> Result:
    t = time.time()
    return Result("bm25", _bm25_rank(apn, g, issue)[:50], wall_s=time.time() - t)


def run_static_graph(g, issue, apn: APN, hops: int = 1, seeds_bm25: int = 5) -> Result:
    t = time.time()
    s0 = anchors(g, issue)
    bm_rank = _bm25_rank(apn, g, issue)
    seeds = list(s0) + bm_rank[:seeds_bm25]
    ego = set(hop_distances(g, seeds, max_hops=hops))
    inside = [c for c in bm_rank if c in ego]
    return Result("static_graph", _pad(inside, bm_rank), wall_s=time.time() - t)


def run_apn(g, issue, apn: APN) -> Result:
    t = time.time()
    r = apn.rank(issue)
    return Result("apn", r.ranked, wall_s=time.time() - t, uncertainty=r.uncertainty)


# ---------------------------------------------------------------- LLM methods
SYS_NAV = """You localize the code that must be edited to resolve a GitHub issue in a Python repository.
The repository is available as a code graph whose nodes are fully qualified symbols
(e.g. pkg.module.Class.method). Use the tools to investigate. Be economical: you have at most
{budget} tool calls. When you are confident, reply with exactly one line:
FINAL: <id1>, <id2>, ... (up to {k} fully qualified ids, most likely first)
Only list functions, methods or classes that need to be modified."""


def _issue_block(issue: str, anchor_ids: list[str], max_chars: int = 6000) -> str:
    a = "\n".join(f"- {x}" for x in anchor_ids[:10]) or "- (none matched)"
    return (f"<issue>\n{issue[:max_chars]}\n</issue>\n\n"
            f"Symbols whose names appear in the issue:\n{a}")


def run_navigator(g, issue, llm: LLM, budget: int = 8, seed_list: list[str] | None = None,
                  name: str = "mdn", emb=None) -> Result:
    t0 = time.time()
    tb = ToolBox(g, search_backend=emb.similar if emb is not None else None)
    s0 = anchors(g, issue)
    anchor_ids = sorted(s0, key=lambda x: -s0[x])
    user = _issue_block(issue, anchor_ids)
    if seed_list:
        user += ("\n\nA graph-ranking algorithm proposes these candidates (most likely first); "
                 "verify or correct them:\n" + "\n".join(f"{i+1}. {x}" for i, x in enumerate(seed_list)))
    msgs = [{"role": "system", "content": SYS_NAV.format(budget=budget, k=K_OUT)},
            {"role": "user", "content": user}]
    res = Result(name, [])
    final = None
    while True:
        r = llm.chat(msgs, tools=TOOL_SCHEMAS if len(tb.calls) < budget else None)
        res.context_chars += sum(len(m.get("content") or "") for m in msgs)
        res.llm_calls += 1
        res.prompt_tokens += r.prompt_tokens
        res.completion_tokens += r.completion_tokens
        if r.tool_calls and len(tb.calls) < budget:
            msgs.append({"role": "assistant", "content": r.content, "tool_calls": r.tool_calls})
            for c in r.tool_calls:
                fn = c.get("function", {})
                out = tb.call(fn.get("name", ""), fn.get("arguments", {}))
                msgs.append({"role": "tool", "tool_name": fn.get("name", ""), "content": out[:4000]})
            if tb.invalid >= 3 and all(not c["ok"] for c in tb.calls[-3:]):
                res.stop = "invalid_calls"
                break
            continue
        final = parse_final(r.content, tb)
        if final is not None:
            res.stop = "final" if final else "final_empty"
            break
        if len(tb.calls) >= budget or res.llm_calls >= budget + 3:
            res.stop = "budget"
            break
        msgs.append({"role": "assistant", "content": r.content})
        msgs.append({"role": "user", "content": "Reply now with the FINAL: line."})
    res.ranked = final or []
    res.tool_calls, res.invalid_tool_calls = len(tb.calls), tb.invalid
    res.visited = list(dict.fromkeys(tb.visited))
    res.transcript = [{"role": m["role"], "content": m.get("content", "")[:2000],
                       **({"tool_calls": m["tool_calls"]} if "tool_calls" in m else {})}
                      for m in msgs[1:]]
    res.wall_s = time.time() - t0
    return res


def run_mdn(g, issue, apn: APN, llm: LLM, budget: int = 8, emb=None) -> Result:
    res = run_navigator(g, issue, llm, budget=budget, name="mdn", emb=emb)
    res.ranked = _pad(res.ranked, _bm25_rank(apn, g, issue))
    return res


def run_gdn(g, issue, apn: APN, llm: LLM, tau: float, budget: int = 4, emb=None) -> Result:
    t0 = time.time()
    r = apn.rank(issue)
    if r.uncertainty < tau:
        return Result("gdn", r.ranked, wall_s=time.time() - t0, gate_open=False,
                      uncertainty=r.uncertainty)
    res = run_navigator(g, issue, llm, budget=budget, seed_list=r.ranked[:K_OUT], name="gdn", emb=emb)
    res.ranked = _pad(res.ranked, r.ranked)
    res.gate_open, res.uncertainty = True, r.uncertainty
    res.wall_s = time.time() - t0
    return res


def _module_list(g: CodeGraph) -> list[str]:
    return sorted(n for n, node in g.nodes.items() if node.kind == "module") or \
        sorted({n.rsplit(".", 1)[0] for n in g.nodes if "." in n})


def run_no_retrieval(g, issue, apn: APN, llm: LLM) -> Result:
    t0 = time.time()
    tb = ToolBox(g)
    mods = "\n".join(_module_list(g)[:400])
    q = (f"<issue>\n{issue[:6000]}\n</issue>\n\nRepository modules:\n{mods}\n\n"
         f"Which functions, methods or classes must be modified? Reply with one line:\n"
         f"FINAL: <id1>, <id2>, ... (up to {K_OUT} fully qualified ids, most likely first)")
    r = llm.chat([{"role": "user", "content": q}])
    ranked = parse_final(r.content, tb) or []
    return Result("no_retrieval", _pad(ranked, _bm25_rank(apn, g, issue)), llm_calls=1,
                  context_chars=len(q),
                  prompt_tokens=r.prompt_tokens, completion_tokens=r.completion_tokens,
                  wall_s=time.time() - t0)


def run_agentless(g, issue, apn: APN, llm: LLM, n_mods: int = 3) -> Result:
    """Two-stage hierarchical localization without graph access (Agentless-style)."""
    t0 = time.time()
    tb = ToolBox(g)
    mods = _module_list(g)
    q1 = (f"<issue>\n{issue[:6000]}\n</issue>\n\nRepository modules:\n" + "\n".join(mods[:400]) +
          f"\n\nList the {n_mods} modules most likely to need edits, one per line, "
          "most likely first. Output only module names.")
    r1 = llm.chat([{"role": "user", "content": q1}])
    chosen = [m for m in re.findall(r"[A-Za-z_][\w.]*", r1.content) if m in set(mods)][:n_mods]
    skel = []
    for m in chosen:
        for n, node in g.nodes.items():
            if n.startswith(m + ".") and n.count(".") <= m.count(".") + 2 and node.kind in CANDIDATE_KINDS:
                skel.append(f"{n}: {node.text.splitlines()[0][:90] if node.text else ''}")
    q2 = (f"<issue>\n{issue[:6000]}\n</issue>\n\nSymbols in the selected modules:\n" +
          "\n".join(skel[:300]) +
          f"\n\nWhich of these must be modified? Reply with one line:\n"
          f"FINAL: <id1>, <id2>, ... (up to {K_OUT} ids, most likely first)")
    r2 = llm.chat([{"role": "user", "content": q2}])
    ranked = parse_final(r2.content, tb) or []
    return Result("agentless", _pad(ranked, _bm25_rank(apn, g, issue)), llm_calls=2,
                  context_chars=len(q1) + len(q2),
                  prompt_tokens=r1.prompt_tokens + r2.prompt_tokens,
                  completion_tokens=r1.completion_tokens + r2.completion_tokens,
                  wall_s=time.time() - t0)


def make_apn(g: CodeGraph, params: APNParams | None = None) -> APN:
    return APN(g, params)

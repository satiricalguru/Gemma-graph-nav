#!/usr/bin/env python3
"""Pre-experiment sanity benchmark for a local Gemma 4 model.

Five probes, each automatically graded (no human judgement):
  P1 repo_structure  - pick the file to edit from a tree + module docstrings
  P2 tool_use        - emit a correct native tool call, then use its result
  P3 code_reasoning  - predict the output of a subtly buggy function
  P4 patch           - produce a unified diff that `git apply`s and passes a test
  P5 long_context    - 2-hop lookup buried in ~N tokens of synthetic code

Everything is synthetic and generated here, so no competition data is needed.
Usage:  GGD_MODEL=gemma4:12b-it-qat python scripts/sanity_benchmark.py --ctx-tokens 20000
"""

from __future__ import annotations

import argparse
import json
import random
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from ggd.llm import ModelConfig, make_llm  # noqa: E402

SYS = "You are a precise software engineering assistant. Follow output formats exactly."


def ask(llm, user, system=SYS, tools=None, history=None):
    msgs = [{"role": "system", "content": system}] + (history or []) + [
        {"role": "user", "content": user}]
    return msgs, llm.chat(msgs, tools=tools)


def rec(name, ok, r, **extra):
    return {"probe": name, "pass": bool(ok), "wall_s": round(r.wall_s, 2),
            "prompt_tokens": r.prompt_tokens, "completion_tokens": r.completion_tokens,
            "gen_tok_per_s": round(r.gen_tok_per_s, 1), **extra}


# ---------------------------------------------------------------- P1
TREE = {
    "shop/__init__.py": "Package root.",
    "shop/cli.py": "Command-line entry points.",
    "shop/billing/__init__.py": "Billing subpackage.",
    "shop/billing/invoice.py": "Invoice model: line items, totals, PDF export hooks.",
    "shop/billing/tax.py": "Tax computation: regional rates and rounding of tax amounts.",
    "shop/billing/currency.py": "Currency conversion using cached FX rates.",
    "shop/catalog/models.py": "Product and Variant dataclasses.",
    "shop/catalog/search.py": "Full-text product search.",
    "shop/orders/cart.py": "Shopping cart: add/remove items, apply discounts.",
    "shop/orders/checkout.py": "Checkout flow: validates cart, calls billing, emits events.",
    "shop/utils/rounding.py": "Generic numeric helpers (clamp, lerp). Not money-specific.",
    "tests/test_tax.py": "Tests for tax computation.",
}


def p1(llm):
    listing = "\n".join(f"{p}  # {d}" for p, d in TREE.items())
    q = ("Repository files with module docstrings:\n" + listing +
         "\n\nIssue: 'Tax on invoices is rounded half-down; it should round half-up.'\n"
         "Which single non-test file should be edited? Reply with the path only.")
    _, r = ask(llm, q)
    answer = r.content.strip().strip("`").strip()
    return rec("repo_structure", answer.split()[:1] == ["shop/billing/tax.py"], r,
               answer=answer[:200])


# ---------------------------------------------------------------- P2
TOOLS = [
    {"type": "function", "function": {
        "name": "find_symbol", "description": "Locate where a Python symbol is defined.",
        "parameters": {"type": "object", "properties": {
            "name": {"type": "string", "description": "symbol name"}}, "required": ["name"]}}},
    {"type": "function", "function": {
        "name": "read_file", "description": "Read a file from the repository.",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string"}}, "required": ["path"]}}},
]


def p2(llm):
    q = ("In this repository, where is the function `apply_discount` defined? "
         "You cannot see the code; use the tools. After you get the tool result, "
         "answer with the file path only.")
    msgs, r1 = ask(llm, q, tools=TOOLS)
    calls = r1.tool_calls
    ok_call = bool(calls) and calls[0]["function"]["name"] == "find_symbol" and \
        "apply_discount" in json.dumps(calls[0]["function"].get("arguments", {}))
    if not calls:
        return rec("tool_use", False, r1, stage="no_tool_call", answer=r1.content[:200])
    msgs = msgs + [{"role": "assistant", "content": r1.content, "tool_calls": calls},
                   {"role": "tool", "tool_name": calls[0]["function"]["name"],
                    "content": "shop/orders/cart.py:41: def apply_discount(cart, code):"}]
    r2 = llm.chat(msgs, tools=TOOLS)
    ok = ok_call and "shop/orders/cart.py" in r2.content
    r2.wall_s += r1.wall_s
    return rec("tool_use", ok, r2, first_call=calls[0]["function"],
               answer=r2.content.strip()[:200])


# ---------------------------------------------------------------- P3
P3_SRC = '''def window_sums(xs, k):
    out = []
    for i in range(len(xs) - k):
        out.append(sum(xs[i:i + k]))
    return out
'''


def p3(llm):
    ns: dict = {}
    exec(P3_SRC, ns)
    gold = ns["window_sums"]([3, 1, 4, 1, 5], 2)
    q = (f"```python\n{P3_SRC}```\nWhat does `window_sums([3, 1, 4, 1, 5], 2)` return? "
         "Trace carefully. End your reply with a final line `ANSWER: <python literal>`.")
    _, r = ask(llm, q)
    m = re.findall(r"ANSWER:\s*(\[[^\]]*\])", r.content)
    try:
        got = eval(m[-1]) if m else None
    except Exception:
        got = None
    return rec("code_reasoning", got == gold, r, gold=gold, got=got)


# ---------------------------------------------------------------- P4
BUGGY = '''def parse_version(s):
    """Parse 'MAJOR.MINOR.PATCH' into a tuple of ints. Missing parts default to 0."""
    parts = s.split(".")
    return tuple(int(p) for p in parts)
'''
TEST = '''from semver import parse_version
assert parse_version("1.2.3") == (1, 2, 3)
assert parse_version("1.2") == (1, 2, 0)
assert parse_version("4") == (4, 0, 0)
print("OK")
'''


def p4(llm):
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        (d / "semver.py").write_text(BUGGY)
        (d / "test_semver.py").write_text(TEST)
        subprocess.run("git init -q && git add . && git -c user.email=a@b -c user.name=a "
                       "commit -qm init", shell=True, cwd=d, check=True)
        fail = subprocess.run([sys.executable, "test_semver.py"], cwd=d,
                              capture_output=True).returncode != 0
        q = (f"File `semver.py`:\n```python\n{BUGGY}```\nTest `test_semver.py`:\n"
             f"```python\n{TEST}```\nThe test fails. Fix `semver.py` (do not edit the test). "
             "Reply with ONLY a unified diff in a ```diff block, with paths a/semver.py "
             "and b/semver.py.")
        _, r = ask(llm, q)
        m = re.search(r"```(?:diff|patch)?\n(.*?)```", r.content, re.S)
        patch = (m.group(1) if m else r.content)
        (d / "fix.patch").write_text(patch if patch.endswith("\n") else patch + "\n")
        ap = subprocess.run(["git", "apply", "--recount", "fix.patch"], cwd=d,
                            capture_output=True, text=True)
        passed = ap.returncode == 0 and subprocess.run(
            [sys.executable, "test_semver.py"], cwd=d, capture_output=True).returncode == 0
        return rec("patch", passed and fail, r, applied=ap.returncode == 0,
                   apply_err=ap.stderr[:200])


# ---------------------------------------------------------------- P5
def p5(llm, ctx_tokens, seed=0):
    rng = random.Random(seed)
    words = ["load", "parse", "emit", "scale", "merge", "fetch", "cache", "split", "index"]
    funcs = []
    approx = 0
    i = 0
    while approx < ctx_tokens:
        a, b = rng.choice(words), rng.choice(words)
        c1, c2 = rng.randint(1000, 9999), rng.randint(1, 9)
        f = (f"def {a}_{b}_{i}(x):\n    \"\"\"Helper {i}.\"\"\"\n"
             f"    y = x * {c2} + {c1}\n    return y\n\n")
        funcs.append(f)
        approx += len(f) // 3.2
        i += 1
    secret = rng.randint(10000, 99999)
    needle_b = f"def _resolve_quota_key():\n    return {secret}\n\n"
    needle_a = "def quota_limit():\n    return _resolve_quota_key() + 7\n\n"
    funcs.insert(int(len(funcs) * 0.15), needle_b)
    funcs.insert(int(len(funcs) * 0.80), needle_a)
    src = "".join(funcs)
    q = (f"```python\n{src}```\nWhat integer does `quota_limit()` return? "
         "End with a final line `ANSWER: <integer>`.")
    _, r = ask(llm, q)
    m = re.findall(r"ANSWER:\s*(-?\d+)", r.content)
    got = int(m[-1]) if m else None
    return rec("long_context", got == secret + 7, r, gold=secret + 7, got=got,
               approx_code_tokens=int(approx))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ctx-tokens", type=int, default=20000)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    cfg = ModelConfig.load()
    llm = make_llm(cfg)
    t0 = time.time()
    results = []
    for fn in (p1, p2, p3, p4):
        results.append(fn(llm))
        print(json.dumps(results[-1]), flush=True)
    results.append(p5(llm, args.ctx_tokens))
    print(json.dumps(results[-1]), flush=True)
    summary = {"model": cfg.name, "num_ctx": cfg.num_ctx, "temperature": cfg.temperature,
               "seed": cfg.seed, "think": cfg.think, "passed": sum(r["pass"] for r in results),
               "total": len(results), "total_wall_s": round(time.time() - t0, 1),
               "results": results}
    out = Path(args.out or f"results/sanity/{cfg.name.replace(':', '_')}"
               f"_think{int(cfg.think)}.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2))
    print(f"\n{summary['passed']}/{summary['total']} passed -> {out}")


if __name__ == "__main__":
    main()

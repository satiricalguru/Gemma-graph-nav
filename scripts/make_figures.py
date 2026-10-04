#!/usr/bin/env python3
"""Figures for the paper, regenerated from results/ (PNG into paper/figures/).
fig1: R@5 by method and model with paired-bootstrap 95% CI of the per-task mean.
fig2: MDN/GDN minus APN-CV on R@5, split by whether the issue names a graph symbol.
fig3: hop distance from issue anchors to gold symbols in the official graph (audit)."""
import json
import random
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "paper" / "figures"
OUT.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(ROOT / "src"))
THEMES = {"light": {"ink": "#1f2328", "muted": "#57606a", "grid": "#d0d7de", "bg": "#ffffff"},
          "dark": {"ink": "#e6edf3", "muted": "#9198a1", "grid": "#30363d", "bg": "#0d1117"}}
INK, MUTED, GRID, BG = (THEMES["light"][k] for k in ("ink", "muted", "grid", "bg"))
SUFFIX = ""


def set_theme(name):
    global INK, MUTED, GRID, BG, SUFFIX
    t = THEMES[name]
    INK, MUTED, GRID, BG, SUFFIX = t["ink"], t["muted"], t["grid"], t["bg"], ("" if name == "light" else "_dark")
    plt.rcParams.update({"figure.facecolor": BG, "axes.facecolor": BG, "savefig.facecolor": BG,
                         "text.color": INK, "axes.labelcolor": MUTED, "legend.labelcolor": INK})
COLORS = {"apn_cv": "#0969da", "bm25": "#8c959f", "no_retrieval": "#bf8700",
          "agentless": "#8250df", "mdn": "#cf222e", "gdn": "#1a7f37"}
LABEL = {"apn_cv": "APN (no LLM)", "bm25": "BM25", "no_retrieval": "No retrieval",
         "agentless": "Agentless-style", "mdn": "MDN (model navigates)", "gdn": "GDN (gated)"}


def load(method, model):
    f = ROOT / "results/runs" / method / model / ("seed0" if model == "no_llm" else "seed1234") / "tasks.jsonl"
    if not f.exists():
        f = f.with_name("tasks_public.jsonl")
    if not f.exists():
        return None
    return [r for r in map(json.loads, f.read_text().splitlines()) if r["gold"]]


def ci(xs, n=4000, seed=0):
    rng = random.Random(seed)
    m = [sum(rng.choices(xs, k=len(xs))) / len(xs) for _ in range(n)]
    m.sort()
    return sum(xs) / len(xs), m[int(.025 * n)], m[int(.975 * n) - 1]


def style(ax):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.spines["left"].set_color(GRID)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(colors=MUTED)
    for lbl in ax.get_xticklabels() + ax.get_yticklabels():
        lbl.set_color(MUTED)
    ax.yaxis.grid(True, color=GRID, lw=0.6)
    ax.set_axisbelow(True)


def fig1(models):
    methods = ["bm25", "apn_cv", "no_retrieval", "agentless", "mdn", "gdn"]
    fig, ax = plt.subplots(figsize=(7.2, 3.2), dpi=200)
    w = 0.13
    groups = ["no LLM"] + [m.replace("gemma4_", "").replace("-it-qat", "") for m in models]
    for gi, model in enumerate(["no_llm"] + models):
        ms = methods[:2] if model == "no_llm" else methods[2:]
        for j, m in enumerate(ms):
            rs = load(m, model)
            if not rs:
                continue
            mu, lo, hi = ci([r["R@5"] for r in rs])
            x = gi + (j - (len(ms) - 1) / 2) * (w + 0.03)
            ax.bar(x, mu, w, color=COLORS[m], label=LABEL[m] if gi < 2 or m in ("mdn", "gdn") else None)
            ax.errorbar(x, mu, yerr=[[mu - lo], [hi - mu]], color=INK, lw=0.8, capsize=2)
    ax.set_xticks(range(len(groups)), groups)
    ax.set_ylabel("Function-level Recall@5", color=MUTED)
    h, l = ax.get_legend_handles_labels()
    seen = dict(zip(l, h))
    ax.legend(seen.values(), seen.keys(), frameon=False, fontsize=7, ncol=3, loc="upper left")
    ax.set_ylim(0, 0.55)
    style(ax)
    fig.tight_layout()
    fig.savefig(OUT / f"fig1_main{SUFFIX}.png")


def fig2(models):
    lab = {d["instance_id"]: d for d in map(json.loads, (ROOT / "data/cache/labels.jsonl").read_text().splitlines())}
    apn = {r["instance_id"]: r["R@5"] for r in load("apn_cv", "no_llm")}
    fig, ax = plt.subplots(figsize=(7.2, 2.8), dpi=200)
    xt, xl, x = [], [], 0
    for model in models:
        for m in ("mdn", "gdn"):
            rs = load(m, model)
            if not rs:
                continue
            for k, (name, cond) in enumerate((("anchored", True), ("no anchor", False))):
                d = [r["R@5"] - apn[r["instance_id"]] for r in rs if (lab[r["instance_id"]]["n_anchors"] > 0) == cond]
                mu, lo, hi = ci(d)
                ax.bar(x + k * 0.38, mu, 0.34, color=COLORS[m], alpha=1.0 if cond else 0.45)
                ax.errorbar(x + k * 0.38, mu, yerr=[[mu - lo], [hi - mu]], color=INK, lw=0.8, capsize=2)
            xt.append(x + 0.19)
            xl.append(f"{m.upper()}\n{model.replace('gemma4_', '').replace('-it-qat', '')}")
            x += 1.1
    ax.axhline(0, color=INK, lw=0.8)
    ax.set_xticks(xt, xl, fontsize=7)
    ax.set_ylabel("ΔR@5 vs APN\n(solid: anchored, light: no anchor)", color=MUTED, fontsize=8)
    style(ax)
    fig.tight_layout()
    fig.savefig(OUT / f"fig2_anchor_split{SUFFIX}.png")


def fig3():
    a = json.loads((ROOT / "results/audit/graph_audit.json").read_text())["hop_distance_histogram"]
    keys = [k for k in a if k.isdigit()] + [k for k in a if not k.isdigit()]
    fig, ax = plt.subplots(figsize=(7.2, 2.4), dpi=200)
    ax.bar(range(len(keys)), [a[k] for k in keys], color=["#0969da"] * (len(keys) - 1) + ["#8c959f"])
    ax.set_xticks(range(len(keys)), [k if k.isdigit() else "none/>8" for k in keys])
    ax.set_xlabel("Hops from nearest issue anchor to gold symbol (official graph)", color=MUTED)
    ax.set_ylabel("Gold symbols", color=MUTED)
    style(ax)
    fig.tight_layout()
    fig.savefig(OUT / f"fig3_hops{SUFFIX}.png")


if __name__ == "__main__":
    models = [m for m in ("gemma4_e2b-it-qat", "gemma4_e4b-it-qat", "gemma4_12b-it-qat")
              if (ROOT / "results/runs/mdn" / m).exists()]
    for theme in ("light", "dark"):
        set_theme(theme)
        fig1(models)
        fig2(models)
        fig3()
    print("figures:", sorted(p.name for p in OUT.glob("*.png")))

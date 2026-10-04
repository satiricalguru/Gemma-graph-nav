# Research Design — Phases 1–7

Status: **design, pre-registration draft** (2026-10-04). Nothing in this document is a result.
Results are only ever reported from `results/` files produced by committed code.

---

## Phase 1 — Novelty investigation

### 1.1 What already exists (and therefore cannot be claimed)

| Idea in the original proposal | Already done by | Verdict |
|---|---|---|
| Represent the repo as a code graph (files/classes/functions; calls/imports/inherits) | RepoGraph (ICLR'25), LocAgent (ACL'25), CodexGraph, CGM (NeurIPS'25), ARISE (2026) | **Not novel** |
| Give the agent graph tools and let it expand the graph | LocAgent (SearchEntity/TraverseGraph), ARISE (3-tier graph API), RepoNavigator (single jump-to-definition tool + RL, 2025/26) — and the **competition harness itself** ships `get_code_neighbors`, `get_code_subgraph`, `search_similar_code` | **Not novel** |
| Iterative / adaptive graph expansion with pruning | CoSIL (iterative call-graph search + pruner), OrcaLoca (priority queue + distance-aware pruning, ICML'25), GraphLocator (FSE'26), RepoAtlas (Sep 2026, select–project–refresh) | **Not novel** |
| "Initial candidates → confidence-filtered local expansion" | **LARGER** (May 2026): lexical anchors aligned to graph nodes, then confidence-filtered local expansion | **Essentially the original proposal. Not novel.** |
| Graph ranking (PageRank) over a code graph to pick context | Aider "repo map" (software, not a paper) | Not novel as a mechanism |
| Context/observation reduction for SWE agents | The Complexity Trap (NeurIPS'25 workshop), harness study (Sep 2026) | Not novel |
| Small models struggle on long-horizon SWE (looping, low resolve) | SWE-Protégé (Feb 2026) | Known |

Conclusion: **"Graph-Guided Adaptive Repository Navigation" as originally framed is not defensible.**
A judge who knows LocAgent/CoSIL/LARGER (and the judges built the competition's graph tools) would score Novelty ≤ 2.

### 1.2 The gap we can defend

Every prior system lets an LLM drive graph navigation, and each is evaluated with *one* model family at *one* scale
(usually ≥ 32B or frontier APIs), with its *own* graph and tools. That confounds three things:
the graph, the navigation policy, and model capability. Nobody has isolated the
**interaction between model capability and who drives the navigation**.

The closest evidence is from outside software engineering: RLM-on-KG (Apr 2026, text QA over mention graphs) found
LLM-driven exploration beat heuristic traversal for Claude Haiku 4.5 (+4.4 pp) and Gemini, but **not for Gemma 4 E2B (−0.8 pp)**.
That suggests a capability threshold below which the model should *not* navigate. No one has tested this on code graphs,
on repository issues, or along a controlled single-family scale ladder.

The competition makes the controlled study possible: one fixed official graph, one embedding space, one tool API, and a
Gemma 4 ladder (E2B → E4B → 12B → 26B-A4B → 31B) from the same family and quantisation lineage (QAT).

### 1.3 Reframed direction

> **Who should walk the graph?** For a small model, a cheap graph algorithm (lexically anchored personalized PageRank)
> may localize better than the model navigating the same graph with tools, and the advantage should shrink as the
> model grows. If so, the right design for small agents is **delegated navigation**: the algorithm navigates by default,
> and the model is called in only when the algorithm's own ranking is uncertain.

This fits the competition's thesis ("capable agents on consumer hardware") and the judges' expertise (graph learning),
and it directly characterises the competition's own resource.

### 1.4 Stronger alternatives considered

| Alternative | Why not primary |
|---|---|
| RL/LoRA post-training of Gemma 31B for navigation (RepoNavigator-style) | Needs sustained multi-GPU time; Kaggle L4×4 quota (~15 effective h/week) is too small for credible RL in 5 weeks; competes with well-resourced labs |
| New benchmark/resource only | Possible secondary contribution (graph-reachability audit + graph builder), but a resource without a scientific finding is weaker for "Best Paper" |
| GNN encoder fused into Gemma (CGM-style) | CGM already did this at 72B; infeasible on our hardware |

### 1.5 Remaining novelty risks (must re-check before submission)
- A 2026 paper may already run a scale-ladder delegation study on code. **Action:** re-search arXiv in week 4 and week 6;
  cite and adjust if found.
- LARGER's "confidence-filtered expansion" is close to our gate. **Distinction:** LARGER filters *which nodes* to expand inside
  an LLM-driven loop; our gate decides *whether the LLM navigates at all*, using dispersion of the algorithm's scores,
  and is evaluated as a function of model scale. We must state this precisely and cite LARGER.

---

## Phase 2 — Contribution

**Research question.** Given a fixed repository code graph, how should navigation be split between a deterministic
graph algorithm and the LLM, as a function of model capability, to maximise issue localization per unit of model compute?

### Hypotheses (pre-registered; tested on the held-out folds only)

- **H1 — Delegation crossover.** On function-level localization, algorithmic navigation (APN) beats model-driven navigation
  (MDN) for Gemma 4 E2B/E4B/12B, and the MDN − APN gap increases with model size.
  *Falsified if* MDN ≥ APN at the smallest scale, **or** the scale × method interaction is not positive
  (95 % bootstrap CI of the difference-in-differences between the smallest and largest model includes 0).
- **H2 — Gated delegation.** An uncertainty gate that calls the LLM navigator only when APN's ranking is dispersed
  matches the better of {APN, MDN} at every scale (non-inferiority margin 3 pp Recall@5) while using ≥ 50 % fewer
  LLM navigation tokens than MDN. *Falsified if* it is significantly worse than max(APN, MDN) at any scale, or saves < 50 %.
- **H3 — Gate signal validity.** APN's score dispersion predicts APN failure (AUROC > 0.65).
  *Falsified if* AUROC ≤ 0.65; H2 would then be a lucky threshold rather than a mechanism.
- **H4 (secondary, compute-permitting) — Downstream effect.** With a fixed repair stage, better localization from
  the H2 policy raises resolution rate over MDN for 12B (local) and 31B (Kaggle). Reported as exploratory if under-powered.

### Contributions (claimed only if supported by the results)
1. **A controlled delegation study**: APN vs MDN vs gated navigation on the *same* graph, tools, budgets and output format,
   across a five-point Gemma 4 scale ladder. Its value does not depend on H1 holding: a null or reversed result is still a finding.
2. **Uncertainty-gated delegation**: a training-free policy for when a small agent should spend tokens on navigation.
3. **An audit of the official competition graph**: whether gold-edited symbols exist as nodes, how far (in hops) they sit
   from issue-anchored nodes, and which edge types reach them. This gives every participant a reachability ceiling for graph navigation.
4. A reproducible, stdlib-light harness (Apache-2.0) that runs on a 16 GB Mac.

### Claim table

| Claim | Why novel | Test | Falsifier |
|---|---|---|---|
| Small models should not drive graph navigation | Prior work tests one scale per paper; only RLM-on-KG (non-code) hints at a threshold | Paired Recall@5, 5-model ladder, 129 tasks + external set | MDN ≥ APN at E2B/E4B |
| Gating on algorithmic uncertainty recovers the best of both | Gate decides *whether* the LLM navigates, not which node to expand | Non-inferiority + token accounting | Worse than max(APN, MDN), or < 50 % savings |
| Official graph has a measurable reachability ceiling | First audit of this resource | Gold-node coverage, hop distribution | (descriptive, no falsifier) |

---

## Phase 3 — System design

### 3.1 Graph
`G = (V, E, τ)` loaded from the official JSON (`nodes[*].id` = fully-qualified symbol, `edges[*].type`).
Our only augmentation is **containment edges** derived from dotted names (module → class → method). These are
reported separately and ablated, because the official graph may encode structure only through `calls`/import edges.
For the external benchmark we rebuild graphs with `graph/build.py` (Python `ast`, same schema), and validate it by
re-building the official snapshots and reporting node/edge overlap with the official graphs.

### 3.2 Gold localization labels
Parse `patch` hunks → changed line ranges in the base snapshot → enclosing function/method node, found by `ast` spans
over the snapshot files (the graph JSON stores source text, not line numbers). Added top-level code maps to the module node.
Labels are generated by a script, never by hand.

### 3.3 Anchors (shared by every method)
From the issue text, extract identifiers: code spans, dotted paths, `snake_case`/`CamelCase` tokens, traceback frames.
Match them to node names, weighted by inverse node frequency. This produces seed scores `s₀(v)`.
A BM25 score `b(v)` over node source text is computed as a lexical fallback.
(If the HARNESS_README documents the embedding encoder, add an embedding-similarity seed; otherwise the embeddings are
used only through the official `search_similar_code` tool. **Open question until the data is in hand.**)

### 3.4 APN — algorithmic navigation
Personalized PageRank on the symmetrised, type-weighted graph:

  π = α·s + (1 − α)·Wᵀπ,  s = normalize(s₀ + β·b)

Rank by `r(v) = λ·ẑ(π_v) + (1 − λ)·ẑ(b_v)` and return the top-k functions.
Parameters `(α, β, λ, edge-type weights)` are tuned by leave-one-repo-out CV only. This step makes **zero LLM calls**.

### 3.5 MDN — model-driven navigation (LocAgent-style, using the official tools)
A Gemma agent gets the issue plus the anchors (same information as APN) and the official tools
`search_similar_code`, `get_code_neighbors`, `get_code_subgraph`, plus read-only `read_file`.
It has a budget of B tool calls / T tokens and must end with `FINAL: [ranked node ids]`. Invalid ids are dropped,
and the output is padded with the BM25 ranking so every method returns exactly k items.

### 3.6 GDN — gated delegation (ours)
Uncertainty of APN = normalised entropy of the top-K score mass:

  u = −Σᵢ pᵢ log pᵢ / log K,  pᵢ = r₍ᵢ₎ / Σⱼ≤K r₍ⱼ₎

Also force the gate open if no anchor matched.
- If `u < τ`: return APN's ranking (0 LLM calls).
- Else: run MDN seeded with APN's top-k as the starting frontier and a reduced budget b < B, then merge
  (LLM list first, then APN order).

`τ` is chosen by leave-one-repo-out CV. **H3 is tested on the raw `u`, independently of `τ`.**

### 3.7 Downstream repair (H4 only)
One fixed repair prompt shared by all conditions: issue + top-k function sources + file context → unified diff →
`git apply` → official `test_patch` (FAIL_TO_PASS + PASS_TO_PASS). The repair stage is held constant so only localization varies.

### 3.8 Stopping, failures
MDN/GDN stop at `FINAL`, at budget exhaustion, or after 3 consecutive invalid tool calls. Every stop reason is logged.
Malformed tool calls are counted (they are part of the small-model finding) and are never silently fixed.

---

## Phase 4 — Baselines (all return a ranked list of k function nodes from the same candidate set)

| ID | Method | What it controls for |
|---|---|---|
| A | **No retrieval**: LLM sees the issue + file tree, names functions | Prior knowledge / memorisation (contamination probe) |
| B | **Flat retrieval**: BM25 over node text (+ official embedding search if usable) | Is structure needed at all? |
| C | **Static graph**: anchors + fixed k-hop ego-graph, ranked by BM25 (RepoGraph-like) | Structure without adaptivity |
| D | **APN** (PPR) | Algorithm drives navigation |
| E | **MDN** (official tools) | Model drives navigation (LocAgent-like) |
| F | **Agentless-style** hierarchical LLM localization (file → function, no graph) | Strong non-graph LLM baseline |
| G | **GDN** (ours) | Gated delegation |

Fairness rules: identical anchors, candidate set, k, token budgets where the LLM is involved, and the same prompt skeleton
for E/F/G. Every prompt is frozen and committed **before** any held-out evaluation (commit hash recorded in the paper).

---

## Phase 5 — Experiments

**Primary metric:** function-level **Recall@5** (fraction of gold functions in the top 5). Also Acc@5 (all gold functions
in the top 5), plus file-level Acc@1/@5.
**Efficiency (per task):** LLM input/output tokens, LLM calls, tool calls, wall time. For GDN, the fraction of tasks where the gate opened.

| Exp | Content | Where |
|---|---|---|
| E1 main | A–G × {E2B, E4B, 12B} on the 129 official tasks | **local Mac** |
| E2 scale | D, E, G × {26B-A4B, 31B} | **Kaggle L4×4** (planned) |
| E3 generalisation | D, E, G on an external localization set (SWE-bench Lite/Verified localization or LocBench; licence check pending) with graphs from our builder; sliced by repo size, issue type, #gold functions, anchor presence | local (12B) + Kaggle |
| E4 ablations | no containment edges; PPR → BFS; no BM25 term; α sweep; K/τ sweep; MDN without anchors; MDN with ±50 % budget; graph tools removed (read_file/grep only) | local |
| E5 gate validity | AUROC of u for APN failure; risk–coverage curve | local |
| E6 downstream (H4) | repair stage on 12B (local, venv + official wheels) and 31B (Kaggle) | local + Kaggle, compute-permitting |
| E7 graph audit | gold-node coverage, hop distance anchor→gold, edge-type paths | local, no LLM |

**Failure taxonomy (auto-labelled from logs):** no anchor within d hops of gold (wrong initial node); gold unreachable in G
(missing relationship); gold visited but ranked > k (over-expansion / ranking); budget stop before reaching gold
(under-expansion); invalid ids or calls (tool misuse); no `FINAL` (format). For E6 add: patch does not apply; tests fail;
regression. Qualitative examples are drawn at random within each category (seeded), not hand-picked.

**Statistics.** Paired, task-level design. McNemar for Acc@k; paired bootstrap (10k resamples, clustered by repo) for
Recall@k differences; difference-in-differences CI for H1; Holm correction across the primary comparisons
(H1 at each scale, H2 at each scale). Primary runs use T = 0. Variance comes from 3 seeds at T = 0.6 for E and G on
E4B/12B. Effect sizes are reported as pp differences with CIs, not just p-values. With n = 129 paired tasks,
differences under ~8 pp will likely be under-powered; we will say so instead of over-claiming.

**Compute estimate (to be replaced by measurements):** APN/B/C: seconds per task. MDN on 12B: ~10 calls/task,
roughly 3–6 min/task on the M2, so 129 tasks ≈ 8–13 h per configuration. Total local E1 + E4 budget ≈ 80–120 Mac-hours.

---

## Phase 6 — Data

- **Primary:** official competition training set, 129 tasks (fastapi, rich, requests, httpx), graphs, embeddings, snapshots.
  Licence: Apache 2.0, **but the rules forbid redistribution to non-participants during the competition.** The repo
  therefore ships `scripts/get_data.sh` (Kaggle API), never the data.
- **Leakage/contamination:** these are popular public repos, so Gemma may have seen the fixes. Baseline A (no retrieval)
  measures this directly, and we report results with and without tasks where A already succeeds. The hidden test set uses
  private repos, which we cannot access; we say so.
- **Tuning separation:** leave-one-repo-out CV for every tuned parameter (α, β, λ, τ). Prompts frozen before evaluation.
- **External set (E3):** a public localization benchmark with exact version/commit pinned; licence verified before use.
  Only repo snapshots and gold patches are needed, so no Docker is required for localization.
- **Language generality:** the official graph is Python-only. Multi-language is **out of scope** and stated as a limitation.

---

## Phase 7 — Reproducibility

```
README.md  LICENSE (Apache-2.0)  pyproject.toml
configs/      model.toml, experiments/*.toml (one file per table row)
src/ggd/      llm.py  graph/  anchors.py  apn.py  mdn.py  gdn.py  labels.py  repair.py  metrics.py  stats.py
scripts/      get_data.sh  record_env.sh  sanity_benchmark.py  run_experiment.py  make_tables.py
results/      env/  sanity/  runs/<exp>/<model>/<seed>/{trajectories.jsonl, metrics.json}
paper/        paper.md (≤3,000 words), figures/
docs/         RESEARCH_DESIGN.md  ENVIRONMENT.md  EXPERIMENT_LOG.md
```

Every run writes model tag, Ollama version, quantisation, num_ctx, sampling parameters, seed, git commit, hardware,
dataset file hashes and wall time into `metrics.json`. `make_tables.py` regenerates every table in the paper from `results/`.

**Dependency licences:** Python stdlib, numpy (BSD-3), networkx (BSD-3), scipy (BSD-3); BM25 implemented in-repo;
Ollama (MIT); Gemma 4 weights (Apache 2.0, per `ollama show`); vLLM for Kaggle (Apache 2.0). No copyleft dependencies.
Competition data is not redistributed.

# Who Should Walk the Graph?
### For small Gemma 4 agents, code-graph navigation pays off only when the issue gives the model a foothold, and a cheap graph algorithm can decide when to let it navigate

## Abstract

Repository-level coding agents increasingly navigate code graphs with LLM-driven tools. Every published system lets the model drive and evaluates one scaffold at large scale, so it is unknown whether *small* local models should navigate at all. We run a controlled study on the official Gemma 4 Developer Agent graphs (122 Python issues from fastapi, rich, requests and httpx). All methods share the same graph, anchors, candidate set and output format. We compare: (i) a zero-LLM algorithmic navigator (personalized PageRank seeded from issue identifiers, APN); (ii) Gemma navigating the same graph with the competition's own tool semantics (MDN); (iii) gated delegation (GDN), which runs APN and calls the LLM navigator only when APN's ranking is uncertain; and four other baselines. With Gemma 4 E2B and E4B on an Apple M2 (16 GB), our pre-registered hypothesis that the algorithm beats the small model was **not** supported: {{H1_SENTENCE}} The aggregate hides a sharp interaction. When the issue names a symbol present in the graph, model-driven navigation beats APN (E2B: +0.067 Recall@5); when it does not, the model does worse than APN (−0.037). GDN reached the highest Recall@5 for E2B (0.328 vs. 0.293 for APN) while invoking the LLM on 57% of tasks and halving MDN's wall time. A graph audit shows that half the official tasks contain no identifier matching any graph node, which bounds what any anchored graph method can do. The uncertainty signal itself was a weak failure predictor (AUROC 0.64, below our pre-registered 0.65 bar). All code, prompts, per-task logs and statistics are released (Apache-2.0).

## 1. Introduction

The competition asks whether an offline agent on consumer hardware can resolve real issues. Before a model can patch code, it has to find it. Repository graphs are the dominant tool for this: the competition ships call graphs, node embeddings and three graph tools, and a line of work (LocAgent, CoSIL, OrcaLoca, ARISE, LARGER, RepoAtlas) gives LLMs ever richer graph interfaces. These systems share an untested assumption: **the language model should drive the navigation.** They are evaluated with one scaffold, usually at ≥32B or on frontier APIs.

That assumption matters most for small models. Small models loop and misuse tools [13], and on a laptop every navigation turn costs seconds to minutes of prefill. If a deterministic graph algorithm localizes as well as a 2–4B model navigating with tools, the model's budget is better spent on repair. Evidence from outside software engineering suggests a capability threshold: on text knowledge graphs, LLM-driven exploration beat heuristic traversal for strong models but not for Gemma 4 E2B [12].

We ask: **for a fixed code graph, how should navigation be split between an algorithm and the model, and does the answer depend on model capability?** We pre-registered four hypotheses (`docs/RESEARCH_DESIGN.md`, Phase 2, committed before any LLM run):
**H1** the algorithm beats model-driven navigation at small scale;
**H2** gated delegation matches the better of the two while using ≥50% fewer navigation tokens than MDN;
**H3** the gate's uncertainty predicts algorithm failure (AUROC > 0.65);
**H4** (compute-permitting) downstream repair improves.

**Contributions.**
(1) A controlled delegation study that holds graph, tools, anchors, candidates and budgets fixed across six methods and multiple Gemma 4 scales, with repo-held-out tuning and paired, repo-clustered statistics.
(2) An empirical finding: small-model navigation helps only when the issue provides an anchor in the graph. This suggests routing on *anchor availability*, not on model size alone.
(3) Gated delegation, a training-free policy that achieved the highest Recall@5 at E2B at half of MDN's cost. Its gate signal underperformed the pre-registered bar, and we report this openly.
(4) An audit of the official competition graph (gold coverage, anchor availability, hop distances) that any participant can use as a ceiling estimate.

We report hypotheses that failed (H1 at E2B, H3) alongside those that held.

## 2. Related work

**LLM-driven repository graphs.** RepoGraph [1] plugs a code graph into SWE-bench systems; CodexGraph [2] exposes a graph database; LocAgent [3] traverses a heterogeneous code graph with LLM tools; ARISE [4] adds statement-level data flow; CGM [5] puts graph structure into a 72B model's attention; RepoNavigator [6] RL-trains 7–32B agents with a single jump-to-definition tool. All assume the LLM drives navigation, and none varies model scale within a fixed scaffold.

**Adaptive localization.** CoSIL [7] iteratively searches call graphs with an LLM pruner; OrcaLoca [8] schedules LLM actions with a priority queue; GraphLocator [9] grows a causal issue graph; LARGER [10] anchors lexical matches in a graph and performs confidence-filtered expansion inside the agent loop; RepoAtlas [11] refreshes repository views during exploration. Our gate is closest to LARGER's filter, but it decides *whether* the LLM navigates, not *which* node it expands.

**Heuristics vs. LLM exploration; small agents.** RLM-on-KG [12] is the closest non-code study (text QA, no scale ladder within one family). SWE-Protégé [13] documents looping in small SWE agents. Harness studies [14, 15] find scaffolding helps weaker models and simple context management rivals LLM summarization. Agentless [16] shows fixed pipelines are strong baselines; we include an Agentless-style localizer.

## 3. Method

**Graph and labels.** G is the official per-commit graph: nodes are fully qualified symbols with source text. Its only edge type is `calls`, which also encodes class→method links. We add containment edges from dotted ids. Gold labels are derived from each reference patch automatically. Changed base-file lines map to the innermost enclosing definition. Added lines are mapped in post-patch coordinates, and a newly created symbol climbs to its nearest existing parent (e.g., a new method → its class). The patch reconstruction this relies on was exact on all 124 file changes we checked from 300 real commits. Candidates are non-test function, method and class nodes. Seven module-level-only tasks are excluded, leaving 122.

**Anchors (shared by all methods).** Code-like identifiers in the issue (backticked spans, dotted paths, snake/Camel tokens, traceback frames) are matched to node names and weighted by log rarity.

**APN.** Personalized PageRank on the symmetrized graph, π = α·s + (1−α)·Wᵀπ. The restart vector s combines normalized anchor weights with β times the normalized BM25 top-20 over node source. The final score is λ·z(π) + (1−λ)·z(BM25). (α, β, λ) come from a 60-point grid with leave-one-repository-out CV (folds: fastapi | rich | requests+httpx). Selected values were α ∈ {0.15, 0.5}, β = 0.5 and λ ∈ {0.2, 0.35, 0.5}. APN makes zero LLM calls.

**MDN.** Gemma receives the issue plus the same anchors and the official tool semantics. `search_similar_code` is reproduced from the official 256-d embeddings using the harness's rule (resolve the query to a node by exact, then suffix, then case-insensitive, then substring match, and return cosine neighbours). `get_code_neighbors` and `get_code_subgraph` are provided as in the harness, plus `view_symbol` (60 lines of a node's source), which stands in for `read_file` because graph nodes carry no paths. The budget is 8 tool calls, and the model ends with `FINAL: ids`. Unresolvable ids are dropped and the list is padded with BM25 order.

**GDN.** Compute APN and the normalized entropy u of its top-10 scores, with u = 1 if no anchor matched. If u < τ, return APN with no LLM call. Otherwise run MDN seeded with APN's top-10 and a budget of 4, then merge (LLM list first, then APN). τ is chosen per fold by Youden's J on the other folds.

**Other baselines.** BM25; a static 1-hop ego graph around the anchors plus BM25 seeds, ranked by BM25 (RepoGraph-like); no-retrieval (issue + module list, a memorization probe); and Agentless-style two-stage localization (modules, then symbols).

## 4. Experimental setup

| | |
|---|---|
| Data | Official training split: 129 tasks, 122 scored (67 fastapi, 48 rich, 13 requests, 1 httpx); graphs and embeddings as distributed |
| Models (local) | `gemma4:e2b-it-qat`, `gemma4:e4b-it-qat` (Ollama 0.35.0, Q4 QAT), T = 0, seed 1234, thinking off, num_ctx 16384 |
| Hardware | Apple M2, 16 GB unified memory (all reported LLM results) |
| Metrics | Function-level Recall@k (share of gold symbols in top-k), Acc@5 (all gold in top-5), LLM calls, tool calls, invalid calls, wall time |
| Statistics | Paired per task vs. APN-CV; 10k-resample bootstrap clustered by repository; exact McNemar on Acc@5; Holm correction across comparisons |

**Not run.** The 12B model (cut for time and storage after an MLX build of E4B exhausted memory; see the experiment log), 31B on Kaggle L4×4 ({{KAGGLE_STATUS}}), downstream repair (H4), and the external-benchmark generalization experiment. No numbers are reported for these.

## 5. Results

![Recall@5 by method and model](figures/fig1_main.png)

**Table 1.** Localization on 122 tasks (single run, T = 0). Δ is paired versus APN-CV with a 95% repo-clustered bootstrap CI.

{{TABLE1}}

**H1 (algorithm beats small model): not supported.** {{H1_PARAGRAPH}}

**The anchor interaction.** Splitting tasks by whether any issue identifier matches a graph node (63 anchored, 59 not) explains the aggregate (Fig. 2). For E2B on anchored tasks, MDN beats APN by +0.067 R@5 (95% CI −0.003 to +0.144). On un-anchored tasks it trails APN by −0.037 (−0.092 to +0.003). {{E4B_ANCHOR_SENTENCE}} The model is useful as a *local verifier around a foothold*, not as a searcher from scratch.

![MDN/GDN minus APN by anchor status](figures/fig2_anchor_split.png)

**H2 (gated delegation).** {{H2_PARAGRAPH}}

**H3 (gate validity): falsified.** APN's normalized score entropy predicts APN failure (R@5 = 0) with AUROC 0.643, below the pre-registered 0.65. The binary "no anchor matched" signal does better (0.673). Combined with the interaction above, this points to a simpler and better-motivated gate: *let the model navigate when the issue anchors it*.

**Memorization probe.** With only the issue and a module list, E2B reaches R@5 = 0.264, close to BM25 (0.280). Prior exposure to these public repositories therefore does not explain the navigation results, though it may inflate all LLM methods equally. The hidden competition test set uses private repositories.

**Efficiency.** {{EFFICIENCY_PARAGRAPH}}

## 6. Ablations and the graph audit

**Structure vs. lexical.** With default parameters, APN, static 1-hop expansion and BM25 are almost tied on R@5 (0.281, 0.280, 0.280). Graph propagation mainly improves the top rank: R@1 is 0.120 for APN vs. 0.071 for BM25. CV tuning adds only +0.011 R@5.

**Audit of the official graph** (no LLM; Fig. 3). 448 of 499 gold symbols (90%) exist as nodes. **65 of 129 issues contain no identifier matching any node.** Among anchored gold symbols, 45 are at hop 0, and 236 of 499 are unreachable within 8 hops of any anchor. The graph has one edge type (`calls`, 457k edges in total), so imports, inheritance and data flow are not navigable. Our independent AST rebuild agrees with the core packages but differs in scope (the official builder includes nested and conditional definitions and names `docs_src` modules from their inner directory). Node Jaccard is 0.28 overall.

![Hop distance from anchors to gold](figures/fig3_hops.png)

## 7. Failure analysis

Failures are labelled automatically from logs for tasks with R@5 = 0. For E2B MDN, the most common causes are a wrong start without an anchor (25), never reaching gold despite an anchor (20), an empty or missing `FINAL` (17), tool misuse (4), and gold absent from the graph (5). Behaviourally, **E2B issued no tool call at all on 59% of MDN tasks**; it answered from the issue and anchors alone. 27% of its tool calls were invalid, mostly non-existent node ids and invented edge types such as `"incoming"`. {{E4B_BEHAVIOUR}} Typical example: on `fastapi_15030`, E4B spent 7 calls on neighbour expansion from `FastAPI` and ended with an empty list. This is over-expansion without a foothold, the regime where APN does better.

## 8. Discussion

For small local agents, the useful question is less "graph or no graph" than "who navigates, and when". Our data support a division of labour. A cheap algorithm gives a full ranking for free; the model adds value when the issue gives it a concrete starting symbol, and loses value when it must search blind. This matches RLM-on-KG's observation that LLMs help with candidate discovery near evidence [12], and it suggests competition agents should route on anchor availability, falling back to algorithmic or lexical ranking otherwise. The audit also tempers expectations for graph tools on this benchmark: half of the issues give an anchored navigator nothing to start from.

## 9. Limitations

Single run per configuration (T = 0); no seed variance. Only E2B and E4B were run; claims about scale beyond 4B are untested, and H1's "gap shrinks with scale" clause cannot be assessed. 122 tasks drawn mostly from two repositories; the requests+httpx fold has 14 tasks. Localization only; no repair (H4 not run). `view_symbol` replaces `read_file`. Recall@5 counts symbols; partial credit on multi-symbol fixes. Gold labels are automatic and may over-count incidental edits. The E4B MLX build was discarded after a memory failure; E4B results use the QAT GGUF build.

## 10. Conclusion

We asked who should walk the code graph for a small model. The answer is neither "always the model" nor "always the algorithm". Gemma 4 E2B navigation beats a PageRank navigator when the issue anchors it in the graph and loses when it does not, and a gate that delegates conditionally gave the best E2B localization at half the cost. Our gate's uncertainty signal was weaker than predicted; anchor availability is the better switch. Code, logs and the pre-registration are public, and every number here regenerates from `scripts/make_tables.py`.

## References
[1] Ouyang et al. RepoGraph. ICLR 2025, arXiv:2410.14684. [2] Liu et al. CodexGraph. arXiv:2408.03910. [3] Chen et al. LocAgent. ACL 2025, arXiv:2503.09089. [4] Seddik et al. ARISE. arXiv:2605.03117. [5] Tao et al. Code Graph Model. NeurIPS 2025, arXiv:2505.16901. [6] Zhang et al. One Tool Is Enough (RepoNavigator). arXiv:2512.20957. [7] Jiang et al. CoSIL. arXiv:2503.22424. [8] Yu et al. OrcaLoca. ICML 2025, arXiv:2502.00350. [9] GraphLocator. FSE 2026, arXiv:2512.22469. [10] Hu et al. LARGER. arXiv:2605.16352. [11] Zhang et al. RepoAtlas. arXiv:2609.16936. [12] Volpini & Raad. RLM-on-KG. arXiv:2604.17056. [13] Kon et al. SWE-Protégé. arXiv:2602.22124. [14] Lindenbauer et al. The Complexity Trap. arXiv:2508.21433. [15] Fan et al. Harness Design for Coding Agents. arXiv:2609.20804. [16] Xia et al. Agentless. arXiv:2407.01489. [17] Jimenez et al. SWE-bench. ICLR 2024, arXiv:2310.06770. [18] Markowitz et al. Google – The Gemma 4 Developer Agent Paper Track. Kaggle, 2026.

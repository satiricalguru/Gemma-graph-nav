## Abstract

Repository-level coding agents increasingly navigate code graphs with LLM-driven tools, but every published system lets the model drive and reports one scaffold at large scale. It is unknown whether small local models should navigate at all. We run a controlled study on the official Gemma 4 Developer Agent graphs (122 Python issues from fastapi, rich, requests and httpx). All methods share the same graph, anchors, candidate set and output format. We compare a zero-LLM navigator (personalized PageRank seeded from issue identifiers, APN), Gemma navigating the same graph with the competition's tool semantics (MDN), gated delegation (GDN: APN first, LLM only when APN is uncertain), and four baselines, at four scales: Gemma 4 E2B, E4B and 12B on an Apple M2 laptop and the competition's 31B model on Kaggle L4×4. Our pre-registered hypothesis that the algorithm beats small models was **not** supported, but its scale clause was. The advantage of model-driven navigation over APN grows from +0.017 (E2B) to +0.028 (E4B) to **+0.110 Recall@5 at 31B** (95% CI +0.041 to +0.188; Acc@5 McNemar 13 wins / 1 loss, Holm-adjusted p ≈ 0.02). Small models help only when the issue names a symbol in the graph (E4B: +0.095 on anchored issues, −0.042 otherwise); at 31B that penalty disappears. GDN gives the best Recall@5 for E2B and E4B at up to 57% fewer tokens than MDN, but loses to MDN at 31B. We also report a harness defect found after the runs: when the tool budget ran out, the final turn carried no explicit instruction, and 12B (118/122 tasks) and 31B (62/122) often replied with nothing, falling back to BM25. Their MDN scores are therefore lower bounds. A graph audit shows half the official issues name no graph symbol at all. Code, prompts, per-task results and statistics are released (Apache-2.0).

## 1. Introduction

Before a model can patch code it has to find it, and repository graphs are the dominant tool for this. The competition ships call graphs, node embeddings and three graph tools, and a line of work (LocAgent, CoSIL, OrcaLoca, ARISE, LARGER, RepoAtlas) gives LLMs ever richer graph interfaces. These systems share an untested assumption: **the language model should drive the navigation**. They are evaluated with one scaffold, usually at ≥32B or with frontier APIs.

That assumption matters most for small models, which loop and misuse tools [13] and pay seconds to minutes of prefill per navigation turn on a laptop. Evidence from outside software engineering suggests a capability threshold: on text knowledge graphs, LLM-driven exploration beat heuristic traversal for strong models but not for Gemma 4 E2B [12].

We ask: **for a fixed code graph, how should navigation be split between an algorithm and the model, and how does the answer change with model capability?** We pre-registered four hypotheses (`docs/RESEARCH_DESIGN.md`, committed before any LLM run):
**H1** the algorithm beats model-driven navigation at small scale, and the MDN−APN gap grows with scale;
**H2** gated delegation matches the better of the two while using ≥50% fewer navigation tokens than MDN;
**H3** the gate's uncertainty signal predicts algorithm failure (AUROC > 0.65);
**H4** (compute-permitting) downstream repair improves.

**Contributions.**
(1) A controlled delegation study that holds graph, tools, anchors, candidates and budgets fixed across seven methods and four Gemma 4 scales, with repo-held-out tuning and paired, repo-clustered statistics.
(2) A scale-dependent answer. Small models are useful navigators only from a *foothold* (a graph symbol named in the issue). At 31B the model beats the algorithm everywhere, and the advantage grows sixfold from E2B.
(3) Gated delegation: a training-free policy that is the best small-model localizer at roughly half the cost, together with evidence that it should be switched off for large models.
(4) An audit of the official competition graph (gold coverage, anchor availability, hop distances) usable by any participant as a ceiling estimate.

We report failed hypotheses (H1's first clause, H3, H2 at 31B) alongside those that held.

## 2. Related work

**LLM-driven repository graphs.** RepoGraph [1] plugs a code graph into SWE-bench systems; CodexGraph [2] exposes a graph database; LocAgent [3] traverses a heterogeneous code graph with LLM tools; ARISE [4] adds statement-level data flow; CGM [5] puts graph structure into a 72B model's attention; RepoNavigator [6] RL-trains 7–32B agents with a single jump-to-definition tool. All assume the LLM drives navigation, and none varies scale within a fixed scaffold and graph.

**Adaptive localization.** CoSIL [7] iteratively searches call graphs with an LLM pruner; OrcaLoca [8] schedules LLM actions with a priority queue; GraphLocator [9] grows a causal issue graph; LARGER [10] anchors lexical matches in a graph and performs confidence-filtered expansion inside the agent loop; RepoAtlas [11] refreshes repository views during exploration. Our gate is closest to LARGER's filter, but it decides *whether* the LLM navigates, not *which* node it expands.

**Heuristics vs. LLM exploration; small agents.** RLM-on-KG [12] is the closest non-code study (text QA, no single-family scale ladder). SWE-Protégé [13] documents looping in small SWE agents. Harness studies [14, 15] find scaffolding helps weaker models. Agentless [16] shows fixed pipelines are strong baselines, and our results reinforce this at 31B.

## 3. Method

**Graph and labels.** G is the official per-commit graph: nodes are fully qualified symbols with source text. Its only edge type is `calls`, which also encodes class→method links; we add containment edges from dotted ids. Gold labels come from each reference patch automatically. Changed base-file lines map to the innermost enclosing definition. Added lines are mapped in post-patch coordinates, and a newly created symbol climbs to its nearest existing parent (e.g., a new method → its class). The patch reconstruction this relies on was exact on all 124 file changes checked from 300 real commits. Candidates are non-test function, method and class nodes. Seven module-level-only tasks are excluded, leaving 122.

**Anchors (shared by all methods).** Code-like identifiers in the issue (backticked spans, dotted paths, snake/Camel tokens, traceback frames) are matched to node names and weighted by log rarity.

**APN.** Personalized PageRank on the symmetrized graph, π = α·s + (1−α)·Wᵀπ. The restart vector s combines normalized anchor weights with β times the normalized BM25 top-20 over node source. The final score is λ·z(π) + (1−λ)·z(BM25). (α, β, λ) come from a 60-point grid with leave-one-repository-out CV (folds: fastapi | rich | requests+httpx). APN makes zero LLM calls.

**MDN.** Gemma receives the issue, the same anchors, and the official tool semantics. `search_similar_code` is reproduced from the official 256-d embeddings with the harness's rule (resolve the query to a node by exact, then suffix, then case-insensitive, then substring match; return cosine neighbours). `get_code_neighbors` and `get_code_subgraph` behave as in the harness, plus `view_symbol` (60 lines of a node's source), which replaces `read_file` because graph nodes carry no paths. The budget is 8 tool calls, ending with `FINAL: ids`. Unresolvable ids are dropped and the list is padded with BM25 order.

**GDN.** Compute APN and the normalized entropy u of its top-10 scores (u = 1 if no anchor matched). If u < τ, return APN with no LLM call. Otherwise run MDN seeded with APN's top-10 and a budget of 4, then merge (LLM list first, then APN). τ is chosen per fold by Youden's J on the other folds.

**Baselines.** BM25; a static 1-hop ego graph around anchors plus BM25 seeds (RepoGraph-like); no-retrieval (issue + module list, a memorization probe); and Agentless-style two-stage localization (modules, then their symbols, no graph).

## 4. Experimental setup

| | |
|---|---|
| Data | Official training split: 129 tasks, 122 scored (67 fastapi, 48 rich, 13 requests, 1 httpx); graphs and embeddings as distributed |
| Local models | `gemma4:e2b-it-qat`, `gemma4:e4b-it-qat`, `gemma4:12b-it-qat` (Ollama 0.35.0, Q4 QAT) on an Apple M2, 16 GB |
| Cloud model | `gemma-4-31b-it-qat-w4a16-ct` (the competition model), vLLM 0.19.1 via the official harness wheels, Kaggle L4×4 (96 GB) |
| Decoding | T = 0, seed 1234, thinking off; identical prompts and code on both backends |
| Metrics | Function-level Recall@k (share of gold symbols in top-k), Acc@5 (all gold in top-5), LLM calls, tool calls, invalid calls, wall time |
| Statistics | Paired per task vs. APN-CV; 10k-resample bootstrap clustered by repository; exact McNemar on Acc@5; Holm correction across all 12 comparisons |

**Not run.** Agentless and no-retrieval for E4B and 12B; downstream repair (H4); the external-benchmark experiment.

## 5. Results

*Figure 1 (media gallery, image 1): Recall@5 by method and model.*

**Table 1.** Localization on 122 tasks (single run, T = 0). Δ is paired versus APN-CV with a 95% repo-clustered bootstrap CI. Wall time is hardware-specific (M2 for E2B/E4B/12B, L4×4 for 31B). † = most MDN runs ended at the tool budget with an empty reply (see §7); a lower bound.

| Method | Model | R@1 | R@5 | Acc@5 | LLM calls | Tool calls | Prefill tok. | s/task | ΔR@5 vs APN-CV [95% CI] |
|---|---|---|---|---|---|---|---|---|---|
| BM25 | – | .071 | .280 | .221 | 0 | 0 | 0 | ~0 | −.013 [−.090, +.042] |
| **APN-CV** | – | .125 | .293 | .238 | 0 | 0 | 0 | ~0 | reference |
| No retrieval | E2B | .059 | .264 | .205 | 1.0 | 0 | 3,838 | 15.8 | −.029 [−.121, +.029] |
| Agentless-style | E2B | .083 | .239 | .197 | 2.0 | 0 | 6,630 | 29.0 | −.053 [−.243, +.011] |
| MDN | E2B | .168 | .309 | .254 | 2.3 | 1.2 | 1,971 | 12.6 | +.017 [−.067, +.063] |
| **GDN** | E2B | .170 | .328 | .271 | 1.3 | 0.8 | 1,499 | 5.5 | +.035 [+.000, +.071] |
| MDN | E4B | .196 | .321 | .279 | 6.2 | 4.5 | 8,728 | 75.1 | +.028 [−.045, +.119] |
| **GDN** | E4B | .186 | .323 | .262 | 2.5 | 1.8 | 3,777 | 41.4 | +.031 [+.000, +.083] |
| MDN† | 12B | .090 | .288 | .230 | 9.0 | 7.9 | 15,739 | 199.1 | −.004 [−.060, +.050] |
| GDN† | 12B | .142 | .301 | .246 | 2.5 | 2.3 | 3,587 | 56.4 | +.008 [+.000, +.030] |
| No retrieval | 31B | .238 | .357 | .303 | 1.0 | 0 | 3,842 | 4.9 | +.065 [−.031, +.144] |
| Agentless-style | 31B | .290 | **.444** | **.361** | 2.0 | 0 | 5,994 | 6.9 | +.151 [+.000, +.252] |
| MDN† | 31B | **.306** | .402 | .336 | 7.8 | 7.1 | 13,936 | 10.3 | +.110 [+.041, +.188] |
| GDN | 31B | .223 | .354 | .287 | 2.5 | 2.0 | 3,554 | 4.8 | +.061 [+.000, +.132] |

On Acc@5, two comparisons survive Holm correction: 31B MDN (13 wins / 1 loss vs. APN, adjusted p ≈ 0.020) and 31B Agentless (17/2, adjusted p ≈ 0.009). The bootstrap R@5 intervals for these exclude or touch zero, but their Holm-adjusted p-values (0.17, 0.65) do not reach significance. Every E2B/E4B difference is directional only.

**H1: first clause falsified, scale clause supported with a caveat.** MDN is at or above APN at E2B, E4B and 31B, and the gap grows from +0.017 to +0.028 to +0.110 (31B interval clear of zero). 12B (−0.004) breaks the monotone trend, but its MDN run is dominated by the budget-exhaustion defect (§7): 118 of 122 tasks fell back to BM25, so it measures the defect rather than navigation. The answer to "who should walk the graph" flips from "it depends" at 2–4B to "the model" at 31B.

**The foothold interaction.** Splitting tasks by whether any issue identifier matches a graph node (63 anchored, 59 not) explains the small-model aggregate (Fig. 2). On anchored issues MDN beats APN at every scale: +0.067 (E2B), +0.095 (E4B, CI +0.019 to +0.179) and +0.149 (31B, CI +0.072 to +0.237). On un-anchored issues E2B and E4B are *worse* than APN (−0.037, −0.042), while 31B turns positive (+0.068). Small models are useful as local verifiers around a foothold, not as searchers from scratch; at 31B the model can also search.

*Figure 2 (media gallery, image 2): gain of MDN/GDN over APN, split by anchor availability.*

**H2: supported for small models, falsified at 31B.** GDN is non-inferior to the better of APN and MDN for E2B (0.328 vs. 0.309) and E4B (0.323 vs. 0.321). At E4B it uses 57% fewer prefill tokens and 45% less wall time than MDN; at E2B only 24% fewer tokens, because E2B MDN rarely navigates anyway. At 31B, GDN (0.354) falls 0.049 below MDN: the gate withholds navigation from a model that would have used it well. The gate opened on 57% of tasks at every scale.

**H3: falsified.** APN's normalized score entropy predicts APN failure (R@5 = 0) with AUROC 0.643, below the pre-registered 0.65. The binary "no anchor matched" signal does better (0.673).

**Memorization probe.** With only the issue and a module list, E2B reaches R@5 = 0.264 (below BM25), but 31B reaches 0.357, above APN. The larger model plausibly knows these popular public repositories, which inflates all 31B LLM methods to an unknown degree. The competition's hidden test set uses private repositories, where this advantage should shrink.

**Agentless at 31B.** The graph-free two-stage localizer is the strongest 31B method on R@5 and Acc@5 (0.444 / 0.361) but the weakest at E2B (0.239), the sharpest scale reversal in the study.

## 6. Ablations and the graph audit

**Structure vs. lexical.** With default parameters, APN, static 1-hop expansion and BM25 tie on R@5 (0.281 / 0.280 / 0.280). Graph propagation mainly improves the top rank (R@1 0.120 vs. 0.071). CV tuning adds +0.011 R@5.

**Audit of the official graph** (no LLM; Fig. 3). 448 of 499 gold symbols (90%) exist as nodes. **65 of 129 issues contain no identifier matching any node.** Only 45 gold symbols sit at hop 0 from an anchor, and 236 of 499 are unreachable within 8 hops. The graph has one edge type (`calls`), so imports, inheritance and data flow are not navigable.

*Figure 3 (media gallery, image 3): hop distance from issue anchors to gold symbols.*

## 7. Failure analysis

Failures are labelled automatically from logs (tasks with R@5 = 0). **E2B** issued no tool call on 59% of MDN tasks, and 27% of its calls were invalid (non-existent ids, invented edge types such as `"incoming"`). Its leading failures are a wrong start without an anchor (25) and an empty `FINAL` (17). **E4B** calls tools on 93% of tasks (4.5 calls, 10% invalid) but often over-expands without a foothold. On `fastapi_15030` it made 7 graph calls (five of them neighbour expansions) and returned an empty list. **12B** always navigates (7.9 calls, 11% invalid) and **hit the 8-call budget on 118 of 122 tasks**; **31B** (7.1 calls, 2.7% invalid) hit it on 62. **Harness defect.** At budget exhaustion our loop withdrew the tools and re-queried without an explicit instruction. Re-running one 12B task shows the model then returns an empty message, whereas adding "Tool budget exhausted. Reply now with FINAL: …" yields a valid answer. Every budget-stopped task therefore fell back to the BM25 ranking: 118/122 (12B MDN), 64 (12B GDN), 62 (31B MDN), 13 (31B GDN), 10 (E4B MDN), 1 (E2B MDN). The 12B and 31B MDN scores are lower bounds, and budget-stopped tasks are also the harder ones, so the two effects cannot be separated without a re-run. The fix ships as protocol v2 in the released code; all reported numbers use v1.

## 8. Discussion

For 2–4B models a cheap algorithm should rank by default, and the model should be invoked from a foothold. Anchor availability is a better switch than ranking uncertainty, and gated delegation is the most cost-effective small-model localizer we tested. For the 31B competition model, gating is counter-productive. Let the model navigate with a generous budget, or use a two-stage Agentless pipeline, which was strongest here. Half the issues give anchored graph methods nothing to start from.

## 9. Limitations

One run per configuration (T = 0), so no seed variance. Four scales; Agentless and no-retrieval missing for E4B and 12B. The budget-exhaustion defect (§7) makes 12B and 31B MDN lower bounds; a v2 re-run is pending. 122 tasks drawn mostly from two repositories; the requests+httpx fold has 14 tasks. 31B results run on different hardware and serving stack (vLLM vs. Ollama) with identical code and prompts, and likely benefit from memorization of public repositories. Localization only; no repair (H4 not run). `view_symbol` replaces `read_file`. Gold labels are automatic and may over-count incidental edits.

## 10. Conclusion

Who should walk the code graph depends on who is walking. Gemma 4 E2B and E4B navigate well only from a foothold in the issue, and a gate that delegates conditionally is their best and cheapest localizer. At 31B the model beats the algorithm on every slice, and gating gets in its way. Every number regenerates from the released code, and the hypotheses were committed before any model was run.

## References
[1] Ouyang et al. RepoGraph. ICLR 2025, arXiv:2410.14684. [2] Liu et al. CodexGraph. arXiv:2408.03910. [3] Chen et al. LocAgent. ACL 2025, arXiv:2503.09089. [4] Seddik et al. ARISE. arXiv:2605.03117. [5] Tao et al. Code Graph Model. NeurIPS 2025, arXiv:2505.16901. [6] Zhang et al. One Tool Is Enough (RepoNavigator). arXiv:2512.20957. [7] Jiang et al. CoSIL. arXiv:2503.22424. [8] Yu et al. OrcaLoca. ICML 2025, arXiv:2502.00350. [9] GraphLocator. FSE 2026, arXiv:2512.22469. [10] Hu et al. LARGER. arXiv:2605.16352. [11] Zhang et al. RepoAtlas. arXiv:2609.16936. [12] Volpini & Raad. RLM-on-KG. arXiv:2604.17056. [13] Kon et al. SWE-Protégé. arXiv:2602.22124. [14] Lindenbauer et al. The Complexity Trap. arXiv:2508.21433. [15] Fan et al. Harness Design for Coding Agents. arXiv:2609.20804. [16] Xia et al. Agentless. arXiv:2407.01489. [17] Jimenez et al. SWE-bench. ICLR 2024, arXiv:2310.06770. [18] Markowitz et al. Google – The Gemma 4 Developer Agent Paper Track. Kaggle, 2026.


**Code, data-download scripts, per-task results and pre-registration:** https://github.com/satiricalguru/Gemma-graph-nav

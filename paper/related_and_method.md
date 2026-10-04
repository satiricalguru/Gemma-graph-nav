<!-- Draft fragments; assembled into paper.md once results are final. -->

## Related work

**Repository graphs for SWE agents.** RepoGraph [1] adds a line-level code graph as a plug-in to SWE-bench systems; CodexGraph [2] exposes a graph database to the agent; LocAgent [3] builds a heterogeneous graph (contain/import/invoke/inherit) and lets an LLM traverse it with dedicated tools, reporting strong localization with a fine-tuned 32B model; ARISE [4] extends graphs to statement-level data flow; CGM [5] integrates graph structure into a 72B model's attention. RepoNavigator [6] trains (RL) agents that use a single jump-to-definition tool, from 7B to 32B. All of these assume **the LLM drives navigation**, and each reports a single scaffold at one or a few scales.

**Adaptive / iterative localization.** CoSIL [7] iteratively searches module and function call graphs with an LLM-driven pruner; OrcaLoca [8] schedules LLM-proposed actions with a priority queue and distance-aware pruning; GraphLocator [9] grows a causal issue graph; LARGER [10] anchors lexical matches in a graph and performs confidence-filtered local expansion inside the agent's search loop; RepoAtlas [11] refreshes multimodal repository views as exploration proceeds. Our gate is related to LARGER's filter but answers a different question: not *which* node to expand, but *whether the LLM should navigate at all*.

**Heuristics vs. LLM-driven graph exploration.** Outside software engineering, RLM-on-KG [12] found LLM-driven exploration of mention graphs beat heuristic traversal for strong models but not for Gemma 4 E2B. We test the analogous question on code graphs with a single model family across scales.

**Small SWE agents and harness design.** SWE-Protégé [13] shows small models loop and benefit from sparse expert help; harness studies [14, 15] find that scaffolding helps weaker models and that simple context management is competitive with LLM summarization. Agentless [16] shows a fixed localize-then-repair pipeline is a strong baseline.

## Method (summary)

Graph G = official competition graph (nodes = fully-qualified symbols with source text; edges = `calls`, which also encode class→method links) plus containment edges from dotted ids. All methods output a ranked list of non-test function/method/class nodes.

* **Anchors.** Code-like identifiers in the issue (code spans, dotted paths, snake/Camel tokens, traceback frames) matched to node names, weighted by rarity.
* **APN.** Personalized PageRank with restart vector s = norm(anchors) + β·norm(BM25 top-20); final score λ·z(π) + (1−λ)·z(BM25). (α, β, λ) chosen by leave-one-repository-out CV. Zero LLM calls.
* **MDN.** Gemma with the official tool semantics (`search_similar_code` reproduced from the official embeddings with the harness's name-resolution rule; `get_code_neighbors`; `get_code_subgraph`) plus `view_symbol`; budget 8 tool calls; ends with `FINAL: ids`.
* **GDN.** Run APN; if its normalized top-10 score entropy u < τ (or anchors matched nothing → u = 1) return APN; else run MDN seeded with APN's top-10 and a budget of 4. τ per fold by Youden's J on the other folds.
* **Baselines.** no-retrieval (issue + module list), BM25, static 1-hop ego graph, Agentless-style two-stage localization.

## References
[1] Ouyang et al. RepoGraph. ICLR 2025. arXiv:2410.14684
[2] Liu et al. CodexGraph. arXiv:2408.03910
[3] Chen et al. LocAgent. ACL 2025. arXiv:2503.09089
[4] Seddik et al. ARISE. arXiv:2605.03117 (2026)
[5] Tao et al. Code Graph Model (CGM). NeurIPS 2025. arXiv:2505.16901
[6] Zhang et al. One Tool Is Enough (RepoNavigator). arXiv:2512.20957
[7] Jiang et al. CoSIL. arXiv:2503.22424
[8] Yu et al. OrcaLoca. ICML 2025. arXiv:2502.00350
[9] GraphLocator. FSE 2026. arXiv:2512.22469
[10] Hu et al. LARGER. arXiv:2605.16352 (2026)
[11] Zhang et al. RepoAtlas. arXiv:2609.16936 (2026)
[12] Volpini & Raad. RLM-on-KG. arXiv:2604.17056 (2026)
[13] Kon et al. SWE-Protégé. arXiv:2602.22124 (2026)
[14] Lindenbauer et al. The Complexity Trap. arXiv:2508.21433
[15] Fan et al. An Empirical Study of Harness Design for Coding Agents. arXiv:2609.20804 (2026)
[16] Xia et al. Agentless. arXiv:2407.01489
[17] Jimenez et al. SWE-bench. ICLR 2024. arXiv:2310.06770
[18] Yang et al. SWE-agent. NeurIPS 2024. arXiv:2405.15793
[19] Markowitz et al. Google – The Gemma 4 Developer Agent Paper Track. Kaggle, 2026.

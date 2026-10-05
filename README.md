<div align="center">

<img src="assets/gemma-color.svg" width="96" alt="Gemma logo">

# Gemma-graph-nav

### Should a small LLM navigate your code graph, or should the graph navigate for it?

**A controlled study of code-graph navigation across the Gemma 4 scale ladder: E2B and E4B on a 16 GB MacBook, 31B on Kaggle.**

[![License](https://img.shields.io/badge/license-Apache_2.0-blue.svg)](LICENSE)
![Python](https://img.shields.io/badge/python-3.11+-3776AB?logo=python&logoColor=white)
![Model](https://img.shields.io/badge/model-Gemma_4_E2B_%7C_E4B_%7C_31B-4285F4?logo=google&logoColor=white)
![Runs on](https://img.shields.io/badge/runs_on-Ollama_%C2%B7_M2_16GB-black?logo=apple)
![Kaggle](https://img.shields.io/badge/Kaggle-Gemma_4_Developer_Agent_Paper_Track-20BEFF?logo=kaggle&logoColor=white)

[**📄 Paper**](paper/paper.md) · [**📊 Results**](#-results) · [**⚡ Quick start**](#-quick-start) · [**🔬 Reproduce everything**](#-reproduce-every-number)

</div>

---

## 💡 The idea in 30 seconds

Coding agents increasingly use **code graphs** (who calls whom) to find the code they need to fix. Every published system lets the **LLM drive** that navigation, and tests it on big models.

On a laptop, every navigation step of a small model costs seconds. So we asked:

> **Is it better to let the model walk the graph, let a cheap graph algorithm do it, or decide case by case, and does the answer change with model size?**

We held the graph, tools, inputs and budgets fixed and compared **6 localization methods** at **3 model sizes** on the **122 official Kaggle tasks** (fastapi, rich, requests, httpx).

## 🏆 Headline findings

| | Finding |
|---|---|
| 📈 | **The bigger the model, the more it should navigate.** Gemma navigating the graph beats the graph algorithm by +1.7 (E2B), +2.8 (E4B) and **+11.0 points** of Recall@5 at 31B (95% CI +4.1 to +18.8; 13 wins / 1 loss on Acc@5). |
| 🎯 | **Small models need a foothold.** When the issue names a symbol in the graph, E4B beats the algorithm by **+9.5 points**; when it doesn't, it does **worse** (−4.2). At 31B that penalty disappears. |
| 🚦 | **Gated delegation is the best small-model localizer.** Run the free algorithm first and call the LLM only when it's unsure: best Recall@5 at E2B and E4B with up to **57% fewer tokens**. At 31B it gets in the way, so switch it off. |
| 🧱 | **At 31B a simple two-stage pipeline wins.** The graph-free Agentless-style localizer reaches **R@5 0.444**, the best of any method, after being the worst at E2B. |
| 🕳️ | **Half the issues give a graph nothing to grab.** 65 of 129 official issues mention no identifier that matches any graph node. |
| ❌ | **We report what failed.** "The algorithm beats small models" (H1, first clause) and our uncertainty signal (H3, AUROC 0.643 < 0.65) both missed. |

## 📊 Results

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="paper/figures/fig1_main_dark.png">
    <img src="paper/figures/fig1_main.png" width="760" alt="Recall@5 by method and model">
  </picture>
</p>

| Method | Model | R@1 | **R@5** | Acc@5 | LLM calls | s / task |
|---|---|---:|---:|---:|---:|---:|
| BM25 | – | .071 | .280 | .221 | 0 | ~0 |
| **Graph algorithm (APN)** | – | .125 | .293 | .238 | 0 | ~0 |
| No retrieval | E2B | .059 | .264 | .205 | 1.0 | 15.8 |
| Agentless-style | E2B | .083 | .239 | .197 | 2.0 | 29.0 |
| Model navigates (MDN) | E2B | .168 | .309 | .254 | 2.3 | 12.6 |
| 🚦 **Gated (GDN)** | E2B | .170 | **.328** | .271 | 1.3 | **5.5** |
| Model navigates (MDN) | E4B | .196 | .321 | .279 | 6.2 | 75.1 |
| 🚦 **Gated (GDN)** | E4B | .186 | **.323** | .262 | 2.5 | 41.4 |
| No retrieval | 31B | .238 | .357 | .303 | 1.0 | 4.9 |
| Agentless-style | 31B | .290 | **.444** | **.361** | 2.0 | 6.9 |
| Model navigates (MDN) | 31B | **.306** | .402 | .336 | 7.8 | 10.3 |
| Gated (GDN) | 31B | .223 | .354 | .287 | 2.5 | 4.8 |

<sub>122 tasks, single run, T = 0. E2B/E4B: Apple M2 16 GB, Ollama 0.35.0, Q4 QAT. 31B: `gemma-4-31b-it-qat-w4a16-ct`, vLLM on Kaggle L4×4 (so wall times aren't comparable across rows). R@k is the share of the functions the reference fix changes that appear in the top k. After Holm correction, 31B MDN and 31B Agentless are significantly better than the algorithm on Acc@5; the small-model differences are directional. The 31B model likely knows these public repos (no-retrieval scores 0.357), see the paper.</sub>

### 🎯 It's all about the foothold

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="paper/figures/fig2_anchor_split_dark.png">
    <img src="paper/figures/fig2_anchor_split.png" width="760" alt="Gain over the graph algorithm, split by anchor availability">
  </picture>
</p>

Solid bars are issues that name a symbol in the graph; light bars are issues that don't. E2B and E4B are good **local verifiers around a starting point** but poor **searchers from scratch**; 31B is positive on both.

### 🕸️ How far is the bug from what the issue mentions?

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="paper/figures/fig3_hops_dark.png">
    <img src="paper/figures/fig3_hops.png" width="760" alt="Hop distance from issue anchors to the code that was fixed">
  </picture>
</p>

Audit of the official competition graph: 90% of fixed symbols exist as nodes, but only 45 sit exactly where the issue points, and 236 of 499 are unreachable within 8 hops of anything the issue mentions.

## 🧠 The methods

```text
issue ─► anchors (identifiers in the issue that match graph nodes)
            │
            ├─► APN  personalized PageRank + BM25 ............ 0 LLM calls
            ├─► MDN  Gemma explores with the official graph tools (≤ 8 calls)
            └─► GDN  run APN ─► uncertain? ─► yes: MDN seeded with APN top-10 (≤ 4 calls)
                                           └─► no : return APN
```

| | What it is | Code |
|---|---|---|
| **APN** | Anchored personalized PageRank, tuned with leave-one-repo-out CV | [`src/ggd/apn.py`](src/ggd/apn.py) |
| **MDN** | Gemma using a faithful replica of the competition's `search_similar_code` / `get_code_neighbors` / `get_code_subgraph` | [`src/ggd/tools.py`](src/ggd/tools.py) |
| **GDN** | Entropy-gated delegation between the two | [`src/ggd/methods.py`](src/ggd/methods.py) |
| Baselines | BM25, static 1-hop graph, no-retrieval, Agentless-style | [`src/ggd/methods.py`](src/ggd/methods.py) |

## ⚡ Quick start

```bash
git clone https://github.com/satiricalguru/gemma-graph-nav && cd gemma-graph-nav
ollama pull gemma4:e2b-it-qat                    # 4.3 GB, runs on any 16 GB Mac
python3 scripts/sanity_benchmark.py              # 5 auto-graded probes: tools, diffs, long context
```

Pure Python standard library plus numpy. No GPU, no Docker, no API keys. Swap models with `GGD_MODEL=...`, or point at any OpenAI-compatible server with `GGD_BACKEND=openai`.

## 🔬 Reproduce every number

```bash
# Accept the rules at kaggle.com/competitions/gemma-4-developer-agent; Kaggle token in ~/.kaggle/access_token
python3 scripts/get_data_parallel.py --with-embeddings          # graphs + embeddings (~1 GB)
mkdir -p data/repos && (cd data/repos && for r in fastapi/fastapi Textualize/rich psf/requests encode/httpx; do git clone --filter=blob:none https://github.com/$r; done)
python3 scripts/prepare_tasks.py      # gold labels + graph audit
python3 scripts/tune_apn.py           # graph algorithm, leave-one-repo-out
python3 scripts/gate_cv.py            # gate threshold + H3
MODELS="gemma4:e2b-it-qat gemma4:e4b-it-qat" scripts/run_queue.sh
python3 scripts/make_tables.py && python3 scripts/analyze.py && python3 scripts/make_figures.py
python3 -m unittest discover -s tests
```

Every run logs model tag, quantization, Ollama version, git commit, seed and data hash. Sanitized per-task results are in [`results/runs`](results/runs), the full run history in [`docs/EXPERIMENT_LOG.md`](docs/EXPERIMENT_LOG.md), and the pre-registered hypotheses in [`docs/RESEARCH_DESIGN.md`](docs/RESEARCH_DESIGN.md).

> ⚠️ **16 GB Mac tip:** avoid the `*-mlx` Ollama tags. `gemma4:e4b-mlx` reserved 18 GB at a 16K context and filled the disk with swap. The `*-it-qat` tags use 5–8 GB.

<details>
<summary><b>📁 Repository layout</b></summary>

```text
src/ggd/        graph, labels, anchors+BM25, APN, tools, methods, LLM backends, stats
scripts/        data, labels/audit, tuning, experiment runner, tables, figures, Kaggle kernel
results/        audit, tuning, sanitized per-task runs, tables
paper/          paper.md + figures
docs/           research design (pre-registration), environment, experiment log
tests/          unit tests for labels, graph, ranking, metrics, stats
```
</details>

<details>
<summary><b>🚧 Limitations and what's next</b></summary>

- Single run per configuration; three sizes (E2B, E4B, 31B); 12B not run.
- 122 tasks, mostly from fastapi and rich; localization only (no patch generation).
- 31B hit the 8-call navigation budget on half the tasks, so its MDN score is likely an underestimate.
- Next steps: 12B scale point, anchor-based gating, larger budgets at 31B, downstream repair.
</details>

## 📜 License and data

Code: **Apache 2.0**. Gemma is a trademark of Google LLC; the logo is from [LobeHub Icons](https://github.com/lobehub/lobe-icons) (MIT) and is used only to indicate the model this project is built on. Competition data is **not** included and must not be redistributed; it is downloaded by script into `data/` (git-ignored).

<div align="center"><sub>Built for the Kaggle <i>Google – The Gemma 4 Developer Agent Paper Track</i> · 2026</sub></div>

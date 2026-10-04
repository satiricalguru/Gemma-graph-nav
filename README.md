# Who Should Walk the Graph?
### Algorithmic vs. model-driven code-graph navigation for small Gemma 4 agents

Code for the Kaggle *Google – The Gemma 4 Developer Agent Paper Track* paper. Paper: `paper/paper.md`.
Design and pre-registered hypotheses: `docs/RESEARCH_DESIGN.md`. Every run: `docs/EXPERIMENT_LOG.md`.

## What it does
Given an issue and the official competition code graph, each method returns a ranked list of
functions/classes to edit (localization), scored against labels derived automatically from the reference patch.

| Method | LLM? | File |
|---|---|---|
| APN: anchored personalized PageRank | no | `src/ggd/apn.py` |
| MDN: Gemma navigates with the official graph tools | yes | `src/ggd/methods.py` |
| GDN: APN, with MDN only when APN is uncertain | sometimes | `src/ggd/methods.py` |
| BM25, static k-hop graph, no-retrieval, Agentless-style | mixed | `src/ggd/methods.py` |

## Reproduce (macOS / Apple Silicon, 16 GB, ~2 GB disk for data)
```bash
# 0. accept rules at kaggle.com/competitions/gemma-4-developer-agent; token in ~/.kaggle/access_token
python3 scripts/get_data_parallel.py --with-embeddings        # tasks, graphs, embeddings (no snapshots)
mkdir -p data/repos && cd data/repos && for r in fastapi/fastapi Textualize/rich psf/requests encode/httpx; do git clone --filter=blob:none https://github.com/$r; done; cd ../..
python3 scripts/prepare_tasks.py                              # gold labels + graph audit (E7)
python3 scripts/run_experiment.py --method bm25               # zero-LLM baselines
python3 scripts/run_experiment.py --method static_graph
python3 scripts/tune_apn.py                                   # leave-one-repo-out APN (apn_cv)
python3 scripts/gate_cv.py                                    # H3 + per-fold gate threshold
ollama pull gemma4:e2b-it-qat && ollama pull gemma4:e4b-it-qat
MODELS="gemma4:e2b-it-qat gemma4:e4b-it-qat" scripts/run_queue.sh   # MDN, GDN (+ baselines for E2B)
python3 scripts/make_tables.py && python3 scripts/analyze.py && python3 scripts/make_figures.py
python3 -m unittest discover -s tests
```
31B (Kaggle L4×4): `scripts/make_kaggle_kernel.py --user <you> --setup-from <official getting-started .ipynb>` then
`kaggle kernels push -p kaggle/kernel_31b`.

Settings: T=0, seed 1234, thinking off, num_ctx 16384, Ollama 0.35.0, Apple M2 16 GB.
Model/backends are configurable in `configs/model.toml` or with `GGD_MODEL`, `GGD_BACKEND` (`ollama` | `openai`), `GGD_NUM_CTX`.

**Note:** do not use the `*-mlx` Ollama tags on a 16 GB Mac. `gemma4:e4b-mlx` reserved 18 GB at a 16K context and filled the disk with swap.

## Data policy and license
Competition data (Apache-2.0) must not be redistributed during the competition. It is downloaded into `data/`
(git-ignored). Code: Apache-2.0 (`LICENSE`). Dependencies: Python stdlib and numpy (BSD-3).

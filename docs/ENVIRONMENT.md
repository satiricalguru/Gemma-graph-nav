# Local environment & model selection

Recorded 2026-10-04. Raw record: `results/env/env_2026-10-04_m2.txt`.

## Hardware / software (measured)
| Item | Value |
|---|---|
| Machine | Apple M2 (8-core CPU, 8-core GPU), **16 GB unified memory** |
| OS | macOS 27.0.1 (26A434) |
| Free disk | **~8 GB** after model pull (blocking constraint, see below) |
| Ollama | 0.35.0 (client and server) |
| Python | 3.14.2 (stdlib only for the harness so far) |
| Docker | **not installed** (the official sandbox uses Docker; localization experiments don't need it) |

## Available Gemma 4 tags (source: ollama.com/library/gemma4/tags, fetched 2026-10-04)
E2B (4.3–10 GB, 128K) · E4B (6.1–16 GB, 128K) · 12B (7.2–25 GB, 256K) · 26B-A4B MoE (16–53 GB, 256K) ·
31B dense (19–64 GB, 256K) · cloud variants. Each comes in QAT / Q4_K_M / Q8 / BF16 / MLX / NVFP4 / MXFP8 builds.

## Decision: `gemma4:12b-it-qat` as the primary local model
`ollama show`: 11.9B parameters, **Q4_0 (quantisation-aware trained)**, 262,144 max context, tools + thinking supported, Apache-2.0.

| Candidate | Fits 16 GB? | Verdict |
|---|---|---|
| 31B (19–20 GB at 4-bit) | No: weights exceed physical memory | Kaggle L4×4 only (this is also the only model the main track allows) |
| 26B-A4B MoE (16–19 GB) | No: only 3.8B active, but all 25B weights must be resident | Kaggle only |
| **12B QAT (7.2 GB)** | **Yes: 8.0 GB resident, 100 % GPU at num_ctx 32768** | **Strongest model that runs reliably here.** QAT keeps 4-bit quality close to BF16 and matches the QAT lineage of the competition's 31B model |
| 12B Q8 (13 GB) / BF16 (24 GB) | Q8 leaves no headroom; BF16 doesn't fit | Rejected |
| E4B (6.1–9.5 GB) | Yes, about 4× faster | Fast iteration model and ladder point |
| E2B (4.3 GB) | Yes | Ladder point only |

Trade-off, measured: 12B is slow at long context, so agent loops must keep prompts short.

## Sanity benchmark (measured; `scripts/sanity_benchmark.py`, T = 0, seed 1234, think = off, num_ctx 32768)
| Probe | e4b-mlx (nvfp4) | 12b-it-qat (Q4_0) |
|---|---|---|
| P1 repo structure | pass | pass |
| P2 native tool call + use result | pass | pass |
| P3 code reasoning (off-by-one trace) | pass | pass |
| P4 unified diff applies + test passes | pass | pass |
| P5 2-hop lookup in 31.7K-token prompt | pass (138 s) | pass (**889 s**) |
| Generation speed (short prompts) | 17–37 tok/s | 10–13 tok/s |
| Long-prompt prefill | ≈ 230 tok/s | ≈ 36 tok/s |

Interpretation: both models clear the bar for tool use, diffs, and long-context retrieval. **These probes are too easy to
rank models**; they are a smoke test only. Capability differences will come from E1.
Note: the E4B run used the pre-installed `e4b-mlx` (NVFP4) build. Ladder experiments will use the `*-it-qat` tags for consistency.

## Reproduce
```bash
ollama pull gemma4:12b-it-qat
GGD_MODEL=gemma4:12b-it-qat python3 scripts/sanity_benchmark.py --ctx-tokens 20000
scripts/record_env.sh
```

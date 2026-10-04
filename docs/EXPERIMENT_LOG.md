# Experiment log

Append-only. Each entry: date (UTC), what was run, exact config, where (LOCAL-MAC / KAGGLE / PLANNED), output path.

| Date | Run | Where | Model / quant | Config | Output | Outcome |
|---|---|---|---|---|---|---|
| 2026-10-04 | Sanity benchmark | LOCAL-MAC (M2, 16 GB) | gemma4:e4b-mlx / NVFP4 | T=0, seed 1234, ctx 32768, think off, Ollama 0.35.0 | results/sanity/gemma4_e4b-mlx_think0.json | 5/5 |
| 2026-10-04 | Sanity benchmark | LOCAL-MAC (M2, 16 GB) | gemma4:12b-it-qat / Q4_0 QAT | same | results/sanity/gemma4_12b-it-qat_think0.json | 5/5; long-ctx probe 889 s |
| — | E1–E7 | PLANNED | — | see docs/RESEARCH_DESIGN.md | — | not run |
| 2026-10-04 | Pipeline smoke test (5 psf/requests commits, commit msg as issue) | LOCAL-MAC | none (APN/BM25) + e4b-mlx for LLM methods on 1 commit | — | not saved (not an experiment) | pipeline runs end to end; numbers meaningless (messages name the fix) |
| 2026-10-04 | Patch-reconstruction check of labels.apply_file | LOCAL-MAC | — | 300 requests commits | console | 124/124 file changes reconstructed exactly |
| 2026-10-04 | Data download (tasks, 127 graphs, 127 embeddings); snapshots replaced by public git clones at base_commit (snapshot tgz are 37–320 MB each) | LOCAL-MAC | — | scripts/get_data_parallel.py --with-embeddings | data/ (git-ignored) | 129 tasks; 0 base commits missing from public clones |
| 2026-10-04 | E7 graph audit + gold labels | LOCAL-MAC | no LLM | scripts/prepare_tasks.py | results/audit/graph_audit.json | 122/129 tasks have function/class gold; 448/499 gold symbols in official graph; 65/129 tasks have no anchor |
| 2026-10-04 | B/C/D baselines, default params | LOCAL-MAC | no LLM | scripts/run_experiment.py --method {bm25,static_graph,apn} | results/runs/{bm25,static_graph,apn}/no_llm | R@5 0.280/0.280/0.281 |
| 2026-10-04 | APN leave-one-repo-out tuning (60-point grid) | LOCAL-MAC | no LLM | scripts/tune_apn.py | results/tuning/apn_cv.json, results/runs/apn_cv | held-out R@5 0.293 |
| 2026-10-04 | H3 gate validity + per-fold tau | LOCAL-MAC | no LLM | scripts/gate_cv.py | results/tuning/gate_cv.json | AUROC 0.643 (< 0.65 pre-registered bar: H3 falsified); no-anchor AUROC 0.673 |
| 2026-10-04 | E1 LLM queue started (mdn, gdn, agentless, no_retrieval × e2b-it-qat, e4b-mlx, 12b-it-qat), num_ctx 16384, T=0, seed 1234, think off | LOCAL-MAC | see models | scripts/run_queue.sh | results/runs/*/gemma4_*/seed1234 | running |
| 2026-10-04 | E2 31B kernel pushed (mdn, gdn, no_retrieval, agentless) | KAGGLE L4x4 | gemma-4-31b-it-qat-w4a16-ct (W4A16), vLLM | scripts/make_kaggle_kernel.py | kaggle output results_31b.tgz | queued |
| 2026-10-04 | Scope change (user decision): 12B runs limited to mdn+gdn; no_retrieval/agentless baselines only for e2b, e4b (and 31B on Kaggle) | — | — | — | — | — |
| 2026-10-04 | e4b-mlx (MLX engine) reserved 18 GB at ctx 16384 -> swap filled disk; partial e4b-mlx runs moved to results/runs_discarded. E4B point switched to gemma4:e4b-it-qat. Scope cut (user, time/storage): E4B mdn+gdn only; local 12B dropped | LOCAL-MAC | — | — | — | — |

| method | model | seed | n | R@1 | R@5 | R@10 | Acc@5 | llm_calls | tool_calls | invalid_tool_calls | prefill_tokens | context_chars | wall_s | gate_open_rate | errors |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| agentless | gemma4_e2b-it-qat | seed1234 | 122 | 0.0825 | 0.2393 | 0.3225 | 0.1967 | 2.0 | 0.0 | 0.0 | 6630 | 20271 | 29.0 |  | 0 |
| apn | no_llm | seed0 | 122 | 0.1204 | 0.2813 | 0.3789 | 0.2213 | 0.0 | 0.0 | 0.0 | 0 | 0 | 0.0 |  | 0 |
| apn_cv | no_llm | seed0 | 122 | 0.1252 | 0.2927 | 0.3815 | 0.2377 | 0.0 | 0.0 | 0.0 | 0 | 0 | 0.0 |  | 0 |
| bm25 | no_llm | seed0 | 122 | 0.071 | 0.2801 | 0.3439 | 0.2213 | 0.0 | 0.0 | 0.0 | 0 | 0 | 0.0 |  | 0 |
| gdn | gemma4_e2b-it-qat | seed1234 | 122 | 0.1699 | 0.3275 | 0.3897 | 0.2705 | 1.33 | 0.77 | 0.16 | 1499 | 4166 | 5.5 | 0.566 | 0 |
| gdn | gemma4_e4b-it-qat | seed1234 | 122 | 0.186 | 0.3234 | 0.3826 | 0.2623 | 2.48 | 1.84 | 0.22 | 3777 | 11581 | 41.4 | 0.566 | 0 |
| mdn | gemma4_e2b-it-qat | seed1234 | 122 | 0.1681 | 0.3094 | 0.363 | 0.2541 | 2.28 | 1.22 | 0.33 | 1971 | 4341 | 12.6 |  | 0 |
| mdn | gemma4_e4b-it-qat | seed1234 | 122 | 0.1958 | 0.3212 | 0.3565 | 0.2787 | 6.24 | 4.46 | 0.46 | 8728 | 23322 | 75.1 |  | 0 |
| no_retrieval | gemma4_e2b-it-qat | seed1234 | 122 | 0.059 | 0.2635 | 0.3311 | 0.2049 | 1.0 | 0.0 | 0.0 | 3838 | 11029 | 15.8 |  | 0 |
| static_graph | no_llm | seed0 | 122 | 0.071 | 0.2801 | 0.3773 | 0.2213 | 0.0 | 0.0 | 0.0 | 0 | 0 | 0.0 |  | 0 |

Paired vs APN-CV on R@5 (method − APN-CV; 95% CI from repo-clustered bootstrap; Holm-adjusted p)
| comparison | n | ΔR@5 | 95% CI | p_holm | McNemar Acc@5 (wins/losses, p) |
|---|---|---|---|---|---|
| agentless|gemma4_e2b-it-qat|seed1234 | 122 | -0.053 | [-0.243, +0.011] | 0.925 | 4/9, p=0.267 |
| bm25|no_llm|seed0 | 122 | -0.013 | [-0.090, +0.042] | 1 | 4/6, p=0.754 |
| gdn|gemma4_e2b-it-qat|seed1234 | 122 | +0.035 | [+0.000, +0.071] | 1 | 4/0, p=0.125 |
| gdn|gemma4_e4b-it-qat|seed1234 | 122 | +0.031 | [+0.000, +0.083] | 1 | 3/0, p=0.25 |
| mdn|gemma4_e2b-it-qat|seed1234 | 122 | +0.017 | [-0.067, +0.063] | 1 | 5/3, p=0.727 |
| mdn|gemma4_e4b-it-qat|seed1234 | 122 | +0.028 | [-0.045, +0.119] | 1 | 8/3, p=0.227 |
| no_retrieval|gemma4_e2b-it-qat|seed1234 | 122 | -0.029 | [-0.121, +0.029] | 1 | 3/7, p=0.344 |
| static_graph|no_llm|seed0 | 122 | -0.013 | [-0.090, +0.042] | 1 | 4/6, p=0.754 |

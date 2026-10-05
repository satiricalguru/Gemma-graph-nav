## agentless|gemma4_31b-it-qat-w4a16
- failures: {'no_anchor_wrong_start': 30, 'never_reached_gold': 13, 'gold_not_in_graph': 5}
- behaviour: {"zero_tool_call_rate": 1.0, "mean_tool_calls": 0.0, "invalid_call_rate": 0.0, "stop_reasons": {"done": 122}, "tool_mix": "see private logs"}
- slices: {"anchored": {"n": 63, "R@5": 0.5843613500730079, "APN_R@5": 0.4195685226657265, "delta_vs_apn": 0.16479282740728143, "ci95": [0.06155737126625631, 0.27063834950175925]}, "no_anchor": {"n": 59, "R@5": 0.29339031966150614, "APN_R@5": 0.15716486902927582, "delta_vs_apn": 0.1362254506322303, "ci95": [0.05988700564971751, 0.22033898305084745]}}

## agentless|gemma4_e2b-it-qat
- failures: {'never_reached_gold': 27, 'no_anchor_wrong_start': 48, 'gold_not_in_graph': 5}
- behaviour: {"zero_tool_call_rate": 1.0, "mean_tool_calls": 0.0, "invalid_call_rate": 0.0, "stop_reasons": {"done": 122}, "tool_mix": "see private logs"}
- slices: {"anchored": {"n": 63, "R@5": 0.37304434053221736, "APN_R@5": 0.4195685226657265, "delta_vs_apn": -0.04652418213350912, "ci95": [-0.1443856554967666, 0.048579396020916495]}, "no_anchor": {"n": 59, "R@5": 0.09643040575243965, "APN_R@5": 0.15716486902927582, "delta_vs_apn": -0.06073446327683616, "ci95": [-0.1271186440677966, -0.0042372881355932195]}}

## gdn|gemma4_31b-it-qat-w4a16
- failures: {'never_reached_gold': 20, 'budget_or_empty_final': 13, 'gold_not_in_graph': 5, 'no_anchor_wrong_start': 21, 'visited_gold_but_not_ranked': 2}
- behaviour: {"zero_tool_call_rate": 0.4344262295081967, "mean_tool_calls": 2.0163934426229506, "invalid_call_rate": 0.02032520325203252, "stop_reasons": {"done": 53, "budget": 13, "final": 54, "final_empty": 2}, "tool_mix": "see private logs"}
- slices: {"anchored": {"n": 63, "R@5": 0.45660555970276345, "APN_R@5": 0.4195685226657265, "delta_vs_apn": 0.03703703703703704, "ci95": [0.0, 0.08465608465608465]}, "no_anchor": {"n": 59, "R@5": 0.24362572455792797, "APN_R@5": 0.15716486902927582, "delta_vs_apn": 0.08646085552865214, "ci95": [0.029560129136400323, 0.15748587570621467]}}

## gdn|gemma4_e2b-it-qat
- failures: {'never_reached_gold': 21, 'no_anchor_wrong_start': 33, 'gold_not_in_graph': 5, 'budget_or_empty_final': 5, 'tool_misuse': 2, 'visited_gold_but_not_ranked': 1}
- behaviour: {"zero_tool_call_rate": 0.8032786885245902, "mean_tool_calls": 0.7704918032786885, "invalid_call_rate": 0.20212765957446807, "stop_reasons": {"done": 53, "final": 58, "budget": 9, "invalid_calls": 1, "final_empty": 1}, "tool_mix": "see private logs"}
- slices: {"anchored": {"n": 63, "R@5": 0.45660555970276345, "APN_R@5": 0.4195685226657265, "delta_vs_apn": 0.03703703703703704, "ci95": [0.0, 0.08465608465608465]}, "no_anchor": {"n": 59, "R@5": 0.1896507447354905, "APN_R@5": 0.15716486902927582, "delta_vs_apn": 0.03248587570621469, "ci95": [-0.009887005649717515, 0.08898305084745763]}}

## gdn|gemma4_e4b-it-qat
- failures: {'never_reached_gold': 21, 'budget_or_empty_final': 13, 'visited_gold_but_not_ranked': 1, 'gold_not_in_graph': 5, 'no_anchor_wrong_start': 23, 'tool_misuse': 3}
- behaviour: {"zero_tool_call_rate": 0.45901639344262296, "mean_tool_calls": 1.8442622950819672, "invalid_call_rate": 0.12, "stop_reasons": {"done": 53, "budget": 14, "final": 50, "final_empty": 4, "invalid_calls": 1}, "tool_mix": "see private logs"}
- slices: {"anchored": {"n": 63, "R@5": 0.45660555970276345, "APN_R@5": 0.4195685226657265, "delta_vs_apn": 0.03703703703703704, "ci95": [0.0, 0.08465608465608465]}, "no_anchor": {"n": 59, "R@5": 0.18117616846430407, "APN_R@5": 0.15716486902927582, "delta_vs_apn": 0.02401129943502825, "ci95": [-0.012711864406779662, 0.07062146892655367]}}

## mdn|gemma4_31b-it-qat-w4a16
- failures: {'budget_or_empty_final': 42, 'visited_gold_but_not_ranked': 4, 'gold_not_in_graph': 5, 'no_anchor_wrong_start': 7, 'never_reached_gold': 2}
- behaviour: {"zero_tool_call_rate": 0.0, "mean_tool_calls": 7.065573770491803, "invalid_call_rate": 0.02668213457076566, "stop_reasons": {"budget": 62, "final": 59, "final_empty": 1}, "tool_mix": "see private logs"}
- slices: {"anchored": {"n": 63, "R@5": 0.5685314242545951, "APN_R@5": 0.4195685226657265, "delta_vs_apn": 0.1489629015888687, "ci95": [0.07235634019689748, 0.23650467268327138]}, "no_anchor": {"n": 59, "R@5": 0.22496147919876736, "APN_R@5": 0.15716486902927582, "delta_vs_apn": 0.06779661016949153, "ci95": [-0.007062146892655366, 0.14689265536723162]}}

## mdn|gemma4_e2b-it-qat
- failures: {'never_reached_gold': 20, 'no_anchor_wrong_start': 25, 'budget_or_empty_final': 17, 'gold_not_in_graph': 5, 'tool_misuse': 4}
- behaviour: {"zero_tool_call_rate": 0.5901639344262295, "mean_tool_calls": 1.221311475409836, "invalid_call_rate": 0.2684563758389262, "stop_reasons": {"final": 91, "final_empty": 27, "invalid_calls": 3, "budget": 1}, "tool_mix": "see private logs"}
- slices: {"anchored": {"n": 63, "R@5": 0.4863959157301978, "APN_R@5": 0.4195685226657265, "delta_vs_apn": 0.0668273930644713, "ci95": [-0.002796011853051261, 0.143635231870526]}, "no_anchor": {"n": 59, "R@5": 0.1204417051874679, "APN_R@5": 0.15716486902927582, "delta_vs_apn": -0.036723163841807904, "ci95": [-0.09180790960451977, 0.0028248587570621473]}}

## mdn|gemma4_e4b-it-qat
- failures: {'never_reached_gold': 11, 'budget_or_empty_final': 22, 'no_anchor_wrong_start': 32, 'gold_not_in_graph': 5}
- behaviour: {"zero_tool_call_rate": 0.07377049180327869, "mean_tool_calls": 4.459016393442623, "invalid_call_rate": 0.10294117647058823, "stop_reasons": {"final": 90, "final_empty": 21, "budget": 10, "invalid_calls": 1}, "tool_mix": "see private logs"}
- slices: {"anchored": {"n": 63, "R@5": 0.5144313274257402, "APN_R@5": 0.4195685226657265, "delta_vs_apn": 0.09486280476001371, "ci95": [0.018636096413874193, 0.17940131152074268]}, "no_anchor": {"n": 59, "R@5": 0.1147919876733436, "APN_R@5": 0.15716486902927582, "delta_vs_apn": -0.0423728813559322, "ci95": [-0.11440677966101695, 0.022598870056497175]}}

## no_retrieval|gemma4_31b-it-qat-w4a16
- failures: {'no_anchor_wrong_start': 40, 'never_reached_gold': 19, 'gold_not_in_graph': 5}
- behaviour: {"zero_tool_call_rate": 1.0, "mean_tool_calls": 0.0, "invalid_call_rate": 0.0, "stop_reasons": {"done": 122}, "tool_mix": "see private logs"}
- slices: {"anchored": {"n": 63, "R@5": 0.4919272399987627, "APN_R@5": 0.4195685226657265, "delta_vs_apn": 0.07235871733303623, "ci95": [-0.016177437869785635, 0.16528915064886102]}, "no_anchor": {"n": 59, "R@5": 0.21366204417051873, "APN_R@5": 0.15716486902927582, "delta_vs_apn": 0.05649717514124294, "ci95": [-0.018361581920903952, 0.13700564971751414]}}

## no_retrieval|gemma4_e2b-it-qat
- failures: {'no_anchor_wrong_start': 45, 'never_reached_gold': 25, 'gold_not_in_graph': 5}
- behaviour: {"zero_tool_call_rate": 1.0, "mean_tool_calls": 0.0, "invalid_call_rate": 0.0, "stop_reasons": {"done": 122}, "tool_mix": "see private logs"}
- slices: {"anchored": {"n": 63, "R@5": 0.38692544853097244, "APN_R@5": 0.4195685226657265, "delta_vs_apn": -0.03264307413475406, "ci95": [-0.12002227791701475, 0.05342115921488913]}, "no_anchor": {"n": 59, "R@5": 0.13174114021571648, "APN_R@5": 0.15716486902927582, "delta_vs_apn": -0.025423728813559324, "ci95": [-0.09887005649717513, 0.04096045197740113]}}

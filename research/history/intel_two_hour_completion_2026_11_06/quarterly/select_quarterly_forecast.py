import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

OUT = Path(__file__).resolve().parent
cpu = json.loads((OUT / 'cpu_smooth_fade_results.json').read_text())
client = json.loads((OUT / 'quarterly_2027_2030_results.json').read_text())['cases']['preferred']['client']
client_annual = json.loads((OUT / 'client_quarterly_results.json').read_text())['cases']['preferred']['annual_2027_2030']
cpu_history = json.loads((OUT / 'quarterly_delivery_results.json').read_text())
client_policy = json.loads((OUT / 'client_policy_before_calculation.json').read_text())
annual = []
for year in range(2027, 2031):
    cpu_q = [r for r in cpu['quarterly'] if r['year'] == year]
    client_q = [r for r in client['quarterly'] if r['year'] == year]
    cpu_a = next(r for r in cpu['annual_2027_2030'] if r['year'] == year)
    client_a = next(r for r in client_annual if r['year'] == year)
    cpu_u = sum(r['unit_index_Q4_2026_100'] for r in cpu_q)
    client_u = sum(r['unit_index_Q4_2026_100'] for r in client_q)
    cpu_r = sum(r['CPU_revenue_B'] for r in cpu_q)
    client_r = sum(r['client_revenue_B'] for r in client_q)
    other = sum(r['Other_CCPG_B'] for r in client_q)
    assert abs(cpu_r - cpu_a['CPU_revenue_B']) < 1e-9
    assert abs(client_r - client_a['client_revenue_B']) < 1e-9
    assert abs(client_r + other - client_a['CCPG_revenue_B']) < 1e-9
    annual.append({'year': year, 'CPU_revenue_B': cpu_r, 'CPU_unit_index_sum': cpu_u, 'CPU_weighted_ASP_index': cpu_r / (6.5257 / 10000) / cpu_u, 'CPU_unit_growth': cpu_a['unit_growth'], 'CPU_ASP_growth': cpu_a['ASP_growth'], 'client_revenue_B': client_r, 'client_unit_index_sum': client_u, 'client_weighted_ASP_index': client_r / (4.87575 / 10000) / client_u, 'client_unit_growth': client_a['client_unit_growth'], 'client_ASP_growth': client_a['client_ASP_growth'], 'Other_CCPG_B': other, 'CCPG_revenue_B': client_r + other, '2027_growth_boundary': '2027 annual units and ASP depend on selected historical level calibration; 2028 onward uses model-to-model weighted growth.'})
for rows, revenue_key, scale in [(cpu['quarterly'], 'CPU_revenue_B', 6.5257 / 10000), (client['quarterly'], 'client_revenue_B', 4.87575 / 10000)]:
    assert len(rows) == 16
    for r in rows:
        assert abs(r[revenue_key] - scale * r['unit_index_Q4_2026_100'] * r['ASP_index_Q4_2026_100']) < 1e-10
sources = ['quarterly_policy_before_calculation.json', 'client_policy_before_calculation.json', 'quarterly_extension_policy_before_calculation.json', 'cpu_smooth_fade_policy_before_calculation.json']
result = {
    'created_utc': datetime.now(timezone.utc).isoformat(),
    'selection': 'Preferred CPU follows the independently selected smooth sequential fade; preferred client follows the owned seasonal recovery path.',
    'chronology': {'CPU2027_policy_selected_utc': json.loads((OUT / sources[0]).read_text())['selected_utc'], 'client_policy_selected_utc': client_policy['selected_utc'], 'extension_policy_selected_utc': json.loads((OUT / sources[2]).read_text())['selected_utc'], 'smooth_CPU_policy_selected_utc': json.loads((OUT / sources[3]).read_text())['selected_utc'], 'price_boundary': 'Quarterly agent selected and recommended smooth CPU policy before receiving root message reporting $54.68 from earlier annual case. Root then adopted smooth policy before calculating its new equity value. No smooth-path rate was revised after seeing that earlier price.'},
    'policy_hashes': {name: hashlib.sha256((OUT / name).read_bytes()).hexdigest() for name in sources},
    'anchors': {'CPU_Q42026_revenue_B': 6.5257, 'client_Q42026_revenue_B': 4.87575, 'unit_index_Q42026': 100, 'ASP_index_Q42026': 100, 'classification': 'Q42026 is analyst guidance-based estimate, not an actual reported quarter. Index is not physical chips.'},
    'CPU_quarterly': cpu['quarterly'],
    'client_quarterly': client['quarterly'],
    'annual_rows': annual,
    'editable_drivers': {'CPU2027_QoQ_units': [0, .05, .10, .10], 'CPU2027_QoQ_ASP': [0, .02, .03, .03], 'CPU2028_QoQ_units': [.03] * 4, 'CPU2028_QoQ_ASP': [.0075] * 4, 'CPU2029_QoQ_units': [.025] * 4, 'CPU2029_QoQ_ASP': [.005] * 4, 'CPU2030_QoQ_units': [.02] * 4, 'CPU2030_QoQ_ASP': [.005] * 4, 'client2027_QoQ_units': [-.05, .10, .15, .05], 'client2027_QoQ_ASP': [0, .01, .01, .01], 'client2028_2030_annual_units': [.05, .05, .03], 'client2028_2030_annual_ASP': [.02, .02, .02], 'client2028_2030_quarter_unit_weights': [.23, .24, .26, .27], 'client2028_2030_ASP_rule': 'Constant sequential ASP rate within each year solved from priorQ4 to selected unit-weighted annualASP target.', 'Other_CCPG2027_B': 4.8279, 'Other_CCPG2028_2030_growth': [.08, .08, .08], 'Other_CCPG_quarter_weights': [.25] * 4},
    'formula_contract': {'quarterly_revenue': 'Q42026 revenue * current unit index /100 * current ASP index /100', 'annual_revenue': 'Sum four quarterly revenues', 'annual_unit_growth': 'Current sum of quarterly unit indices /prior-year sum -1', 'annual_ASP_growth': '(Current annualrevenue/current annualunits)/(prior annualrevenue/prior annualunits)-1; same revenue/index scale cancels', 'client_seasonal_units': 'Prior-year annualunitindexsum*(1+annualunitgrowth)*fixedquarterweight'},
    'calibration': {'CPU_history': cpu_history['historical_calibration'], 'CPU_history_reconciliation': cpu_history['history_revenue_reconciliation'], 'CPU_conditional_ratio_bounds': cpu_history['calibration_interval_sensitivities'], 'client': client_policy['historical_normalization']},
    'limits': ['All sequential growth rates are analyst assumptions informed by timing and direction of supply and demand evidence; none are independently measured available package capacity.', 'Rounded historical disclosures do not uniquely identify quarterly Intel unit levels or ASP levels. Annual2027volume/ASP split changes with calibration; forecast dollar totals do not.', 'Resource capacity, wafer starts, cores and finished CPU packages are different denominators. No conversion multiplier is inferred.', 'Fab28 hit already sits in Q4anchor. Q1 flat CPU revenue does not subtract a second blanket$300M.', 'Client recovery assumes destocking wanes, not that PCmemory constraints disappear in2027.', 'The annual20/15/10 CPU unit-growth schedule is retained in quarterly_2027_2030_results.json as a control, not selected.', 'Old annualtarget schedule is a favorable execution hurdle, not mathematically impossible and not independently verified.'],
    'controls': {'annual_policy_control': 'quarterly_2027_2030_results.json:cases.preferred', 'slower_delivery': 'quarterly_2027_2030_results.json:cases.slower', 'old_target_favorable': 'quarterly_2027_2030_results.json:cases.old_target_favorable'},
}
(OUT / 'selected_quarterly_forecast.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(annual, indent=2))

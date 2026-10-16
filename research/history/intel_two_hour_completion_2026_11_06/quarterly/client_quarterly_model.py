import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

OUT = Path(__file__).resolve().parent
policy_path = OUT / 'client_policy_before_calculation.json'
policy = json.loads(policy_path.read_text())
old_path = OUT.parents[1] / 'pricing_and_competition_review_2026_11_04/intel_server_ASP_mix_operating_policy.json'
old = json.loads(old_path.read_text())
anchor = policy['Q4_2026_anchor']['client_revenue_B']
base_2026 = policy['historical_normalization']['2026_client_revenue_B']
other_2027 = policy['Other_CCPG_policy']['2027_annual_B']


def build_case(name: str) -> dict:
    units = asp = 100.
    quarterly = []
    for quarter, (ug, ag, other_weight) in enumerate(zip(policy[f'{name}_2027_QoQ']['units'], policy[f'{name}_2027_QoQ']['ASP'], policy['Other_CCPG_policy']['2027_quarter_weights']), 1):
        units *= 1 + ug
        asp *= 1 + ag
        revenue = anchor * units * asp / 10000
        other = other_2027 * other_weight
        quarterly.append({'year': 2027, 'quarter': quarter, 'unit_growth_QoQ': ug, 'ASP_growth_QoQ': ag, 'unit_index_Q4_2026_100': units, 'ASP_index_Q4_2026_100': asp, 'client_revenue_B': revenue, 'Other_CCPG_B': other, 'CCPG_revenue_B': revenue + other})
    revenue = sum(row['client_revenue_B'] for row in quarterly)
    yearly_units = sum(row['unit_index_Q4_2026_100'] for row in quarterly)
    weighted_asp = revenue / (anchor / 10000) / yearly_units
    history_asp_ratio = policy['historical_normalization']['Q4_2026_ASP_over_full2026_weighted_ASP_chosen']
    implied_asp_growth = weighted_asp / 100 * history_asp_ratio - 1
    implied_unit_growth = revenue / base_2026 / (1 + implied_asp_growth) - 1
    other = other_2027
    annual = [{'year': 2027, 'client_revenue_B': revenue, 'Other_CCPG_B': other, 'CCPG_revenue_B': revenue + other, 'client_unit_growth': implied_unit_growth, 'client_ASP_growth': implied_asp_growth, 'unit_ASP_boundary': 'Derived from assumed neutral Q4/full-year2026 ASP calibration, not identified annual unit forecast.'}]
    for year, ug, ag, og in zip(range(2028, 2031), policy[f'{name}_2028_2030_annual']['unit_growth'], policy[f'{name}_2028_2030_annual']['ASP_growth'], policy['Other_CCPG_policy']['2028_2030_annual_growth']):
        revenue *= (1 + ug) * (1 + ag)
        other *= 1 + og
        annual.append({'year': year, 'client_revenue_B': revenue, 'Other_CCPG_B': other, 'CCPG_revenue_B': revenue + other, 'client_unit_growth': ug, 'client_ASP_growth': ag, 'unit_ASP_boundary': 'Analyst forward assumption'})
    for row in annual:
        old_row = next(r for r in old['annual_rows'] if r['year'] == row['year'])
        row['old_CCPG_revenue_B'] = old_row['CCPG_revenue_B']
        row['CCPG_delta_vs_old_B'] = row['CCPG_revenue_B'] - old_row['CCPG_revenue_B']
    h1 = sum(row['client_revenue_B'] for row in quarterly[:2])
    h2 = sum(row['client_revenue_B'] for row in quarterly[2:])
    sensitivities = []
    for ratio in policy['historical_normalization']['Q4_2026_ASP_over_full2026_weighted_ASP_sensitivity']:
        ag = weighted_asp / 100 * ratio - 1
        ug = annual[0]['client_revenue_B'] / base_2026 / (1 + ag) - 1
        sensitivities.append({'assumed_Q4_2026_ASP_over_full2026': ratio, 'implied_2027_unit_growth': ug, 'implied_2027_ASP_growth': ag})
    return {'quarterly_2027': quarterly, 'annual_2027_2030': annual, 'H1_client_B': h1, 'H2_client_B': h2, 'H2_vs_H1_revenue_growth': h2 / h1 - 1, 'historical_ASP_calibration_sensitivity': sensitivities, '2028_flat_Q42027_carryover': {'unit_growth': 4 * units / yearly_units - 1, 'ASP_growth': asp / weighted_asp - 1}}


cases = {name: build_case(name) for name in ['preferred', 'slower']}
preferred = cases['preferred']
target = policy['old_2027_control']['client_revenue_B']
h2_multiplier = (target - preferred['H1_client_B']) / preferred['H2_client_B']
favorable = []
previous_units = 100.
for row in preferred['quarterly_2027']:
    multiplier = h2_multiplier if row['quarter'] >= 3 else 1.
    revised = dict(row)
    revised['unit_index_Q4_2026_100'] *= multiplier
    revised['client_revenue_B'] *= multiplier
    revised['CCPG_revenue_B'] = revised['client_revenue_B'] + revised['Other_CCPG_B']
    revised['unit_growth_QoQ'] = revised['unit_index_Q4_2026_100'] / previous_units - 1
    previous_units = revised['unit_index_Q4_2026_100']
    favorable.append(revised)
assert abs(sum(r['client_revenue_B'] for r in favorable) - target) < 1e-9
result = {'computed_utc': datetime.now(timezone.utc).isoformat(), 'policy_sha256': hashlib.sha256(policy_path.read_bytes()).hexdigest(), 'cases': cases, 'old_target_hurdle': {'old_client_B': target, 'old_CCPG_B': policy['old_2027_control']['CCPG_revenue_B'], 'preferred_H1_client_B': preferred['H1_client_B'], 'required_H2_client_B': target - preferred['H1_client_B'], 'required_H2_average_CCPG_B': (target - preferred['H1_client_B'] + other_2027 / 2) / 2, 'H2_client_revenue_vs_H1_growth': (target - preferred['H1_client_B']) / preferred['H1_client_B'] - 1, 'required_H2_units_multiplier_vs_preferred': h2_multiplier, 'favorable_schedule_holding_old_annual_target': favorable, 'classification': 'Reverse hurdle. Stronger inventory normalization/product-cycle gains could deliver it; no disclosed OEM orders verify this schedule.'}, 'guards': ['PC system ASP is not Intel CPU ASP', 'AMD client unit growth is competitive evidence, not an Intel unit forecast', 'Other CCPG timing is a bookkeeping allocation', '2028growth does not mechanically restore the old2027target', 'No price target calculated']}
(OUT / 'client_quarterly_results.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps({'cases': {name: {'CCPG_quarters': [r['CCPG_revenue_B'] for r in case['quarterly_2027']], 'annual_CCPG': [r['CCPG_revenue_B'] for r in case['annual_2027_2030']], 'annual_client': [r['client_revenue_B'] for r in case['annual_2027_2030']]} for name, case in cases.items()}, 'old_hurdle': result['old_target_hurdle']}, indent=2))

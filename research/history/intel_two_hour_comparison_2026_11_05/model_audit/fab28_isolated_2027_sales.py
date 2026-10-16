import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


OUT = Path(__file__).resolve().parent
policy_path = OUT / 'fab28_isolated_2027_sales_policy.json'
ns = {'__file__': str(OUT / 'extended_scenarios.py')}
exec((OUT / 'extended_scenarios.py').read_text().split('\ncases = ')[0], ns)
rows = copy.deepcopy(ns['base_rows'])
delta = -.3
row = rows[2027]
profit = row['DCAI_product_margin'] * row['DCAI_revenue_B']
row['CPU_revenue_B'] += delta
row['DCAI_revenue_B'] += delta
row['capital_denominator_revenue_B'] += delta
row['EBIT_B'] += .5 * delta
row['DCAI_product_margin'] = (profit + .5 * delta) / row['DCAI_revenue_B']
for year, change in [(2027, .1 * delta), (2028, -.1 * delta)]:
    rows[year]['WC_cash_use_B'] += change
    rows[year]['net_operating_investment_B'] += change
    ns['close_cash'](rows[year])
before = ns['value'](rows)
base_before = ns['value'](ns['base_rows'])
ns['OTHER_ASSETS'] -= 1.215
after = ns['value'](rows)
base_after = ns['value'](ns['base_rows'])
summary = {}
for label, case, base in [('before_claims_overlay', before, base_before), ('after_claims_overlay', after, base_after)]:
    target = case['values'][2030]['price_USD']
    summary[label] = {'December2026_planning_value_USD': case['values'][2026]['price_USD'], 'December2030_target_USD': target, 'annual_price_return_from52_22': (target / ns['ENTRY']) ** (1 / ns['YEARS']) - 1, 'planning_delta_vs_matching_base_USD': case['values'][2026]['price_USD'] - base['values'][2026]['price_USD'], 'target_delta_vs_matching_base_USD': target - base['values'][2030]['price_USD']}
tax = rows[2027]['tax_rate']
annual_owner_cash_loss = .3 * .5 * (1 - tax)
target_delta_identity = -annual_owner_cash_loss / ns['SHARES']
planning_delta_identity = ((-.3 * .5 * (1 - tax) + .03) / (1 + ns['RATE']) - .03 / (1 + ns['RATE']) ** 2) / ns['SHARES']
assert abs(summary['after_claims_overlay']['target_delta_vs_matching_base_USD'] - target_delta_identity) < 1e-12
assert abs(summary['after_claims_overlay']['planning_delta_vs_matching_base_USD'] - planning_delta_identity) < 1e-12
unit_factor_2027 = 1.2 * rows[2027]['CPU_revenue_B'] / ns['base_rows'][2027]['CPU_revenue_B']
result = {'computed_utc': datetime.now(timezone.utc).isoformat(), 'policy_sha256': hashlib.sha256(policy_path.read_bytes()).hexdigest(), 'policy': json.loads(policy_path.read_text()), 'summary': summary, 'operating_delta_B': {'2027_revenue': -.3, '2027_EBIT': -.15, '2027_aftertax_operating_profit': -.1275, '2027_WC_cash_use': -.03, '2028_WC_cash_use': .03, '2030_cash_vs_base': after['treasury'][2030]['ending_economic_cash_B'] - base_after['treasury'][2030]['ending_economic_cash_B']}, 'required_units': {'2027_unit_growth_if_ASP_unchanged': unit_factor_2027 - 1, '2028_unit_growth_to_restore_base_absolute_level': 1.5 / unit_factor_2027 - 1, 'base2028_unit_growth': .25}, 'independent_delta_check': {'planning_per_share': planning_delta_identity, 'target_per_share': target_delta_identity}, 'before_overlay_values': before['values'], 'after_overlay_values': after['values'], 'rows': rows, 'treasury': after['treasury'], 'coverage_finding': 'The original2027host31.475088B CPUforecast equals21.8577B2026anchor times1.2units times1.2ASP. It has no explicit quarterlyFab28delivery/costadjustment or offset;2026Q4guide is already net. Therefore no separate annual netting can be proved, but subtracting0.3B from the full-yearforecast is a conditional diagnostic, not an unambiguous correction.'}
result['source_locator'] = {'url': 'https://www.marketbeat.com/earnings/reports/2026-10-29-intel-co-stock/', 'locator': 'Q3 2026 published Quartr transcript, David Zinsner Q&A at39:31; browsed lines1036–1045', 'facts': 'Early assessment about300MQ4 revenue impact, likely similarQ1; most wafer scrapping expectedQ4 and noadditionalQ1scrapping expected.', 'provenance_limit': 'Published transcript on a third-party host, not independently audio-verified. Preparedremarks alone did not quantifyQ1.'}
result['anchor_qualification'] = {'net_2026_CPU_anchor_B': 21.8577, 'hypothetical_2026_anchor_before_0_3B_hit_B': 22.1577, 'same_1_44_growth_on_net_anchor_2027_B': 21.8577 * 1.44, 'same_1_44_growth_on_hypothetical_pre_hit_anchor_2027_B': 22.1577 * 1.44, 'mechanically_carried_gap_B': .3 * 1.44, 'interpretation': 'This algebra shows why absence of a named2027event row does not prove the annualforecast is gross of theevent. It does not identify actualgross2027demand or establish that the2027damage is alreadyoffset. Further0.3Bstress is conditional.'}
result['model_locators'] = [{'file': 'pricing_and_competition_review_2026_11_04/intel_server_ASP_mix_operating_policy.json', 'lines': '10–37,187–207', 'facts': 'Ownedannualunit/ASP forecasts,50%consolidatedEBITretention, heldFoundry,capital andWCconventions;31.475088CPUannualforecast.'}, {'file': 'intel_benchmark_rebuild_2026_11_05/evidence_to_operating_profit_bridge.json', 'line': 54, 'facts': '21.8577×1.2×1.2annualidentity.'}]
(OUT / 'fab28_isolated_2027_sales_results.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps({key: result[key] for key in ['summary', 'operating_delta_B', 'required_units', 'independent_delta_check', 'coverage_finding']}, indent=2))

import hashlib
import json
from datetime import datetime, timezone
from math import prod
from pathlib import Path


OUT = Path(__file__).resolve().parent
RESEARCH = OUT.parents[1]
POLICY_PATH = OUT / 'selected_margin_policy.json'
QUARTER_PATH = OUT.parent / 'quarterly/selected_quarterly_forecast.json'
CLIENT_PATH = OUT.parent / 'quarterly/client_quarterly_results.json'
HOST_PATH = RESEARCH / 'pricing_and_competition_review_2026_11_04/intel_server_ASP_mix_operating_policy.json'
HISTORY_PATH = RESEARCH / 'intel_benchmark_rebuild_2026_11_05/margin_evidence.json'
policy = json.loads(POLICY_PATH.read_text())
selected = policy['preferred']
quarter = json.loads(QUARTER_PATH.read_text())
client = json.loads(CLIENT_PATH.read_text())
host = {r['year']: r for r in json.loads(HOST_PATH.read_text())['annual_rows']}
history = json.loads(HISTORY_PATH.read_text())


def residual_cpu_margin(revenue: float, profit: float, other: float, other_margin: float) -> float:
    return (profit - other * other_margin) / (revenue - other)


def blended_margin(cpu_margin: float, other_margin: float, other_share: float) -> float:
    return cpu_margin * (1 - other_share) + other_margin * other_share


anchors = {
    r['quarter']: (r['DCAI_revenue_B'], r['DCAI_operating_income_B'], r['Other_DCAI_revenue_B'])
    for r in history['quarterly_2026']
}
anchors['PooledQ2Q3_2026'] = (13.58, 5.513, 2.351)
anchors['YTD2026'] = (18.632, 7.055, 3.3)
anchor_rows = []
for name, (revenue, profit, other) in anchors.items():
    for other_margin in policy['stress_axes']['Other_operating_margin']:
        anchor_rows.append({
            'anchor': name,
            'DCAI_revenue_B': revenue,
            'DCAI_operating_profit_B': profit,
            'DCAI_margin': profit / revenue,
            'Other_DCAI_revenue_B': other,
            'Other_margin_assumption': other_margin,
            'CPU_margin_residual': residual_cpu_margin(revenue, profit, other, other_margin),
        })

cpu_margin = residual_cpu_margin(*anchors['YTD2026'], .2)
pooled_margin = residual_cpu_margin(*anchors['PooledQ2Q3_2026'], .2)
assert abs(cpu_margin - selected['mature_CPU_margin']) < 1e-12

near_term = []
other_revenue = selected['Other_DCAI_2026_revenue_B']
cpu_rows = {r['year']: r for r in quarter['annual_rows']}
client_rows = {r['year']: r for r in client['cases']['preferred']['annual_2027_2030']}
old_asp_index, new_asp_index = 1.0, 1.0
for year, growth in zip(range(2027, 2031), selected['Other_DCAI_growth_2027_2030']):
    other_revenue *= 1 + growth
    old = host[year]
    cpu_revenue = cpu_rows[year]['CPU_revenue_B']
    ccpg_revenue = client_rows[year]['CCPG_revenue_B']
    cpu_delta = cpu_revenue - old['server_CPU_revenue_proxy_B']
    other_delta = other_revenue - old['Other_DCAI_revenue_B']
    client_delta = ccpg_revenue - old['CCPG_revenue_B']
    dcai_profit = old['DCAI_operating_profit_B'] + .5 * cpu_delta + .2 * other_delta
    ccpg_profit = old['CCPG_operating_profit_B'] + .5 * client_delta
    products_revenue = cpu_revenue + other_revenue + ccpg_revenue
    foundry_profit = selected['Foundry_near_term_profit_B_2027_2030'][year - 2027]
    if year > 2027:
        old_asp_index *= 1 + old['server_ASP_growth']
        new_asp_index *= 1 + cpu_rows[year]['CPU_ASP_growth']
    counterfactual_cpu_sales_at_old_2028plus_ASP = cpu_revenue * old_asp_index / new_asp_index
    asp_gap = cpu_revenue - counterfactual_cpu_sales_at_old_2028plus_ASP
    near_term.append({
        'year': year,
        'CPU_revenue_B': cpu_revenue,
        'Other_DCAI_revenue_B': other_revenue,
        'Other_DCAI_growth': growth,
        'CCPG_revenue_B': ccpg_revenue,
        'Products_revenue_B': products_revenue,
        'CPU_revenue_delta_B': cpu_delta,
        'Other_DCAI_revenue_delta_B': other_delta,
        'client_revenue_delta_B': client_delta,
        'CPU_group_EBIT_delta_B': .5 * cpu_delta,
        'Other_DCAI_group_EBIT_delta_B': .2 * other_delta,
        'client_group_EBIT_delta_B': .5 * client_delta,
        'DCAI_allocated_operating_profit_B': dcai_profit,
        'CCPG_allocated_operating_profit_B': ccpg_profit,
        'Foundry_allocated_operating_profit_B': foundry_profit,
        'Products_plus_Foundry_profit_B': dcai_profit + ccpg_profit + foundry_profit,
        'DCAI_margin': dcai_profit / (cpu_revenue + other_revenue),
        'CPU_margin_implied_by_20pct_Other': (dcai_profit - .2 * other_revenue) / cpu_revenue,
        'CCPG_margin': ccpg_profit / ccpg_revenue,
        'Foundry_profit_per_Products_revenue': foundry_profit / products_revenue,
        'CPU_ASP_gap_2028plus_B': asp_gap,
        'extra_group_EBIT_loss_if_that_ASP_gap_is_pure_price_B': .5 * asp_gap,
        'cost_stress_group_EBIT_delta_vs_preferred_B': {
            str(c): (c - .5) * (cpu_delta + client_delta)
            for c in [.75, 1.0]
        },
    })

anchor2030 = near_term[-1]
future_rows = []
future_cpu = anchor2030['CPU_revenue_B']
future_other = anchor2030['Other_DCAI_revenue_B']
future_client = client_rows[2030]['client_revenue_B']
foundry_ratio = anchor2030['Foundry_profit_per_Products_revenue']
for i, year in enumerate(range(2031, 2041)):
    fraction = (year - 2030) / 10
    future_cpu *= (1 + selected['CPU_units_growth_2031_2040'][i]) * (1 + selected['CPU_ASP_growth_2031_2040'][i])
    future_other *= 1 + selected['Other_DCAI_growth_2031_2040'][i]
    future_client *= (1 + host[year]['client_unit_growth']) * (1 + host[year]['client_ASP_growth'])
    future_ccpg = future_client + host[year]['Other_CCPG_revenue_B']
    current_cpu_margin = anchor2030['CPU_margin_implied_by_20pct_Other'] * (1 - fraction) + cpu_margin * fraction
    current_ccpg_margin = anchor2030['CCPG_margin'] * (1 - fraction) + .28 * fraction
    future_dcai = future_cpu + future_other
    products = future_dcai + future_ccpg
    dcai_profit = current_cpu_margin * future_cpu + .2 * future_other
    ccpg_profit = current_ccpg_margin * future_ccpg
    foundry_profit = foundry_ratio * products
    future_rows.append({
        'year': year,
        'CPU_revenue_B': future_cpu,
        'Other_DCAI_revenue_B': future_other,
        'CCPG_revenue_B': future_ccpg,
        'Products_revenue_B': products,
        'Other_DCAI_share': future_other / future_dcai,
        'CPU_margin': current_cpu_margin,
        'DCAI_margin': dcai_profit / future_dcai,
        'CCPG_margin': current_ccpg_margin,
        'DCAI_operating_profit_B': dcai_profit,
        'CCPG_operating_profit_B': ccpg_profit,
        'Foundry_operating_profit_B': foundry_profit,
        'Foundry_profit_per_Products_revenue': foundry_ratio,
        'Products_plus_Foundry_profit_B': dcai_profit + ccpg_profit + foundry_profit,
    })

future_other_share = future_rows[-1]['Other_DCAI_share']
for row in anchor_rows:
    row['2040_blend_at_preferred_revenue_mix'] = blended_margin(row['CPU_margin_residual'], row['Other_margin_assumption'], future_other_share)

cost_growth_hurdles = []
future_unit_factor = prod(1 + x for x in selected['CPU_units_growth_2031_2040'])
future_asp_factor = prod(1 + x for x in selected['CPU_ASP_growth_2031_2040'])
future_revenue_factor = future_unit_factor * future_asp_factor
cpu40 = (.4 - .2 * future_other_share) / (1 - future_other_share)
for name, margin_target in [('selected_CPU_margin', cpu_margin), ('40pct_DCAI_hypothesis', cpu40)]:
    for fixed_share in [.1, .15, .2]:
        variable_share = 1 - anchor2030['CPU_margin_implied_by_20pct_Other'] - fixed_share
        for fixed_growth in [0, .02, .03]:
            cost_factor = ((1 - margin_target) * future_revenue_factor - fixed_share * (1 + fixed_growth) ** 10) / (variable_share * future_unit_factor)
            cost_growth_hurdles.append({
                'case': name,
                'CPU_margin2040': margin_target,
                '2030_fixed_operating_cost_fraction_of_CPU_revenue_assumption': fixed_share,
                '2030_variable_booked_product_cost_fraction_of_CPU_revenue_residual': variable_share,
                'fixed_operating_cost_annual_growth_assumption': fixed_growth,
                'required_variable_booked_product_cost_per_unit_CAGR': cost_factor ** .1 - 1,
                'unit_factor2030to2040': future_unit_factor,
                'ASP_factor2030to2040': future_asp_factor,
                'boundary': 'Algebraic cost requirement, not disclosed CPU cost structure. Booked product cost includes internal charges; only physical cost improvement retained across Products plus Foundry creates group value. No added valuation overlay.',
            })

price_cost_hurdles = []
for price_change in [0, -.05, -.1, -.15]:
    # Product all-in cost after internal transfer charges, not identified physical cost.
    cost_ratio_required = (1 - cpu_margin) * (1 + price_change) / (1 - pooled_margin)
    price_cost_hurdles.append({
        'realized_same_mix_price_change_vs_pooled_Q2Q3': price_change,
        'required_all_in_product_cost_per_unit_change_for_selected_CPU_margin': cost_ratio_required - 1,
        'CPU_margin_if_all_in_cost_unchanged': 1 - (1 - pooled_margin) / (1 + price_change),
        'boundary': 'Conditional same-unit product-profit hurdle, not an observed physical wafer-cost forecast. Transfer changes must be offset in Foundry.',
    })

mix_hurdles = []
preferred_other_factor = prod(1 + x for x in selected['Other_DCAI_growth_2027_2030'])
old_other_factor = prod(1 + x for x in policy['favorable']['Other_DCAI_growth_2027_2030'])
legacy_factor = 1.03 ** 4
for custom_share in [.4, .5, .6, .7, .8, 1.0]:
    for name, overall_factor in [('preferred', preferred_other_factor), ('old', old_other_factor)]:
        custom_factor = (overall_factor - (1 - custom_share) * legacy_factor) / custom_share
        mix_hurdles.append({
            'case': name,
            '2026_custom_share_of_Other_assumption': custom_share,
            'legacy_growth_assumption': .03,
            'required_custom_2030_over_2026': custom_factor,
            'required_custom_CAGR': custom_factor ** .25 - 1,
            'scope': 'Conditional hurdle, not custom share estimation. Actual share and timing undisclosed.',
        })

transfer_checks = []
for transfer_change in [-2.0, -1.0, .5, 1.0, 2.0]:
    product_profit = anchor2030['DCAI_allocated_operating_profit_B'] + anchor2030['CCPG_allocated_operating_profit_B']
    foundry_profit = anchor2030['Foundry_allocated_operating_profit_B']
    changed = (product_profit - transfer_change) + (foundry_profit + transfer_change)
    transfer_checks.append({'internal_charge_change_B': transfer_change, 'group_profit_change_B': changed - product_profit - foundry_profit})
assert max(abs(r['group_profit_change_B']) for r in transfer_checks) < 1e-12
assert all(abs(r['DCAI_margin'] - blended_margin(r['CPU_margin'], .2, r['Other_DCAI_share'])) < 1e-12 for r in future_rows)
assert abs(future_rows[-1]['CPU_margin'] - cpu_margin) < 1e-12
assert abs(future_rows[-1]['CCPG_margin'] - .28) < 1e-12

out = {
    'computed_utc': datetime.now(timezone.utc).isoformat(),
    'input_sha256': {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in [POLICY_PATH, QUARTER_PATH, CLIENT_PATH, HOST_PATH, HISTORY_PATH]},
    'scope': 'Operating bridge only. No equity valuation or target calculation. Near-term Products/Foundry allocations are not disclosed forecasts.',
    'selected_CPU_margin': cpu_margin,
    'pooled_recent_CPU_margin': pooled_margin,
    'selected_erosion_from_pooled_percentage_points': (pooled_margin - cpu_margin) * 100,
    'historical_anchor_sensitivities': anchor_rows,
    'rounding_sensitivity_YTD_Other3_3_plus_minus_0_05B': [
        {'Other_B': other, 'CPU_margin': residual_cpu_margin(18.632, 7.055, other, .2)}
        for other in [3.25, 3.3, 3.35]
    ],
    'near_term_2027_2030': near_term,
    'illustrative_post2030_component_transition': future_rows,
    'post_LTA_product_price_cost_hurdles': price_cost_hurdles,
    'post2030_margin_implied_cost_growth_hurdles': cost_growth_hurdles,
    'custom_growth_scope_hurdles': mix_hurdles,
    'Other_revenue_runrate': {
        'Q4_2026_assumed_Other_B': 1.89,
        '2027_Other_B': near_term[0]['Other_DCAI_revenue_B'],
        '2027_growth_over_four_times_Q4_exit': near_term[0]['Other_DCAI_revenue_B'] / (4 * 1.89) - 1,
        'preferred_2030_over_2026': preferred_other_factor,
        'old_2030_over_2026': old_other_factor,
        'literal_custom3x_plus_legacy3pct_maximum_aggregate': 3.0,
        'required_custom_share_for_preferred_if_custom_exactly3x_by2030': (preferred_other_factor - legacy_factor) / (3 - legacy_factor),
        'required_custom_share_for_old_if_custom3x_in3years_and_sameCAGR_in_year4': (old_other_factor - legacy_factor) / (3 ** (4 / 3) - legacy_factor),
    },
    'historical_cost_response_context': {
        'Q3_group_product_profit_change_over_revenue_change_approx': 1.6 / (16.513 - 13.653),
        'YTD_group_product_profit_change_over_revenue_change_approx': 2.9 / (46.218 - 39.179),
        'CFO_incremental_gross_profit_rule_of_thumb': [.4, .6],
        'rule_locator': 'Q3 earnings Q&A47:19, original webcast linked on Intel IR event page; transcript reproduction cross-check.',
        'limits': 'Not a regression or same-mix CPU unit response. Product-profit attribution and revenue include different businesses and rounded management components. EBIT follows GP only with opex fixed.',
    },
    'transfer_price_checks': transfer_checks,
    'checks': {
        'no_equity_value_computed': True,
        'transfer_cancellation_error_max_B': max(abs(r['group_profit_change_B']) for r in transfer_checks),
        'mature_component_weighting_identity_passed': True,
        'no_fixed40pct_DCAI_overlay': True,
        'no_additional_Foundry_absorption_overlay': True,
        'no_capex_DA_taxcredit_changes': True,
        'only_owned_output_written': True,
    },
}
(OUT / 'margin_bridge_results.json').write_text(json.dumps(out, indent=2) + '\n')
print(json.dumps({
    'CPU_margin': cpu_margin,
    'mature_blend': future_rows[-1]['DCAI_margin'],
    'mature_Other_share': future_other_share,
    'Other_runrate': out['Other_revenue_runrate'],
    '2030': near_term[-1],
    'price_cost_hurdles': price_cost_hurdles,
    'checks': out['checks'],
}, indent=2))

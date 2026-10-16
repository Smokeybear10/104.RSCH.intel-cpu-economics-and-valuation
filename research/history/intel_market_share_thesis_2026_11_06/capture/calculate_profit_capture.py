import copy
import hashlib
import importlib.util
import itertools
import json
import math
from datetime import datetime, timezone
from pathlib import Path


OUT = Path(__file__).resolve().parent
OLD = OUT.parents[1] / 'intel_two_hour_completion_2026_11_06'
SOURCES = {
    'policy': OUT / 'capture_policy_before_calculation.json',
    'engine': OLD / 'root/integrated_model.py',
    'selected': OLD / 'root/integrated_results.json',
    'favorable': OLD / 'quarterly/anchor_valuation_overlay_results.json',
    'anchors': OLD / 'quarterly/favorable_anchor_case_results.json',
    'cross_stresses': OLD / 'margin/favorable_cross_stress_results.json',
    'margin': OLD / 'margin/selected_margin_policy.json',
}
spec = importlib.util.spec_from_file_location('capture_root_engine', SOURCES['engine'])
engine = importlib.util.module_from_spec(spec)
spec.loader.exec_module(engine)
selected = json.loads(SOURCES['selected'].read_text())['cases']['preferred']
favorable = json.loads(SOURCES['favorable'].read_text())['cases']['joint_anchor_old_CPU2028plus_growth_pooled_old_growth']
anchor = json.loads(SOURCES['anchors'].read_text())['cases']['joint_favorable']
FACTOR_NAMES = ['Q4_anchor', 'CPU_delivery_2028_2030', 'mature_CPU_margin', 'CPU_growth_2031_2040', 'discount_rate']
MARGINS = [.4171014870858335, .4490871849674949]
RATES = [.11555, .10625]


def independent_value(case: dict, rate: float) -> dict:
    rows = {int(y): r for y, r in case['annual_rows'].items()}
    values = {}
    for year in (2026, 2030):
        explicit = sum(rows[y]['parent_unlevered_cash_B'] / (1 + rate) ** (y - year) for y in range(year + 1, 2041))
        terminal = rows[2041]['parent_unlevered_cash_B'] / (rate - .03) / (1 + rate) ** (2040 - year)
        shield = sum(rows[y]['financing_shield_B'] / (1 + rate) ** (y - year) for y in range(year + 1, 2041))
        shield += rows[2041]['financing_shield_B'] / rate / (1 + rate) ** (2040 - year)
        cash = case['treasury'][2027]['opening_cash_B'] if year == 2026 else case['treasury'][2030]['ending_cash_B']
        debt = case['treasury'][2027]['opening_debt_B'] if year == 2026 else case['treasury'][2030]['ending_debt_B']
        escrow = sum(engine.FUND[y]['escrow_cash_B'] / (1 + rate) ** (y - year) for y in range(year + 1, 2031))
        acquisitions = sum(engine.FUND[y]['Classiq_cash_B'] / (1 + rate) ** (y - year) for y in range(year + 1, 2031))
        equity = explicit + terminal + shield + cash - debt + 4.502 + escrow - acquisitions
        values[year] = {'price_USD': equity / 5.51, 'explicit_operating_PV_B': explicit,
                        'terminal_operating_PV_B': terminal, 'terminal_share': terminal / (explicit + terminal)}
    return values


def build_combination(bits: tuple) -> dict:
    a, delivery, margin, growth, rate = bits
    if a:
        override = copy.deepcopy(anchor)
    else:
        override = {'annual_rows': [dict(selected['annual_rows'][str(y)]) for y in range(2027, 2031)],
                    'Q4_2026': {'net_consolidated_revenue_delta_B': 0., 'opening2027_economic_cash_delta_B': 0.}}
    if delivery:
        cpu = override['annual_rows'][0]['CPU_revenue_B']
        for row, units, asp in zip(override['annual_rows'][1:], [.25, .18, .12], [.08, .04, .02]):
            cpu *= (1 + units) * (1 + asp)
            row['CPU_revenue_B'] = cpu
    case = engine.build_case(delivery='preferred', revised_other=True, component_margin=True,
                             normalized_growth=not growth, cpu_margin=MARGINS[margin], anchor_case=override)
    values = independent_value(case, RATES[rate])
    rows = case['annual_rows']
    return {'factor_bits': bits, 'values': values, 'CPU2030_B': rows[2030]['CPU_revenue_B'],
            'CPU2040_B': rows[2040]['CPU_revenue_B'], 'EBIT2030_B': rows[2030]['EBIT_B'],
            'owner_cash_2027_2030_B': sum(t['owner_cash_B'] for t in case['treasury'].values()),
            'parent_cash2041_B': rows[2041]['parent_unlevered_cash_B'], 'case': case}


def profit_cash_rows(case: dict) -> list:
    result = []
    for year, raw in case['annual_rows'].items():
        r = copy.deepcopy(raw)
        y = int(year)
        r['CPU_allocated_product_profit_B'] = r['DCAI_profit_B'] - r['Other_DCAI_B'] * r['Other_DCAI_margin']
        r['Other_DCAI_allocated_profit_B'] = r['Other_DCAI_B'] * r['Other_DCAI_margin']
        r['net_credits_B'] = r['old_credit_collection_B'] + r['new_credit_collection_B'] - r['credit_basis_loss_tax_B']
        r['cash_without_net_credits_B'] = r['parent_unlevered_cash_B'] - r['net_credits_B']
        r['owner_cash_after_financing_B'] = case['treasury'][str(y)]['owner_cash_B'] if y <= 2030 else None
        r['group_EBIT_margin'] = r['EBIT_B'] / r['consolidated_revenue_B']
        r['external_revenue_less_EBIT_less_DA_proxy_B'] = r['consolidated_revenue_B'] - r['EBIT_B'] - r['DA_B']
        r['profit_identity_error_B'] = (r['CPU_allocated_product_profit_B'] + r['Other_DCAI_allocated_profit_B']
                                        + r['CCPG_profit_B'] + r['Foundry_profit_B'] + r['net_packaging_profit_B']
                                        + r['Other_profit_less_corporate_B'] - r['EBIT_B'])
        r['cash_identity_error_B'] = (r['EBIT_B'] - r['ordinary_operating_tax_B'] - r['physical_capex_B']
                                      + r['DA_B'] - r['WC_cash_use_B'] - r['lease_cash_B']
                                      - r['minority_cash_B'] + r['net_credits_B'] - r['parent_unlevered_cash_B'])
        result.append(r)
    return result


def period_bridge(rows: list) -> dict:
    by_year = {r['year']: r for r in rows}
    start, end = by_year[2027], by_year[2030]
    fields = ['CPU_allocated_product_profit_B', 'Other_DCAI_allocated_profit_B', 'CCPG_profit_B',
              'Foundry_profit_B', 'net_packaging_profit_B', 'Other_profit_less_corporate_B']
    delta = {field: end[field] - start[field] for field in fields}
    delta['total_group_EBIT_change_B'] = end['EBIT_B'] - start['EBIT_B']
    delta['factory_and_packaging_share_of_EBIT_increase'] = (delta['Foundry_profit_B'] + delta['net_packaging_profit_B']) / delta['total_group_EBIT_change_B']
    assert abs(sum(delta[f] for f in fields) - delta['total_group_EBIT_change_B']) < 1e-10
    totals = {f: sum(by_year[y][f] for y in range(2027, 2031)) for f in ['NOPAT_B', 'physical_capex_B', 'DA_B', 'WC_cash_use_B', 'net_operating_investment_B', 'net_credits_B', 'lease_cash_B', 'minority_cash_B', 'parent_unlevered_cash_B', 'owner_cash_after_financing_B']}
    return {'EBIT_change2027_2030': delta, 'cumulative2027_2030': totals,
            'CPU_revenue_CAGR2027_2030': (end['CPU_revenue_B'] / start['CPU_revenue_B']) ** (1 / 3) - 1,
            'CPU_revenue_CAGR2030_2040': (by_year[2040]['CPU_revenue_B'] / end['CPU_revenue_B']) ** .1 - 1}


def main() -> None:
    grid = {bits: build_combination(bits) for bits in itertools.product((0, 1), repeat=5)}
    errors = []
    for bits, reference in [((0, 0, 0, 0, 0), selected), ((1, 1, 1, 1, 0), favorable)]:
        for y, row in reference['annual_rows'].items():
            for field, value in row.items():
                if isinstance(value, (int, float)):
                    errors.append(abs(value - grid[bits]['case']['annual_rows'][int(y)][field]))
        for year in (2026, 2030):
            errors.append(abs(grid[bits]['values'][year]['price_USD'] - reference['values'][str(year)]['price_USD']))
    assert max(errors) < 1e-9
    assert abs(grid[(1, 1, 1, 1, 1)]['values'][2030]['price_USD'] - 82.47015162680005) < 1e-9
    shapley = {}
    for endpoint in (2026, 2030):
        contributions = [0.] * 5
        for order in itertools.permutations(range(5)):
            bits = [0] * 5
            for index in order:
                before = grid[tuple(bits)]['values'][endpoint]['price_USD']
                bits[index] = 1
                after = grid[tuple(bits)]['values'][endpoint]['price_USD']
                contributions[index] += (after - before) / math.factorial(5)
        shapley[endpoint] = dict(zip(FACTOR_NAMES, contributions))
        difference = grid[(1,) * 5]['values'][endpoint]['price_USD'] - grid[(0,) * 5]['values'][endpoint]['price_USD']
        assert abs(sum(contributions) - difference) < 1e-9
    bridges = {name: profit_cash_rows(case) for name, case in [('selected', selected), ('favorable', favorable)]}
    for rows in bridges.values():
        assert max(abs(r['profit_identity_error_B']) for r in rows) < 1e-10
        assert max(abs(r['cash_identity_error_B']) for r in rows) < 1e-10
    comparison = {}
    for year in range(2027, 2031):
        s, f = selected['annual_rows'][str(year)], favorable['annual_rows'][str(year)]
        cpu = .5 * (f['CPU_revenue_B'] - s['CPU_revenue_B'])
        client = .5 * (f['client_revenue_B'] - s['client_revenue_B'])
        other = .2 * (f['Other_DCAI_B'] - s['Other_DCAI_B'])
        assert abs(cpu + client + other - (f['EBIT_B'] - s['EBIT_B'])) < 1e-10
        comparison[year] = {'CPU_EBIT_delta_B': cpu, 'client_EBIT_delta_B': client, 'Other_DCAI_EBIT_delta_B': other,
                            'group_EBIT_delta_B': f['EBIT_B'] - s['EBIT_B'],
                            'parent_cash_delta_B': f['parent_unlevered_cash_B'] - s['parent_unlevered_cash_B']}
    unit_factor = 1.4 * .42 / .50
    market = {'industry_unit_growth_assumed': .4, 'Intel_share_2026': .5, 'Intel_share2027': .42,
              'implied_Intel_units_growth': unit_factor - 1,
              'selected_required_ASP_growth': selected['annual_rows']['2027']['CPU_revenue_B'] / (15.332 + 6.5257) / unit_factor - 1,
              'favorable_required_ASP_growth': favorable['annual_rows']['2027']['CPU_revenue_B'] / (15.332 + 6.81206) / unit_factor - 1,
              'scope': 'Conditional decomposition of forecast market estimates and analyst revenue. Industry source says more than40%;40% is a lower growth anchor, not an exact reported value. Each forecast uses its own matched2026CPUrevenue base.'}
    result = {'computed_utc': datetime.now(timezone.utc).isoformat(),
              'source_hashes': {k: {'path': str(p), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for k, p in SOURCES.items()},
              'reconciliation': {'comparisons': len(errors), 'maximum_error': max(errors)},
              'market_to_revenue': market, 'annual_profit_cash_bridges': bridges,
              'period_bridges': {name: period_bridge(rows) for name, rows in bridges.items()},
              'favorable_minus_selected_group_capture': comparison,
              'factorial_cases': {''.join(map(str, bits)): {k: v for k, v in case.items() if k != 'case'} for bits, case in grid.items()},
              'Shapley_value_attribution_USD': shapley,
              'attribution_limit': 'Permutation-averaged model attribution, not independent causal evidence or probabilities.'}
    (OUT / 'profit_capture_results.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'reconciliation': result['reconciliation'], 'market': market, 'period_bridges': result['period_bridges'], 'Shapley': shapley,
                      'one_change_from_favorable': {FACTOR_NAMES[i]: grid[tuple(0 if j == i else 1 for j in range(5))]['values'] for i in range(5)}}, indent=2))


if __name__ == '__main__':
    main()

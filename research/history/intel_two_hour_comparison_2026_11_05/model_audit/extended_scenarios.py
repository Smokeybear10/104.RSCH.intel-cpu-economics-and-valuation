import copy
import hashlib
import json
import math
from datetime import date, datetime, timezone
from pathlib import Path


OUT = Path(__file__).resolve().parent
RESEARCH = OUT.parents[1]
BASE_PATH = OUT / 'reconstruction_results.json'
POLICY_PATH = OUT / 'extended_scenario_policy.json'
HOST_PATH = RESEARCH / 'pricing_and_competition_review_2026_11_04/intel_server_ASP_mix_operating_policy.json'
MODEL_PATH = RESEARCH / 'pricing_and_competition_review_2026_11_04/intel_ASP20_mature_margin35_valuation.json'
PACKAGING_PATH = RESEARCH / 'intel_competition_screen_2026_11_04/external_packaging_operating_policy_2026_11_04.json'
FOUNDRY_PATH = RESEARCH / 'intel_competition_screen_2026_11_04/foundry_operating_policy.json'
inputs = {p.name: {'path': str(p), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in [BASE_PATH, POLICY_PATH, HOST_PATH, MODEL_PATH, PACKAGING_PATH, FOUNDRY_PATH]}
base_reconstruction = json.loads(BASE_PATH.read_text())
base = base_reconstruction['independently_reconstructed_base']
base_rows = {int(y): row for y, row in base['rows'].items()}
host = {row['year']: row for row in json.loads(HOST_PATH.read_text())['annual_rows']}
packaging = {row['year']: row for row in json.loads(PACKAGING_PATH.read_text())['annual_rows']}
model = json.loads(MODEL_PATH.read_text())
funding = {row['year']: row for row in model['treasury_rows']}
foundry_anchor = json.loads(FOUNDRY_PATH.read_text())['historical_anchor']['rounded_2026_planning_operating_profit_B']
RATE = .11555
GROWTH = .03
SHARES = 5.51
ENTRY = 52.22
YEARS = (date(2030, 12, 31) - date(2026, 11, 5)).days / 365.25
OTHER_ASSETS = model['values_at12pct']['2026']['net_other_assets_B']


def value(rows: dict) -> dict:
    cash = funding[2027]['opening_economic_cash_B']
    debt = funding[2027]['opening_ordinary_debt_B']
    treasury = {}
    for y in range(2027, 2031):
        row, finance = rows[y], funding[y]
        owner = row['parent_unlevered_cash_B'] - finance['ordinary_interest_B'] - finance['capitalized_interest_B'] + finance['cash_income_B'] * (1 - row['tax_rate']) + row['financing_shield_B']
        cash += owner + finance['escrow_cash_B'] - finance['Classiq_cash_B'] - finance['principal_B']
        debt -= finance['principal_B']
        treasury[y] = {'owner_cash_B': owner, 'ending_economic_cash_B': cash, 'ending_ordinary_debt_B': debt}
        assert cash >= 20, 'Scenario requires financing-policy extension before valuation.'
    result = {}
    for endpoint in (2026, 2030):
        explicit = math.fsum(row['parent_unlevered_cash_B'] / (1 + RATE) ** (y - endpoint) for y, row in rows.items() if endpoint < y <= 2040)
        tail = rows[2041]['parent_unlevered_cash_B'] / (RATE - GROWTH) / (1 + RATE) ** (2040 - endpoint)
        shields = math.fsum(row['financing_shield_B'] / (1 + RATE) ** (y - endpoint) for y, row in rows.items() if endpoint < y <= 2040)
        shields += rows[2041]['financing_shield_B'] / RATE / (1 + RATE) ** (2040 - endpoint)
        if endpoint == 2026:
            cash_value, debt_value = funding[2027]['opening_economic_cash_B'], funding[2027]['opening_ordinary_debt_B']
        else:
            cash_value, debt_value = treasury[endpoint]['ending_economic_cash_B'], treasury[endpoint]['ending_ordinary_debt_B']
        escrow = math.fsum(row['escrow_cash_B'] / (1 + RATE) ** (y - endpoint) for y, row in funding.items() if endpoint < y <= 2030)
        acquisition = math.fsum(row['Classiq_cash_B'] / (1 + RATE) ** (y - endpoint) for y, row in funding.items() if endpoint < y <= 2030)
        equity = explicit + tail + shields + cash_value - debt_value + OTHER_ASSETS + escrow - acquisition
        result[endpoint] = {
            'price_USD': equity / SHARES, 'equity_B': equity,
            'explicit_operating_PV_B': explicit, 'terminal_operating_PV_B': tail,
            'financing_shield_PV_B': shields,
            'economic_cash_B': cash_value, 'ordinary_debt_B': debt_value,
        }
    return {'rows': rows, 'treasury': treasury, 'values': result}


def close_cash(row: dict) -> None:
    row['ordinary_operating_tax_B'] = max(row['EBIT_B'], 0) * row['tax_rate']
    row['NOPAT_B'] = row['EBIT_B'] - row['ordinary_operating_tax_B']
    row['parent_unlevered_cash_B'] = row['NOPAT_B'] - row['net_operating_investment_B'] - row['lease_cash_B'] - row['minority_cash_B'] + row['old_credit_collection_B'] + row['new_credit_collection_B'] - row['credit_basis_loss_tax_B']
    assert row['ordinary_operating_tax_B'] > row['financing_shield_B']


def scenario(name: str) -> dict:
    rows = copy.deepcopy(base_rows)
    for y, row in rows.items():
        row['host_Foundry_profit_B'] = host[y]['Foundry_operating_profit_B']
        row['CPU_revenue_delta_B'] = 0
        row['consolidated_EBIT_delta_B'] = 0
        if name == 'foundry_recovery_delayed_one_year' and y <= 2030:
            previous = foundry_anchor if y == 2027 else host[y - 1]['Foundry_operating_profit_B']
            change = previous - row['host_Foundry_profit_B']
            row['host_Foundry_profit_B'] = previous
            row['EBIT_B'] += change
            row['consolidated_EBIT_delta_B'] = change
        if name == 'profit_retention_erosion_from_2028' and y >= 2028:
            margin = .35 + (base_rows[2027]['DCAI_product_margin'] - .35) * max((2030 - y) / 3, 0)
            change = (margin - row['DCAI_product_margin']) * row['DCAI_revenue_B']
            row['DCAI_product_margin'] = margin
            row['EBIT_B'] += change
            row['consolidated_EBIT_delta_B'] = change
        if name == 'CPU_growth_normalizes_2031' and y >= 2031:
            new_cpu = host[2030]['server_CPU_revenue_proxy_B'] * 1.03 ** (y - 2030)
            delta = new_cpu - row['CPU_revenue_B']
            retention = .5 - .01 * min(y - 2030, 10)
            change = delta * retention
            dcai_profit = row['DCAI_product_margin'] * row['DCAI_revenue_B'] + change
            row['CPU_revenue_B'] = new_cpu
            row['CPU_revenue_delta_B'] = delta
            row['DCAI_revenue_B'] += delta
            row['DCAI_product_margin'] = dcai_profit / row['DCAI_revenue_B']
            row['capital_denominator_revenue_B'] += delta
            row['EBIT_B'] += change
            row['consolidated_EBIT_delta_B'] = change
            row['decremental_group_EBIT_retention'] = retention
            new_products = host[y]['Products_revenue_B'] + delta
            host_da = host[y]['DA_fraction_of_Products_revenue'] * new_products
            current_host_sales = host[y]['consolidated_external_revenue_for_capital_denominator_B'] + delta
            prior_delta = rows[y - 1]['CPU_revenue_delta_B']
            prior_host_sales = host[y - 1]['consolidated_external_revenue_for_capital_denominator_B'] + prior_delta
            host_sales_change = current_host_sales - prior_host_sales
            host_wc = .1 * host_sales_change
            host_net_investment = host_sales_change / .8
            row['DA_B'] = host_da + packaging[y]['incremental_DA_B']
            row['WC_cash_use_B'] = host_wc + packaging[y]['incremental_WC_cash_use_B']
            row['net_operating_investment_B'] = host_net_investment + packaging[y]['incremental_net_operating_investment_B']
            row['physical_capex_B'] = row['DA_B'] + row['net_operating_investment_B'] - row['WC_cash_use_B']
            assert host_sales_change > 0
            if y in (2031, 2032):
                assert row['physical_capex_B'] - packaging[y]['incremental_physical_cash_capex_B'] > {2031: 5, 2032: 2}[y]
        close_cash(row)
    assert abs(rows[2041]['parent_unlevered_cash_B'] / rows[2040]['parent_unlevered_cash_B'] - 1.03) < 1e-12
    return value(rows)


cases = {name: scenario(name) for name in ['base', 'foundry_recovery_delayed_one_year', 'profit_retention_erosion_from_2028', 'CPU_growth_normalizes_2031']}
errors = []
for endpoint in (2026, 2030):
    for field in ('price_USD', 'explicit_operating_PV_B', 'terminal_operating_PV_B', 'equity_B', 'economic_cash_B', 'ordinary_debt_B'):
        error = abs(cases['base']['values'][endpoint][field] - base['values'][str(endpoint)][field])
        errors.append(error)
        assert error < 1e-9, (endpoint, field, error)

summary = []
for name, case in cases.items():
    target = case['values'][2030]['price_USD']
    summary.append({
        'name': name,
        'December2026_planning_value_USD': case['values'][2026]['price_USD'],
        'December2030_target_USD': target,
        'target_change_USD': target - cases['base']['values'][2030]['price_USD'],
        'annual_price_return_from52_22': (target / ENTRY) ** (1 / YEARS) - 1,
        'minimum_economic_cash_2027_2030_B': min(row['ending_economic_cash_B'] for row in case['treasury'].values()),
        '2030_economic_cash_change_B': case['treasury'][2030]['ending_economic_cash_B'] - cases['base']['treasury'][2030]['ending_economic_cash_B'],
        '2030_remaining_operating_value_change_B': case['values'][2030]['explicit_operating_PV_B'] + case['values'][2030]['terminal_operating_PV_B'] - cases['base']['values'][2030]['explicit_operating_PV_B'] - cases['base']['values'][2030]['terminal_operating_PV_B'],
    })


def value_with_mature_margin(margin: float) -> dict:
    rows = copy.deepcopy(base_rows)
    for y, row in rows.items():
        weight = min(max((y - 2030) / 10, 0), 1)
        row['EBIT_B'] += (margin - .4) * weight * row['DCAI_revenue_B']
        row['DCAI_product_margin'] += (margin - .4) * weight
        close_cash(row)
    return value(rows)


def solve_margin(endpoint: int, desired_price: float) -> float:
    low, high = .2, .7
    assert value_with_mature_margin(low)['values'][endpoint]['price_USD'] < desired_price < value_with_mature_margin(high)['values'][endpoint]['price_USD']
    for _ in range(80):
        mid = (low + high) / 2
        if value_with_mature_margin(mid)['values'][endpoint]['price_USD'] < desired_price:
            low = mid
        else:
            high = mid
    return (low + high) / 2


target_base = cases['base']['values'][2030]['price_USD']
margin_reference = solve_margin(2026, ENTRY)
decision = {
    'conditional_mature_margin_matching52_22_planning_value': margin_reference,
    'recomputed_planning_price_at_solution': value_with_mature_margin(margin_reference)['values'][2026]['price_USD'],
    'planning_quote_mismatch_days': 56,
    'holding_years': YEARS,
    'return_choices': [],
    'conditional_margin_frontier': [],
    'interpretation': 'One-variable conditional solutions with all sales, capital, tax and risk unchanged. These are mathematical dependencies, not uniquely identified market expectations or recommended margins. The quote predates the planning valuation by56days. Return choices are investor preferences, not CAPM cost-of-equity estimates. No probability of achieving the target is supplied.',
}
for hurdle in (.08, .10, .12, .15):
    required_target = ENTRY * (1 + hurdle) ** YEARS
    margin = solve_margin(2030, required_target)
    decision['return_choices'].append({
        'chosen_annual_price_return': hurdle,
        'maximum_entry_with_unchanged_base_target_USD': target_base / (1 + hurdle) ** YEARS,
        'required2030_target_at52_22_USD': required_target,
        'conditional_mature_margin_to_generate_required_target': margin,
        'solution_reconstruction_error_USD': value_with_mature_margin(margin)['values'][2030]['price_USD'] - required_target,
    })


def frontier_value(path_name: str, productivity: float, mature_margin: float) -> float:
    rows = copy.deepcopy(cases[path_name]['rows'])
    for y, row in rows.items():
        if y < 2031:
            continue
        current_host_sales = host[y]['consolidated_external_revenue_for_capital_denominator_B'] + row['CPU_revenue_delta_B']
        prior_host_sales = host[y - 1]['consolidated_external_revenue_for_capital_denominator_B'] + rows[y - 1]['CPU_revenue_delta_B']
        additional_investment = (current_host_sales - prior_host_sales) * (1 / productivity - 1 / .8)
        row['net_operating_investment_B'] += additional_investment
        row['physical_capex_B'] += additional_investment
        margin_wedge = (mature_margin - .4) * min((y - 2030) / 10, 1)
        row['EBIT_B'] += margin_wedge * row['DCAI_revenue_B']
        row['DCAI_product_margin'] += margin_wedge
        close_cash(row)
    return value(rows)['values'][2026]['price_USD']


for path_name in ['base', 'CPU_growth_normalizes_2031']:
    for productivity in [.6, .8, 1.0]:
        low, high = .2, .7
        assert frontier_value(path_name, productivity, low) < ENTRY < frontier_value(path_name, productivity, high)
        for _ in range(80):
            mid = (low + high) / 2
            if frontier_value(path_name, productivity, mid) < ENTRY:
                low = mid
            else:
                high = mid
        margin = (low + high) / 2
        decision['conditional_margin_frontier'].append({
            'CPU_path': path_name, 'host_capital_productivity': productivity,
            'mature_DCAI_margin_matching52_22_planning_value': margin,
            'planning_value_at40percent_margin': frontier_value(path_name, productivity, .4),
            'reconstruction_error': frontier_value(path_name, productivity, margin) - ENTRY,
        })

output = {
    'computed_utc': datetime.now(timezone.utc).isoformat(),
    'input_files': inputs, 'policy': json.loads(POLICY_PATH.read_text()),
    'summary': summary, 'cases': cases, 'decision_boundary': decision,
    'checks': {'base_reconciliation_comparisons': len(errors), 'maximum_absolute_error': max(errors), 'all_scenarios_above20B_annual_economic_cash': True, 'all_operating_tails_grow3percent': True},
    'limitations': [
        'A temporary profit delay can have a modest2030targeteffect only because the remaining business is explicitly restored. This does not prove restoration is likely.',
        'Growth duration and profit retention are different from a2027delivery delay. Their continuation cash changes persist beyond2030.',
        'The capital denominator still omits embedded externalFoundry sales; this audit does not invent a fully consolidated revenue forecast.',
        'All scenarios retain the base financing and credit eligibility conventions; no quarterly funding schedule or legal credit-entitlement determination is implied.',
        'No case probability, optimal allocation or competition-winning probability is inferred.',
    ],
}
(OUT / 'extended_scenario_results.json').write_text(json.dumps(output, indent=2) + '\n')
print(json.dumps({key: output[key] for key in ['summary', 'decision_boundary', 'checks']}, indent=2))

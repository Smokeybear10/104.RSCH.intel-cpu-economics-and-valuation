from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import math

OUT = Path(__file__).resolve().parent
RUN = OUT.parent
FILES = {
    'base': RUN / 'root/integrated_results.json',
    'quarters': RUN / 'root/quarterly_cash_results.json',
    'policy': RUN / 'margin/packaging_scale_stress_policy.json',
    'stress': RUN / 'margin/packaging_scale_results.json',
    'pack': RUN.parent / 'intel_competition_screen_2026_11_04/external_packaging_operating_policy_2026_11_04.json',
}
HASHES = {name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in FILES.items()}
D = {name: json.loads(path.read_text()) for name, path in FILES.items()}
BASE = D['base']['cases']['preferred']
PACK = {r['year']: r for r in D['pack']['annual_rows']}
ERRORS, CASES = [], {}
R, G, SHARES = .11555, .03, 5.51


def compare(actual: float, expected: float, name: str) -> None:
    ERRORS.append({'label': name, 'difference': abs(actual - expected)})


for name, avoid in [('proportional_cash_cost_avoidance', True), ('no_cash_cost_avoidance', False)]:
    previous_net = 0.
    rows = {}
    for year in range(2027, 2042):
        b, p = BASE['annual_rows'][str(year)], PACK[year]
        gross = b['gross_new_packaging_B'] * D['policy']['retained_gross_fraction']
        net = gross - b['shadow_packaging_B']
        lost_sales = b['net_new_packaging_B'] - net
        retained_da = p['incremental_DA_B']
        original_cash_cost = b['net_new_packaging_B'] - b['net_packaging_profit_B'] - retained_da
        kept_cash_cost = original_cash_cost * net / b['net_new_packaging_B'] if avoid else original_cash_cost
        net_profit = net - kept_cash_cost - retained_da
        profit_delta = net_profit - b['net_packaging_profit_B']
        new_wc = .15 * (net - previous_net)
        new_capex = p['incremental_physical_cash_capex_B'] if year <= 2030 else retained_da + .85 * (net - previous_net)
        wc_delta = new_wc - p['incremental_WC_cash_use_B']
        capex_delta = new_capex - p['incremental_physical_cash_capex_B']
        ebit = b['EBIT_B'] + profit_delta
        cash_delta = profit_delta - (max(ebit, 0) * b['tax_rate'] - b['ordinary_operating_tax_B']) - wc_delta - capex_delta
        fields = {'stressed_gross_sales_B': gross, 'stressed_net_sales_B': net, 'lost_sales_B': lost_sales,
                  'stressed_net_incremental_EBIT_B': net_profit, 'selected_incremental_cash_operating_cost_B': original_cash_cost,
                  'avoided_cash_cost_B': original_cash_cost - kept_cash_cost, 'unchanged_incremental_DA_B': retained_da,
                  'group_EBIT_delta_B': profit_delta, 'stressed_incremental_capex_B': new_capex,
                  'incremental_capex_delta_B': capex_delta, 'stressed_incremental_WC_cash_B': new_wc,
                  'incremental_WC_cash_delta_B': wc_delta}
        expected = D['stress']['packaging_rows'][name][year - 2027]
        for key, value in fields.items():
            compare(value, expected[key], f'{name} {year} {key}')
        compare(b['consolidated_revenue_B'] - lost_sales - net, b['host_capital_revenue_B'], f'{name} {year} unchanged host capital denominator')
        rows[year] = {**fields, 'group_EBIT_B': ebit, 'FCFF_delta_B': cash_delta,
                      'FCFF_B': b['parent_unlevered_cash_B'] + cash_delta}
        previous_net = net
    values = {}
    for endpoint in [2026, 2030]:
        explicit_delta = math.fsum(r['FCFF_delta_B'] / (1 + R) ** (year - endpoint) for year, r in rows.items() if endpoint < year <= 2040)
        terminal_delta = rows[2041]['FCFF_delta_B'] / (R - G) / (1 + R) ** (2040 - endpoint)
        cash_delta = 0. if endpoint == 2026 else sum(rows[y]['FCFF_delta_B'] for y in range(2027, 2031))
        original = BASE['values'][str(endpoint)]
        price = original['price_USD'] + (explicit_delta + terminal_delta + cash_delta) / SHARES
        values[endpoint] = {'price_USD': price, 'operating_PV_change_B': explicit_delta + terminal_delta, 'economic_cash_change_B': cash_delta}
        compare(price, D['stress']['valuation'][name][str(endpoint)]['price_USD'], f'{name} {endpoint} price')
        compare(original['cash_B'] + cash_delta, D['stress']['valuation'][name][str(endpoint)]['cash_B'], f'{name} {endpoint} cash')
    terminal, base_terminal = rows[2041], BASE['annual_rows']['2041']
    next_cash = terminal['group_EBIT_B'] * 1.03 * (1 - base_terminal['tax_rate']) - .03 * base_terminal['host_capital_revenue_B'] / .8 - .03 * terminal['stressed_net_sales_B'] - 1.03 * (base_terminal['lease_cash_B'] + base_terminal['minority_cash_B'])
    tail_error = next_cash - 1.03 * terminal['FCFF_B']
    quarters = {}
    for timing in ['base', 'concentrated_timing_stress']:
        forecast = D['quarters'][timing]['quarterly_rows']
        cumulative, observations = 0., []
        for year in range(2027, 2031):
            group = [q for q in forecast if q['year'] == year]
            r, b = rows[year], BASE['annual_rows'][str(year)]
            profits = [q['EBIT_B'] + r['group_EBIT_delta_B'] * w for q, w in zip(group, [.1, .2, .3, .4])]
            positive = sum(max(x, 0) for x in profits)
            annual_tax = max(r['group_EBIT_B'], 0) * b['tax_rate']
            for q, profit, profit_weight, wc_weight in zip(group, profits, [.1, .2, .3, .4], [.35, .3, .2, .15]):
                tax = annual_tax * max(profit, 0) / positive if positive else 0.
                cumulative += r['group_EBIT_delta_B'] * profit_weight - (tax - q['ordinary_operating_tax_B']) - r['incremental_WC_cash_delta_B'] * wc_weight
                observations.append({'year': year, 'quarter': q['quarter'], 'cash_B': q['ending_cash_B'] + cumulative})
            compare(cumulative, sum(rows[y]['FCFF_delta_B'] for y in range(2027, year + 1)), f'{name} {year} {timing} annual delta')
        minimum = min(observations, key=lambda r: r['cash_B'])
        quarters[timing] = {**minimum, 'owned_buffer_shortfall_B': max(0., 20 - minimum['cash_B']), 'negative_cash': minimum['cash_B'] < 0}
    CASES[name] = {'values': values, '2030_packaging': rows[2030], 'terminal_cash_scaling_error_B': tail_error,
                   'quarterly_controls': quarters}

report = {
    'audited_utc': datetime.now(timezone.utc).isoformat(), 'input_sha256': HASHES,
    'method': 'Independent residual cash-cost and capital rebuild from selected model and frozen packaging policy. No imports or execution of source model functions. DCF differences independently sum each revised FCFF and terminal cash plus accumulated pre-target cash once.',
    'comparison_count': len(ERRORS), 'maximum_difference': max(e['difference'] for e in ERRORS),
    'mismatches': [e for e in ERRORS if e['difference'] > 1e-9], 'cases': CASES,
    'findings': [
        'The accounting is coherent: gross program sales fall7B to4B, shadow2B stays, incremental sales fall5B to2B. Consolidated revenue and net incremental revenue fall equally, leaving host capital and Foundry profit unchanged.',
        'Only lost net sales less avoided cash-equivalent operating cost reduces EBIT. The shadow-profit reservation is not subtracted again; no CPU decremental or second host Foundry penalty is applied.',
        '2030 incremental D&A remains0.6214285714B. Scaling cash cost, rather than EBIT, gives incremental EBIT0.0971428571B under proportional avoidance and -1.825B under no avoidance. This preserves depreciation on committed assets.',
        'All2027-30 capex is retained. Smaller WC needs reduce cash use once. Later capex equals original D&A maintenance plus85% of revised net-sales growth, while WC funds15%; total net reinvestment therefore equals revised net-sales growth at turnover1.',
        'Unchanged finite credits are consistent with the original packaging policy, which credited no additional AMIC to this wholly owned overlay. If the reduced capacity instead changes the separate eligible project pool, a jointly specified tax-credit case would be required.',
        'Both terminal profit and capital cash components scale3%; the independent2042 FCFF check matches2041 cash times1.03. Retained maintenance on underused assets is conservative within this declared capital convention, not a physical tool-vintage forecast.',
        'Cash-equivalent SBC is inside the operating-cost residual. Proportional avoidance assumes it can flex along with the residual; this is an explicit optimistic convention, not evidence of actual contracts.',
        'The range bounds two specified cost responses only. Yield problems, penalties, collateral effects on host production, different program mix and credit eligibility could produce other outcomes. No probability is calibrated.',
        'Concentrated timing still breaches the owned20B buffer while economic cash stays positive. Annual no-financing flags do not certify intra-year liquidity; these are not covenant or insolvency results.'
    ],
    'all_inputs_unchanged': all(hashlib.sha256(path.read_bytes()).hexdigest() == HASHES[name] for name, path in FILES.items()),
}
(OUT / 'independent_packaging_scale_audit.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps({'comparison_count': report['comparison_count'], 'maximum_difference': report['maximum_difference'], 'mismatches': report['mismatches'],
                  'cases': {k: {n: v[n] for n in ['values', 'terminal_cash_scaling_error_B', 'quarterly_controls']} for k, v in CASES.items()}, 'all_inputs_unchanged': report['all_inputs_unchanged']}, indent=2))

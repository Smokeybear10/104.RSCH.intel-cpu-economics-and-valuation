from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import math

OUT = Path(__file__).resolve().parent
RUN = OUT.parent
FILES = {'base': RUN / 'root/integrated_results.json', 'policy': RUN / 'root/reverse_growth_policy.json',
         'results': RUN / 'root/reverse_growth_results.json',
         'host': RUN.parent / 'pricing_and_competition_review_2026_11_04/intel_server_ASP_mix_operating_policy.json',
         'pack': RUN.parent / 'intel_competition_screen_2026_11_04/external_packaging_operating_policy_2026_11_04.json'}
HASHES = {k: hashlib.sha256(p.read_bytes()).hexdigest() for k, p in FILES.items()}
D = {k: json.loads(p.read_text()) for k, p in FILES.items()}
BASE = D['base']['cases']['preferred']
B = {int(y): r for y, r in BASE['annual_rows'].items()}
HOST = {r['year']: r for r in D['host']['annual_rows']}
PACK = {r['year']: r for r in D['pack']['annual_rows']}
SHARES, G = 5.51, .03


def evaluate(growth: float, rate: float, mature: float) -> dict:
    rows = {y: {'FCFF': r['parent_unlevered_cash_B'], 'host': r['host_capital_revenue_B']} for y, r in B.items() if y <= 2030}
    for year in range(2031, 2042):
        source, p = B[year], PACK[year]
        cpu = B[2030]['CPU_revenue_B'] * (1 + growth) ** min(year - 2030, 10) * (1.03 if year == 2041 else 1)
        products = cpu + source['Other_DCAI_B'] + source['CCPG_revenue_B']
        host = products + source['net_All_Other_B'] + source['legacy_external_Foundry_B'] + source['shadow_packaging_B']
        consolidated = host + source['net_new_packaging_B']
        phase = min((year - 2030) / 10, 1)
        cpu_margin = B[2030]['CPU_margin'] * (1 - phase) + mature * phase
        dcai_profit = cpu * cpu_margin + source['Other_DCAI_B'] * source['Other_DCAI_margin']
        foundry = products * B[2030]['Foundry_profit_B'] / B[2030]['Products_revenue_B']
        ebit = dcai_profit + foundry + source['CCPG_profit_B'] + source['net_packaging_profit_B'] + source['Other_profit_less_corporate_B']
        host_change = host - rows[year - 1]['host']
        investment = host_change / .8 + p['incremental_net_operating_investment_B']
        wc = host_change * .1 + p['incremental_WC_cash_use_B']
        depreciation = HOST[year]['DA_fraction_of_Products_revenue'] * products + p['incremental_DA_B']
        capex = depreciation + investment - wc
        fcff = ebit - max(ebit, 0) * source['tax_rate'] - investment - source['lease_cash_B'] - source['minority_cash_B'] + source['old_credit_collection_B'] + source['new_credit_collection_B'] - source['credit_basis_loss_tax_B']
        rows[year] = {'CPU': cpu, 'Products': products, 'consolidated': consolidated, 'host': host, 'EBIT': ebit,
                      'investment': investment, 'WC': wc, 'DA': depreciation, 'capex': capex, 'FCFF': fcff}
    values = {}
    for endpoint in [2026, 2030]:
        explicit = math.fsum(r['FCFF'] / (1 + rate) ** (y - endpoint) for y, r in rows.items() if endpoint < y <= 2040)
        terminal = rows[2041]['FCFF'] / (rate - G) / (1 + rate) ** (2040 - endpoint)
        shield = math.fsum(r['financing_shield_B'] / (1 + rate) ** (y - endpoint) for y, r in B.items() if endpoint < y <= 2040) + B[2041]['financing_shield_B'] / rate / (1 + rate) ** (2040 - endpoint)
        escrow = math.fsum(f['escrow_cash_B'] / (1 + rate) ** (int(y) - endpoint) for y, f in BASE['treasury'].items() if endpoint < int(y))
        acquisition = math.fsum(f['Classiq_cash_B'] / (1 + rate) ** (int(y) - endpoint) for y, f in BASE['treasury'].items() if endpoint < int(y))
        claims = BASE['values'][str(endpoint)]
        values[endpoint] = (explicit + terminal + shield + claims['cash_B'] - claims['debt_B'] + claims['net_other_assets_B'] + escrow - acquisition) / SHARES
    return {'rows': rows, 'values': values}


checks = []
baseline = evaluate(1.02 ** 2 - 1, .11555, (7.055 - .2 * 3.3) / (18.632 - 3.3))
for year in range(2031, 2042):
    for ours, theirs in [('CPU', 'CPU_revenue_B'), ('Products', 'Products_revenue_B'), ('EBIT', 'EBIT_B'), ('capex', 'physical_capex_B'), ('FCFF', 'parent_unlevered_cash_B')]:
        checks.append(abs(baseline['rows'][year][ours] - B[year][theirs]))
cases, errors = [], []
for case in D['results']['cases']:
    rate, margin = case['rate'], case['mature_CPU_margin']
    endpoint, required = case['threshold_endpoint'], case['threshold_price']
    low, high = 0., .25
    assert evaluate(low, rate, margin)['values'][endpoint] < required < evaluate(high, rate, margin)['values'][endpoint]
    for _ in range(65):
        middle = (low + high) / 2
        if evaluate(middle, rate, margin)['values'][endpoint] < required:
            low = middle
        else:
            high = middle
    growth = (low + high) / 2
    actual = evaluate(growth, rate, margin)
    rows = actual['rows']
    computed = {'CPU_growth2031to2040': growth, 'planning_value': actual['values'][2026], 'target2030': actual['values'][2030],
                'CPU_revenue2040_B': rows[2040]['CPU'], 'consolidated_revenue2040_B': rows[2040]['consolidated'],
                'EBIT2040_B': rows[2040]['EBIT'], 'net_investment2031to2040_B': sum(rows[y]['investment'] for y in range(2031, 2041)),
                'terminal_cash2041_B': rows[2041]['FCFF']}
    for key, value in computed.items():
        errors.append({'rate': rate, 'margin': margin, 'endpoint': endpoint, 'field': key, 'error': abs(value - case[key])})
    grid = [evaluate(i / 400, rate, margin)['values'][endpoint] for i in range(101)]
    next_cash = rows[2041]['EBIT'] * 1.03 * (1 - B[2041]['tax_rate']) - .03 * rows[2041]['host'] / .8 - .03 * B[2041]['net_new_packaging_B'] - 1.03 * (B[2041]['lease_cash_B'] + B[2041]['minority_cash_B'])
    cases.append({'rate': rate, 'mature_margin': margin, 'endpoint': endpoint, **computed,
                  'root_residual_USD': actual['values'][endpoint] - required,
                  'strictly_increasing_on_0_to25pct_grid': all(b > a for a, b in zip(grid, grid[1:])),
                  'minimum_post2030_FCFF_B': min(rows[y]['FCFF'] for y in range(2031, 2042)),
                  'minimum_post2030_physical_capex_B': min(rows[y]['capex'] for y in range(2031, 2042)),
                  'terminal2042_cash_scaling_residual_B': next_cash - rows[2041]['FCFF'] * 1.03})

report = {'audited_utc': datetime.now(timezone.utc).isoformat(), 'input_sha256': HASHES,
          'method': 'Independent closed-form CPU revenue path, component EBIT, capital/WC, FCFF, DCF and bisection. No source-function imports. Validate each published hurdle and a101-point monotonicity grid per specified rate/margin/endpoint.',
          'baseline_comparisons': len(checks), 'baseline_max_error': max(checks), 'hurdle_comparisons': len(errors),
          'hurdle_max_error': max(e['error'] for e in errors), 'mismatches': [e for e in errors if e['error'] > 1e-9], 'cases': cases,
          'findings': ['The13.43805% and9.92090% CPU revenue CAGRs reconcile at the YTD-derived margin. Using the pooled margin instead lowers the corresponding planning hurdles to12.23655% and8.79934%.',
                       'Growth is explicitly funded at host turnover0.8 with working capital included, plus separate packaging investment; D&A and gross physical capex are recalculated. No extra capital subsidy or second packaging charge is introduced.',
                       'This is CPU revenue CAGR, not unit CAGR. It can combine unit, price and mix; the analysis does not identify that split or validate future market size, competitive share, technology or equipment capacity.',
                       'All near-term2027-2030 operating/treasury figures stay selected. The hurdle can compensate for that near-term path with unusually strong later growth; it is not an identified market forecast or investment recommendation.',
                       '2041 resets revenue growth to3% and the terminal tail is funded. All solved cases retain positive post2030 unlevered cash and positive gross capex, but this is not a complete future financing or physical-capacity schedule.',
                       'Planning52.25 is aDec31 value compared with aNov5 quote. The56-day mismatch must stay explicit; the separate2030 target hurdle uses the exact stated holding period.',
                       'The0-25% numerical search bracket contains each root and the tested response is monotone. The bracket is a computational choice, not an externally proven feasibility limit.',
                       'At a fixed rate and unchanged pre2031 cash, equal planning valuations necessarily imply equal2030 targets irrespective of the margin/growth combination. Those two endpoints are not independent corroboration.'],
          'all_inputs_unchanged': all(hashlib.sha256(p.read_bytes()).hexdigest() == HASHES[k] for k, p in FILES.items())}
(OUT / 'independent_reverse_growth_audit.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps({k: report[k] for k in ['audited_utc', 'baseline_comparisons', 'baseline_max_error', 'hurdle_comparisons', 'hurdle_max_error', 'mismatches', 'all_inputs_unchanged']}, indent=2))
print(json.dumps([{k: r[k] for k in ['rate', 'mature_margin', 'endpoint', 'CPU_growth2031to2040', 'minimum_post2030_FCFF_B', 'strictly_increasing_on_0_to25pct_grid', 'terminal2042_cash_scaling_residual_B']} for r in cases], indent=2))

from datetime import date, datetime, timezone
from pathlib import Path
import hashlib
import json
import math

OUT = Path(__file__).resolve().parent
RUN = OUT.parent
FILES = {
    'annual': RUN / 'root/integrated_results.json',
    'quarterly': RUN / 'root/quarterly_cash_results.json',
    'policy': RUN / 'margin/foundry_stress_policy.json',
    'results': RUN / 'margin/foundry_recovery_results.json',
    'source_engine': RUN / 'root/integrated_model.py',
    'source_calculator': RUN / 'margin/foundry_recovery_audit.py',
}
HASHES = {name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in FILES.items()}
D = {name: json.loads(path.read_text()) for name, path in FILES.items() if path.suffix == '.json'}
BASE = D['annual']['cases']['preferred']
POLICY = D['policy']['scenarios']
BASE_ROWS = {int(y): row for y, row in BASE['annual_rows'].items()}
R, G, SHARES = .11555, .03, 5.51
HOLDING_YEARS = (date(2030, 12, 31) - date(2026, 11, 5)).days / 365.25
COMPARISONS, CASES = [], {}


def check(actual: float, expected: float, label: str) -> None:
    COMPARISONS.append({'label': label, 'difference': abs(actual - expected)})


for name in ['selected', *POLICY]:
    rows, treasury = {}, {}
    cash = BASE['treasury']['2027']['opening_cash_B']
    debt = BASE['treasury']['2027']['opening_debt_B']
    for year, base in BASE_ROWS.items():
        if name == 'selected':
            foundry = base['Foundry_profit_B']
        elif name == 'flat_2027_loss':
            foundry = -4.12 if year == 2041 else -4.
        elif name == 'two_year_recovery_delay':
            foundry = [-4., -4., -4., -.75, 1., 2.5][year - 2027] if year <= 2032 else 2.5 * base['Products_revenue_B'] / BASE_ROWS[2032]['Products_revenue_B']
        else:
            foundry = [-4., -2.5, -1., 0.][year - 2027] if year <= 2030 else 0.
        ebit = base['DCAI_profit_B'] + base['CCPG_profit_B'] + base['Other_profit_less_corporate_B'] + base['net_packaging_profit_B'] + foundry
        tax = max(ebit, 0) * base['tax_rate']
        fcff = ebit - tax + base['DA_B'] - base['physical_capex_B'] - base['WC_cash_use_B'] - base['lease_cash_B'] - base['minority_cash_B'] + base['old_credit_collection_B'] + base['new_credit_collection_B'] - base['credit_basis_loss_tax_B']
        rows[year] = {'foundry': foundry, 'EBIT': ebit, 'tax': tax, 'FCFF': fcff}
        check(foundry, D['results']['scenario_annual_Foundry_profits_B'][name][str(year)], f'{name} {year} Foundry')
        check(ebit - base['EBIT_B'], foundry - base['Foundry_profit_B'], f'{name} {year} no extra profit penalty')
        if year <= 2030:
            f = BASE['treasury'][str(year)]
            owner = fcff - f['ordinary_interest_B'] - f['capitalized_interest_B'] + f['cash_income_B'] * (1 - base['tax_rate']) + base['financing_shield_B']
            cash += owner + f['escrow_cash_B'] - f['Classiq_cash_B'] - f['principal_B']
            debt -= f['principal_B']
            treasury[year] = {'owner': owner, 'cash': cash, 'debt': debt}
    values = {}
    for endpoint in [2026, 2030]:
        explicit = math.fsum(row['FCFF'] / (1 + R) ** (year - endpoint) for year, row in rows.items() if endpoint < year <= 2040)
        terminal = rows[2041]['FCFF'] / (R - G) / (1 + R) ** (2040 - endpoint)
        shield = math.fsum(row['financing_shield_B'] / (1 + R) ** (year - endpoint) for year, row in BASE_ROWS.items() if endpoint < year <= 2040)
        shield += BASE_ROWS[2041]['financing_shield_B'] / R / (1 + R) ** (2040 - endpoint)
        cash_value = BASE['treasury']['2027']['opening_cash_B'] if endpoint == 2026 else treasury[2030]['cash']
        debt_value = BASE['treasury']['2027']['opening_debt_B'] if endpoint == 2026 else treasury[2030]['debt']
        escrow = math.fsum(f['escrow_cash_B'] / (1 + R) ** (int(year) - endpoint) for year, f in BASE['treasury'].items() if int(year) > endpoint)
        acquisition = math.fsum(f['Classiq_cash_B'] / (1 + R) ** (int(year) - endpoint) for year, f in BASE['treasury'].items() if int(year) > endpoint)
        equity = explicit + terminal + shield + cash_value - debt_value + 4.502 + escrow - acquisition
        values[endpoint] = {'explicit_operating_PV_B': explicit, 'terminal_operating_PV_B': terminal,
                            'total_operating_value_B': explicit + terminal, 'financing_shield_PV_B': shield,
                            'cash_B': cash_value, 'debt_B': debt_value, 'net_other_assets_B': 4.502,
                            'remaining_escrow_PV_B': escrow, 'remaining_acquisition_PV_B': acquisition,
                            'equity_B': equity, 'price_USD': equity / SHARES}
        for key, value in values[endpoint].items():
            check(value, D['results']['scenario_values'][name][str(endpoint)][key], f'{name} {endpoint} {key}')
    quarters = {}
    for timing in ['base', 'concentrated_timing_stress']:
        forecast = D['quarterly'][timing]['quarterly_rows']
        result, accumulated_delta = [], 0.
        for year in range(2027, 2031):
            group = [q for q in forecast if q['year'] == year]
            cost_delta = rows[year]['foundry'] - BASE_ROWS[year]['Foundry_profit_B']
            profits = [q['EBIT_B'] + cost_delta / 4 for q in group]
            positive = sum(max(profit, 0) for profit in profits)
            for q, profit in zip(group, profits):
                new_tax = rows[year]['tax'] * max(profit, 0) / positive if positive else 0.
                accumulated_delta += cost_delta / 4 - (new_tax - q['ordinary_operating_tax_B'])
                result.append({'year': year, 'quarter': q['quarter'], 'cash_B': q['ending_cash_B'] + accumulated_delta})
            check(result[-1]['cash_B'], treasury[year]['cash'], f'{name} {year} {timing} Q4 vs annual cash')
        minimum = min(result, key=lambda row: row['cash_B'])
        quarters[timing] = {**minimum, 'below_owned20B_buffer_B': max(0., 20 - minimum['cash_B']), 'negative_cash': minimum['cash_B'] < 0}
    CASES[name] = {'values': values, 'minimum_annual_cash_B': min(f['cash'] for f in treasury.values()),
                   'owner_cash2027to2030_B': sum(f['owner'] for f in treasury.values()),
                   'annual_price_return': (values[2030]['price_USD'] / 52.25) ** (1 / HOLDING_YEARS) - 1,
                   'quarterly_cost_overlay_controls': quarters}
    for field in ['minimum_annual_cash_B', 'owner_cash2027to2030_B', 'annual_price_return']:
        check(CASES[name][field], D['results']['summaries'][name][field], f'{name} {field}')

report = {
    'audited_utc': datetime.now(timezone.utc).isoformat(), 'input_sha256': HASHES,
    'method': 'Independently replace only Foundry operating profit using the written policy; sum all group EBIT components; rebuild ordinary tax, FCFF, treasury and both valuation endpoints without importing source functions. Additional quarter overlays keep the existing base/concentrated timing and allocate the independent annual cost miss equally across quarters.',
    'comparison_count': len(COMPARISONS), 'maximum_difference': max(c['difference'] for c in COMPARISONS),
    'mismatches': [c for c in COMPARISONS if c['difference'] > 1e-9], 'cases': CASES,
    'findings': [
        'Foundry replaces one host-profit component once. DCAI, CCPG, corporate and net incremental packaging stay unchanged; no duplicate revenue decremental, absorption penalty or packaging profit is charged.',
        'All physical capex, D&A, working capital, leases, minority allowances and finite credits stay fixed. Lower EBIT therefore represents additional cash operating expense under the existing accounting policy, not a pure increase in noncash depreciation.',
        'A depreciation-only miss would require a matching D&A add-back and an explicit tax treatment. An impairment or reserve release also cannot be treated mechanically as recurring cash expense. Narrow the current cost/process/depreciation wording to a cash operating-cost recovery stress.',
        'These are isolated cost stresses at unchanged shipments and investment. A yield or ramp miss requiring more equipment, inventory or credits would need a separate jointly specified capital case; the present stresses do not establish that funding outcome.',
        'Annual buffer flags cannot certify intra-year liquidity. All cases are cash-positive under these quarter overlays, but the pre-existing concentrated timing stress breaches the owned20B buffer and Foundry cost misses deepen that shortfall.',
        'No additional borrowing is assumed. A buffer shortfall is an analyst funding preference, not negative cash, covenant failure or proven financing unavailability.',
        'Fixed dollar interest income and financing-shield assumptions are inherited. They are not recalculated from reduced cash balances; this is a retained-policy control, not a fully dynamic treasury model.',
        'The 2027 pre-D&A hurdle combines a frozen2026 Foundry-profit assumption of -8.5B with Q3 consolidated D&A annualized to12.928B. Neither is a disclosed matched full-year Foundry cash-cost baseline.',
        'Conditional internal-revenue intensity and allocated D&A bridges are accounting-dollar hurdles only. Their assumed75/90/100% allocation is not reported Foundry EBITDA and must not be added to consolidated external sales.'
    ],
    'all_inputs_unchanged': all(hashlib.sha256(path.read_bytes()).hexdigest() == HASHES[name] for name, path in FILES.items()),
}
(OUT / 'independent_foundry_cost_stress_audit.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps({'comparison_count': report['comparison_count'], 'maximum_difference': report['maximum_difference'], 'mismatches': report['mismatches'],
                  'quarterly_controls': {k: v['quarterly_cost_overlay_controls'] for k, v in CASES.items()}, 'all_inputs_unchanged': report['all_inputs_unchanged']}, indent=2))

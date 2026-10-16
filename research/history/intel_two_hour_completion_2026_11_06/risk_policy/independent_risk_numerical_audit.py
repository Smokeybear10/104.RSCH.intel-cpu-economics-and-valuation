from datetime import date, datetime, timezone
from pathlib import Path
import hashlib
import json
import math

OUT = Path(__file__).resolve().parent
RUN = OUT.parent
INPUTS = {
    'integrated': RUN / 'root/integrated_results.json',
    'anchor': RUN / 'quarterly/anchor_valuation_overlay_results.json',
    'rounded': OUT / 'rounded_ERP_comparison_results.json',
    'risk': OUT / 'risk_robustness_results.json',
}
data = {key: json.loads(path.read_text()) for key, path in INPUTS.items()}
INPUTS['original_financing'] = Path(data['integrated']['input_files']['raw']['path'])
raw = json.loads(INPUTS['original_financing'].read_text())
financing = {row['year']: row for row in raw['treasury_rows']}
cases = {
    'selected_operating': data['integrated']['cases']['preferred'],
    'existing_favorable_operating': data['anchor']['cases']['joint_anchor_old_CPU2028plus_growth_pooled_old_growth'],
}
shares, entry = 5.51, 52.25
holding_years = (date(2030, 12, 31) - date(2026, 11, 5)).days / 365.25
errors = []


def compare(label: str, calculated: float, reported: float) -> None:
    error = calculated - reported
    errors.append({'label': label, 'calculated': calculated, 'reported': reported, 'error': error})
    assert abs(error) < 1e-9, (label, error)


def cash_from_components(row: dict) -> float:
    return (row['EBIT_B'] - max(0, row['EBIT_B']) * row['tax_rate']
            - row['physical_capex_B'] + row['DA_B'] - row['WC_cash_use_B']
            - row['lease_cash_B'] - row['minority_cash_B']
            + row['old_credit_collection_B'] + row['new_credit_collection_B']
            - row['credit_basis_loss_tax_B'])


def check(case_name: str, rate: float, growth: float = .03) -> dict:
    case = cases[case_name]
    rows = {int(key): value for key, value in case['annual_rows'].items()}
    operating = {year: cash_from_components(row) for year, row in rows.items()}
    for year, amount in operating.items():
        compare(f'{case_name} operating cash {year}', amount, rows[year]['parent_unlevered_cash_B'])
    cash = case['treasury']['2027']['opening_cash_B']
    debt = case['treasury']['2027']['opening_debt_B']
    opening_cash, opening_debt = cash, debt
    for year in range(2027, 2031):
        f, r = financing[year], rows[year]
        cash += (operating[year] - f['ordinary_interest_B'] - f['capitalized_interest_B']
                 + f['cash_income_B'] * (1 - r['tax_rate']) + r['financing_shield_B']
                 + f['escrow_cash_B'] - f['Classiq_cash_B'] - f['principal_B'])
        debt -= f['principal_B']
        compare(f'{case_name} treasury cash {year}', cash, case['treasury'][str(year)]['ending_cash_B'])
        compare(f'{case_name} treasury debt {year}', debt, case['treasury'][str(year)]['ending_debt_B'])
    terminal_nopat = rows[2040]['EBIT_B'] * (1 + growth) * (1 - rows[2041]['tax_rate'])
    host_growth_funding = rows[2040]['host_capital_revenue_B'] * growth / .8
    packaging_growth_funding = rows[2040]['net_new_packaging_B'] * growth
    other_cash = (rows[2040]['lease_cash_B'] + rows[2040]['minority_cash_B']) * (1 + growth)
    first_terminal_cash = terminal_nopat - host_growth_funding - packaging_growth_funding - other_cash
    if growth == .03:
        compare(f'{case_name} funded terminal cash', first_terminal_cash, operating[2041])
    values = {}
    for endpoint in [2026, 2030]:
        explicit = math.fsum(operating[year] * (1 + rate) ** (endpoint - year)
                             for year in range(endpoint + 1, 2041))
        # Independently sum actual dated tail cash flows, rather than using the parent's evaluator.
        terminal = math.fsum(first_terminal_cash * (1 + growth) ** (year - 2041)
                             * (1 + rate) ** (endpoint - year) for year in range(2041, 3041))
        terminal_closed = first_terminal_cash / (rate - growth) * (1 + rate) ** (endpoint - 2040)
        compare(f'{case_name} rate{rate} growth{growth} tail sum {endpoint}', terminal, terminal_closed)
        shield_explicit = math.fsum(rows[year]['financing_shield_B'] * (1 + rate) ** (endpoint - year)
                                    for year in range(endpoint + 1, 2041))
        shield_tail = math.fsum(rows[2041]['financing_shield_B'] * (1 + rate) ** (endpoint - year)
                               for year in range(2041, 3041))
        shield_closed = rows[2041]['financing_shield_B'] / rate * (1 + rate) ** (endpoint - 2040)
        compare(f'{case_name} rate{rate} flat shield sum {endpoint}', shield_tail, shield_closed)
        escrow = math.fsum(financing[year]['escrow_cash_B'] * (1 + rate) ** (endpoint - year)
                           for year in range(endpoint + 1, 2031))
        acquisitions = math.fsum(financing[year]['Classiq_cash_B'] * (1 + rate) ** (endpoint - year)
                                 for year in range(endpoint + 1, 2031))
        cash_at_date, debt_at_date = (opening_cash, opening_debt) if endpoint == 2026 else (cash, debt)
        equity = explicit + terminal + shield_explicit + shield_tail + cash_at_date - debt_at_date + 4.502 + escrow - acquisitions
        values[str(endpoint)] = {
            'price_USD': equity / shares, 'explicit_operating_PV_B': explicit,
            'terminal_operating_PV_B': terminal, 'financing_shield_PV_B': shield_explicit + shield_tail,
            'remaining_escrow_PV_B': escrow, 'remaining_acquisition_PV_B': acquisitions,
            'cash_B': cash_at_date, 'debt_B': debt_at_date,
            'terminal_share_of_operating_value': terminal / (explicit + terminal),
        }
    target = values['2030']['price_USD']
    return {'case': case_name, 'rate': rate, 'growth': growth, 'values': values,
            'planning_value_USD': values['2026']['price_USD'], 'target2030_USD': target,
            'annual_price_return': (target / entry) ** (1 / holding_years) - 1,
            'entry_ceiling_for10pct_price_return_USD': target / 1.1 ** holding_years,
            'terminal_cash_B': first_terminal_cash,
            'terminal_growth_funding_B': host_growth_funding + packaging_growth_funding}


baseline, rounded, growth_controls = [], [], []
for name in cases:
    result = check(name, .11555)
    for endpoint, computed in result['values'].items():
        for field in ['price_USD', 'explicit_operating_PV_B', 'terminal_operating_PV_B', 'financing_shield_PV_B', 'cash_B', 'debt_B']:
            compare(f'baseline {name} {endpoint} {field}', computed[field], cases[name]['values'][endpoint][field])
    baseline.append(result)
    result = check(name, .10625)
    ref = data['rounded']['cases'][name]
    for endpoint, computed in result['values'].items():
        for field, expected in ref['values'][endpoint].items():
            compare(f'rounded {name} {endpoint} {field}', computed[field], expected)
    for field in ['planning_value_USD', 'target2030_USD', 'annual_price_return', 'entry_ceiling_for10pct_price_return_USD']:
        compare(f'rounded {name} {field}', result[field], ref[field])
    rounded.append(result)
for growth in [.02, .04]:
    result = check('selected_operating', .11555, growth)
    ref = next(row for row in data['risk']['funded_terminal_growth_controls'] if row['g'] == growth)
    for field in ['planning_value_USD', 'target2030_USD', 'annual_price_return']:
        compare(f'funded growth {growth} {field}', result[field], ref[field])
    compare(f'funded growth {growth} terminal cash', result['terminal_cash_B'], ref['terminal']['parent_unlevered_cash_B'])
    compare(f'funded growth {growth} funding', result['terminal_growth_funding_B'], ref['terminal']['net_operating_investment_B'])
    growth_controls.append(result)
output = {
    'computed_utc': datetime.now(timezone.utc).isoformat(),
    'scope': 'Independent numerical reconstruction from source annual components and original financing cash flows. No parent evaluate helper imported or called. This validates arithmetic conditional on supplied forecasts, not economic truth, scenario probabilities or investment returns.',
    'method': 'Operating cash reconstructed from EBIT/tax/capex/depreciation/working capital/leases/minorities/credit collections. Each case retains its own opening treasury balance; cash/debt rolled forward from original financing. Terminal operating and flat tax-shield streams summed year by year through3040 and compared with closed forms. No rounded source price substituted in calculations.',
    'input_receipts': [{'name': name, 'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()} for name, path in INPUTS.items()],
    'dates': {'entry': '2026-11-05', 'planning_value': '2026-12-31', 'exit': '2030-12-31', 'holding_years_ACT36525': holding_years},
    'baseline11555': baseline, 'published_rounded10625': rounded, 'funded_terminal_growth_controls': growth_controls,
    'validation': {'comparison_count': len(errors), 'maximum_absolute_error': max(abs(row['error']) for row in errors), 'tolerance': 1e-9, 'all_passed': True},
    'comparison_details': errors,
    'limits': ['Treasury income and financing paths remain supplied assumptions; sensitivity does not reprice borrowing or cash yields.', 'A November entry quote is not directly comparable to a December planning value without a date bridge.', 'The1000-year numerical tail is only a cross-check of the modeled perpetuity, not evidence the business persists that long.']
}
(OUT / 'independent_risk_numerical_audit.json').write_text(json.dumps(output, indent=2) + '\n')
print(json.dumps({key: output[key] for key in ['computed_utc', 'validation', 'baseline11555', 'published_rounded10625', 'funded_terminal_growth_controls']}, indent=2))

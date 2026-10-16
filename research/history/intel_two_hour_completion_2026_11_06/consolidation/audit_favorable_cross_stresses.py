from datetime import date, datetime, timezone
from pathlib import Path
import copy
import hashlib
import json
import math

OUT = Path(__file__).resolve().parent
RUN = OUT.parent
FILES = {'anchors': RUN / 'quarterly/anchor_valuation_overlay_results.json',
         'policy': RUN / 'margin/favorable_cross_stress_policy.json',
         'results': RUN / 'margin/favorable_cross_stress_results.json',
         'pack': RUN.parent / 'intel_competition_screen_2026_11_04/external_packaging_operating_policy_2026_11_04.json'}
HASHES = {k: hashlib.sha256(p.read_bytes()).hexdigest() for k, p in FILES.items()}
D = {k: json.loads(p.read_text()) for k, p in FILES.items()}
P = D['policy']
SOURCE = D['anchors']['cases'][P['favorable_case']]
PACK = {r['year']: r for r in D['pack']['annual_rows']}
SHARES, G, RATE = 5.51, .03, P['rate']
HOLDING = (date(2030, 12, 31) - date(2026, 11, 5)).days / 365.25
ERRORS, CASES = [], {}


def check(actual: float, expected: float, label: str) -> None:
    ERRORS.append({'label': label, 'difference': abs(actual - expected)})


for name in D['results']['summaries']:
    rows = {int(y): copy.deepcopy(row) for y, row in SOURCE['annual_rows'].items()}
    prior_net = 0.
    for year, row in rows.items():
        if name.startswith('missing_program'):
            p = PACK[year]
            gross = row['gross_new_packaging_B'] * 4 / 7
            net = gross - row['shadow_packaging_B']
            old_net = row['net_new_packaging_B']
            old_cash_cost = old_net - row['net_packaging_profit_B'] - p['incremental_DA_B']
            retained_cost = old_cash_cost * net / old_net if 'proportional' in name else old_cash_cost
            row['net_packaging_profit_B'] = net - retained_cost - p['incremental_DA_B']
            row['gross_new_packaging_B'] = gross
            row['net_new_packaging_B'] = net
            row['consolidated_revenue_B'] -= old_net - net
            new_wc = .15 * (net - prior_net)
            row['WC_cash_use_B'] += new_wc - p['incremental_WC_cash_use_B']
            if year > 2030:
                new_capex = p['incremental_DA_B'] + (net - prior_net) - new_wc
                row['physical_capex_B'] += new_capex - p['incremental_physical_cash_capex_B']
            prior_net = net
        elif name.startswith('two_year'):
            row['Foundry_profit_B'] = [-4., -4., -4., -.75, 1., 2.5][year - 2027] if year <= 2032 else 2.5 * row['Products_revenue_B'] / rows[2032]['Products_revenue_B']
        row['EBIT_B'] = sum(row[k] for k in ['DCAI_profit_B', 'CCPG_profit_B', 'Foundry_profit_B', 'Other_profit_less_corporate_B', 'net_packaging_profit_B'])
        row['ordinary_operating_tax_B'] = max(0., row['EBIT_B']) * row['tax_rate']
        row['NOPAT_B'] = row['EBIT_B'] - row['ordinary_operating_tax_B']
        row['net_operating_investment_B'] = row['physical_capex_B'] - row['DA_B'] + row['WC_cash_use_B']
        row['parent_unlevered_cash_B'] = row['NOPAT_B'] - row['net_operating_investment_B'] - row['lease_cash_B'] - row['minority_cash_B'] + row['old_credit_collection_B'] + row['new_credit_collection_B'] - row['credit_basis_loss_tax_B']
        expected = D['results']['reconstructed_cases_before_rate_change'][name]['annual_rows'][str(year)]
        for key, value in row.items():
            if isinstance(value, (float, int)):
                check(value, expected[key], f'{name} {year} {key}')
    cash, debt = SOURCE['values']['2026']['cash_B'], SOURCE['values']['2026']['debt_B']
    treasury = {}
    for year in range(2027, 2031):
        row, old = rows[year], SOURCE['treasury'][str(year)]
        owner = row['parent_unlevered_cash_B'] - old['ordinary_interest_B'] - old['capitalized_interest_B'] + old['cash_income_B'] * (1 - row['tax_rate']) + row['financing_shield_B']
        cash += owner + old['escrow_cash_B'] - old['Classiq_cash_B'] - old['principal_B']
        debt -= old['principal_B']
        treasury[year] = {'owner_cash_B': owner, 'ending_cash_B': cash, 'ending_debt_B': debt}
        for key, value in treasury[year].items():
            check(value, D['results']['reconstructed_cases_before_rate_change'][name]['treasury'][str(year)][key], f'{name} {year} {key}')
    last = rows[2040]
    nopat = last['EBIT_B'] * (1 + G) * (1 - rows[2041]['tax_rate'])
    investment = G * last['host_capital_revenue_B'] / .8 + G * last['net_new_packaging_B']
    terminal_claims = (last['lease_cash_B'] + last['minority_cash_B']) * (1 + G)
    terminal_cash = nopat - investment - terminal_claims
    terminal = {'NOPAT_B': nopat, 'net_operating_investment_B': investment, 'lease_and_minority_cash_B': terminal_claims,
                'parent_unlevered_cash_B': terminal_cash, 'reinvestment_fraction_of_NOPAT': investment / nopat,
                'implied_incremental_ROC': G * nopat / investment}
    for key, value in terminal.items():
        check(value, D['results']['risk_valuations'][name]['terminal'][key], f'{name} terminal {key}')
    check(terminal_cash, rows[2041]['parent_unlevered_cash_B'], f'{name} terminal rebuilt vs2041 row')
    values = {}
    for endpoint in [2026, 2030]:
        explicit = math.fsum(rows[y]['parent_unlevered_cash_B'] / (1 + RATE) ** (y - endpoint) for y in range(endpoint + 1, 2041))
        terminal_pv = terminal_cash / (RATE - G) / (1 + RATE) ** (2040 - endpoint)
        shield = math.fsum(rows[y]['financing_shield_B'] / (1 + RATE) ** (y - endpoint) for y in range(endpoint + 1, 2041)) + rows[2041]['financing_shield_B'] / RATE / (1 + RATE) ** (2040 - endpoint)
        escrow = math.fsum(SOURCE['treasury'][str(y)]['escrow_cash_B'] / (1 + RATE) ** (y - endpoint) for y in range(endpoint + 1, 2031))
        acquisition = math.fsum(SOURCE['treasury'][str(y)]['Classiq_cash_B'] / (1 + RATE) ** (y - endpoint) for y in range(endpoint + 1, 2031))
        cash_value = SOURCE['values']['2026']['cash_B'] if endpoint == 2026 else treasury[2030]['ending_cash_B']
        debt_value = SOURCE['values']['2026']['debt_B'] if endpoint == 2026 else treasury[2030]['ending_debt_B']
        price = (explicit + terminal_pv + shield + cash_value - debt_value + 4.502 + escrow - acquisition) / SHARES
        values[endpoint] = {'price_USD': price, 'explicit_operating_PV_B': explicit, 'terminal_operating_PV_B': terminal_pv,
                            'financing_shield_PV_B': shield, 'remaining_escrow_PV_B': escrow,
                            'remaining_acquisition_PV_B': acquisition, 'terminal_share_of_operating_value': terminal_pv / (explicit + terminal_pv)}
        for key, value in values[endpoint].items():
            check(value, D['results']['risk_valuations'][name]['values'][str(endpoint)][key], f'{name} {endpoint} {key}')
    CASES[name] = {'planning_value_USD': values[2026]['price_USD'], 'target2030_USD': values[2030]['price_USD'],
                   'annual_price_return': (values[2030]['price_USD'] / 52.25) ** (1 / HOLDING) - 1,
                   'opening2027_cash_B': SOURCE['values']['2026']['cash_B'], 'ending2030_cash_B': treasury[2030]['ending_cash_B'],
                   'minimum_annual_cash_B': min(r['ending_cash_B'] for r in treasury.values()), 'terminal': terminal}

report = {'audited_utc': datetime.now(timezone.utc).isoformat(), 'input_sha256': HASHES,
          'method': 'Independent arithmetic from favorable anchor annual rows, frozen packaging policy and stated scenarios. No source-model/helper imports. Rebuild all operating rows, taxes, owner cash, treasury, terminal reinvestment and both DCF dates at10.625%.',
          'comparisons': len(ERRORS), 'maximum_difference': max(e['difference'] for e in ERRORS),
          'mismatches': [e for e in ERRORS if e['difference'] > 1e-9], 'cases': CASES,
          'stale_recorded_inputs': [p for p, digest in D['results']['input_sha256'].items() if hashlib.sha256(Path(p).read_bytes()).hexdigest() != digest],
          'findings': ['Favorable Q4 opening cash50.991828B is preserved; it is not reset to selected50.839B. Each stress changes treasury before the2030 equity valuation.',
                       'No selected-case equity-value delta is borrowed. Packaging stress reallocates actual favorable cash rows; Foundry delay uses the favorable2032 Products denominator.',
                       'Terminal growth remains funded: incremental host sales use turnover0.8 and packaging sales turnover1. All terminal claims and profits scale3%.',
                       'The rate is the declared rounded plain-T12ERP convention10.625%, not the separately calculated unrounded10.631495%. The same rate is used for all four cases.',
                       'The operating cases are favorable, jointly assumed and unweighted. Planning value is datedDec31 while entry isNov5; their difference is not a same-date verified margin of safety.',
                       'These are separate single-stress controls, not a combined packaging/Foundry shock or a probability distribution. Annual cash minima do not certify quarter-end liquidity.'],
          'all_inputs_unchanged': all(hashlib.sha256(p.read_bytes()).hexdigest() == HASHES[k] for k, p in FILES.items())}
(OUT / 'independent_favorable_cross_stress_audit.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps({k: report[k] for k in ['audited_utc', 'comparisons', 'maximum_difference', 'mismatches', 'cases', 'stale_recorded_inputs', 'all_inputs_unchanged']}, indent=2))

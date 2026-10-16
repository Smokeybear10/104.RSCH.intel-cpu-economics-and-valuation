import hashlib
import json
import math
from datetime import date, datetime, timezone
from pathlib import Path


OUT = Path(__file__).resolve().parent
RESEARCH = OUT.parents[1]
MODEL = RESEARCH / 'pricing_and_competition_review_2026_11_04/intel_ASP20_mature_margin35_valuation.json'
HOST = RESEARCH / 'pricing_and_competition_review_2026_11_04/intel_server_ASP_mix_operating_policy.json'
REFERENCE = RESEARCH / 'intel_benchmark_rebuild_2026_11_05/return_value_bridge.json'
PACKAGING = RESEARCH / 'intel_competition_screen_2026_11_04/external_packaging_operating_policy_2026_11_04.json'
POLICY = OUT / 'diagnostic_policy.json'
inputs = {p.name: {'path': str(p), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in (MODEL, HOST, REFERENCE, PACKAGING, POLICY)}
model = json.loads(MODEL.read_text())
host = {r['year']: r for r in json.loads(HOST.read_text())['annual_rows']}
reference = json.loads(REFERENCE.read_text())
raw = {r['year']: r for r in model['annual_operating_rows']}
funding = {r['year']: r for r in model['treasury_rows']}
old_shields = {r['year']: r['financing_tax_benefit_B'] for r in model['financing_tax_benefit_rows']}
packaging = {r['year']: r for r in json.loads(PACKAGING.read_text())['annual_rows']}
R = .11555
G = .03
SHARES = 5.51
ENTRY = 52.22
HOLDING = (date(2030, 12, 31) - date(2026, 11, 5)).days / 365.25
NET_OTHER = model['values_at12pct']['2026']['net_other_assets_B']


def reconstruct(case: str = 'base') -> dict:
    rows = {}
    for y, r in raw.items():
        margin_weight = min(max((y - 2030) / 10, 0), 1)
        ebit = r['EBIT_after_economic_SBC_B'] + .05 * margin_weight * host[y]['DCAI_revenue_B']
        revenue = r['external_revenue_B']
        capex, da, wc = r['physical_cash_capex_B'], r['DA_B'], r['WC_cash_use_B']
        cpu_revenue = host[y]['server_CPU_revenue_proxy_B']
        dcai_revenue = host[y]['DCAI_revenue_B']
        dcai_profit = (host[y]['DCAI_margin'] + .08 * margin_weight) * dcai_revenue
        if case == 'temporary_2027_unit_shortfall_restore_2028':
            missed_sales = host[2027]['server_CPU_revenue_proxy_B'] * (1 - 1.1 / 1.2)
            if y == 2027:
                ebit -= .5 * missed_sales
                revenue -= missed_sales
                cpu_revenue -= missed_sales
                dcai_revenue -= missed_sales
                dcai_profit -= .5 * missed_sales
                wc -= .1 * missed_sales
            elif y == 2028:
                wc += .1 * missed_sales
        if case == 'remove_external_packaging_overlay':
            p = packaging[y]
            ebit -= p['net_incremental_operating_profit_B']
            revenue -= p['incremental_external_packaging_revenue_B']
            capex -= p['incremental_physical_cash_capex_B']
            da -= p['incremental_DA_B']
            wc -= p['incremental_WC_cash_use_B']
        if case == 'embedded_packaging_sales_capital_denominator':
            revenue += packaging[y]['existing_embedded_packaging_revenue_allowance_B']
        tax_rate = r['tax_rate']
        if case == 'mature_tax_21':
            tax_rate = .15 + .06 * min(max((y - 2030) / 5, 0), 1)
        tax = max(0, ebit) * tax_rate
        net_investment = capex - da + wc
        investment_delta = 0
        if case == 'capital_productivity_060' and y >= 2031:
            host_growth = host[y]['consolidated_external_revenue_for_capital_denominator_B'] - host[y - 1]['consolidated_external_revenue_for_capital_denominator_B']
            investment_delta = host_growth * (1 / .6 - 1 / .8)
        if case == 'embedded_packaging_sales_capital_denominator' and y >= 2031:
            investment_delta = (packaging[y]['existing_embedded_packaging_revenue_allowance_B'] - packaging[y - 1]['existing_embedded_packaging_revenue_allowance_B']) / .8
        new_collection = r['new_credit_collection_B'] if case != 'no_new_capital_credits' else 0
        basis_loss = r['credit_basis_loss_tax_B'] if case != 'no_new_capital_credits' else 0
        cash = ebit - tax - net_investment - investment_delta - r['lease_cash_B'] - r['minority_cash_B'] + r['old_credit_collection_B'] + new_collection - basis_loss
        shield = old_shields[y] * tax_rate / r['tax_rate']
        rows[y] = {
            'year': y, 'capital_denominator_revenue_B': revenue,
            'CPU_revenue_B': cpu_revenue,
            'DCAI_revenue_B': dcai_revenue,
            'DCAI_product_margin': dcai_profit / dcai_revenue,
            'EBIT_B': ebit, 'tax_rate': tax_rate, 'NOPAT_B': ebit - tax,
            'net_operating_investment_B': net_investment + investment_delta,
            'physical_capex_B': capex + investment_delta,
            'DA_B': da, 'WC_cash_use_B': wc,
            'lease_cash_B': r['lease_cash_B'], 'minority_cash_B': r['minority_cash_B'],
            'old_credit_collection_B': r['old_credit_collection_B'],
            'new_credit_collection_B': new_collection, 'credit_basis_loss_tax_B': basis_loss,
            'parent_unlevered_cash_B': cash, 'financing_shield_B': shield,
            'ordinary_operating_tax_B': tax,
        }
    if case == 'terminal_incremental_return_equal_operating_rate':
        new_investment = (rows[2041]['NOPAT_B'] - rows[2040]['NOPAT_B']) / R
        rows[2041]['parent_unlevered_cash_B'] -= new_investment - rows[2041]['net_operating_investment_B']
        rows[2041]['physical_capex_B'] += new_investment - rows[2041]['net_operating_investment_B']
        rows[2041]['net_operating_investment_B'] = new_investment

    treasury = {}
    cash_balance = funding[2027]['opening_economic_cash_B']
    debt_balance = funding[2027]['opening_ordinary_debt_B']
    for y in range(2027, 2031):
        f, r = funding[y], rows[y]
        owner_cash = r['parent_unlevered_cash_B'] - f['ordinary_interest_B'] - f['capitalized_interest_B'] + f['cash_income_B'] * (1 - r['tax_rate']) + r['financing_shield_B']
        cash_balance += owner_cash + f['escrow_cash_B'] - f['Classiq_cash_B'] - f['principal_B']
        debt_balance -= f['principal_B']
        treasury[y] = {'owner_cash_B': owner_cash, 'ending_economic_cash_B': cash_balance, 'ending_ordinary_debt_B': debt_balance}

    values = {}
    for endpoint in (2026, 2030):
        explicit = math.fsum(r['parent_unlevered_cash_B'] / (1 + R) ** (y - endpoint) for y, r in rows.items() if endpoint < y <= 2040)
        terminal = rows[2041]['parent_unlevered_cash_B'] / (R - G) / (1 + R) ** (2040 - endpoint)
        shield_pv = math.fsum(r['financing_shield_B'] / (1 + R) ** (y - endpoint) for y, r in rows.items() if endpoint < y <= 2040)
        shield_pv += rows[2041]['financing_shield_B'] / R / (1 + R) ** (2040 - endpoint)
        if endpoint == 2026:
            cash, debt = funding[2027]['opening_economic_cash_B'], funding[2027]['opening_ordinary_debt_B']
        else:
            cash, debt = treasury[endpoint]['ending_economic_cash_B'], treasury[endpoint]['ending_ordinary_debt_B']
        remaining_escrow = math.fsum(f['escrow_cash_B'] / (1 + R) ** (y - endpoint) for y, f in funding.items() if endpoint < y <= 2030)
        remaining_acquisition = math.fsum(f['Classiq_cash_B'] / (1 + R) ** (y - endpoint) for y, f in funding.items() if endpoint < y <= 2030)
        equity = explicit + terminal + cash - debt + NET_OTHER + remaining_escrow - remaining_acquisition + shield_pv
        values[endpoint] = {
            'explicit_operating_PV_B': explicit, 'terminal_operating_PV_B': terminal,
            'financing_tax_benefit_PV_B': shield_pv,
            'equity_B': equity, 'price_USD': equity / SHARES,
            'economic_cash_B': cash, 'ordinary_debt_B': debt,
            'terminal_share_of_equity': terminal / equity,
        }
    return {'rows': rows, 'treasury': treasury, 'values': values}


cases = {name: reconstruct(name) for name in [
    'base', 'capital_productivity_060', 'mature_tax_21',
    'no_new_capital_credits', 'terminal_incremental_return_equal_operating_rate',
    'embedded_packaging_sales_capital_denominator', 'remove_external_packaging_overlay',
    'temporary_2027_unit_shortfall_restore_2028',
]}
base = cases['base']
errors = []
for endpoint in (2026, 2030):
    expected = reference['by_endpoint'][str(endpoint)]['values']['base_demand_margin40']
    for key in ['price_USD', 'explicit_operating_PV_B', 'terminal_operating_PV_B', 'financing_tax_benefit_PV_B', 'equity_B']:
        errors.append(abs(base['values'][endpoint][key] - expected[key]))
        assert errors[-1] < 1e-9, (endpoint, key, errors[-1])
for y in range(2027, 2031):
    for own, original in [('owner_cash_B', 'owner_cash_after_financing_and_incentives_B'), ('ending_economic_cash_B', 'ending_economic_cash_B'), ('ending_ordinary_debt_B', 'ending_ordinary_debt_B')]:
        errors.append(abs(base['treasury'][y][own] - funding[y][original]))
        assert errors[-1] < 1e-9, (y, own, errors[-1])

terminal = base['rows'][2041]
prior = base['rows'][2040]
terminal_metrics = {
    'same_year_delta_NOPAT_over_net_investment': (terminal['NOPAT_B'] - prior['NOPAT_B']) / terminal['net_operating_investment_B'],
    'growth_over_reinvestment_fraction': G / (terminal['net_operating_investment_B'] / terminal['NOPAT_B']),
    'reinvestment_fraction_of_NOPAT': terminal['net_operating_investment_B'] / terminal['NOPAT_B'],
    'NOPAT_margin_on_capital_denominator': terminal['NOPAT_B'] / terminal['capital_denominator_revenue_B'],
    'physical_capex_fraction_of_capital_denominator': terminal['physical_capex_B'] / terminal['capital_denominator_revenue_B'],
    'explanation': 'The24%-range shorthand uses the conventional growth/reinvestment-rate formula. Same-year delta-NOPAT/net-investment is lower by1.03 because growth investment is measured contemporaneously. Neither is a measured historical ROIC or an independent second model input. Minority/lease reserves are deducted later in cash and no separate average invested-capital balance sheet is reconstructed.',
}
scenario_summary = []
for name, case in cases.items():
    p = case['values'][2030]['price_USD']
    scenario_summary.append({
        'case': name, 'December2026_planning_value': case['values'][2026]['price_USD'],
        'December2030_target': p, 'change_from_base_2030': p - base['values'][2030]['price_USD'],
        'annual_price_return_at_52_22': (p / ENTRY) ** (1 / HOLDING) - 1,
        'minimum_2027_2030_economic_cash_B': min(r['ending_economic_cash_B'] for r in case['treasury'].values()),
    })

ev2030 = base['values'][2030]['explicit_operating_PV_B'] + base['values'][2030]['terminal_operating_PV_B']
at2030 = base['rows'][2030]
matched_controls = {
    '2030_unlevered_operating_value_B': ev2030,
    '2030_operating_value_to_EBIT': ev2030 / at2030['EBIT_B'],
    '2030_operating_value_to_EBITDA': ev2030 / (at2030['EBIT_B'] + at2030['DA_B']),
    '2030_operating_value_to_revenue_capital_denominator': ev2030 / at2030['capital_denominator_revenue_B'],
    '2030_owner_cash_to_equity_value': base['treasury'][2030]['owner_cash_B'] / base['values'][2030]['equity_B'],
    'warning': 'Implied multiples summarize the sameDCF and are not independent validation. Revenue is the model capital denominator, not fully reconstructed consolidated revenue. Owner cash is economic, notGAAPFCF. No peer or historical average is imputed.',
}
result = {
    'computed_utc': datetime.now(timezone.utc).isoformat(),
    'input_files': inputs,
    'independently_reconstructed_base': base,
    'scenario_summary': scenario_summary,
    'diagnostic_cases': {k: v for k, v in cases.items() if k != 'base'},
    'terminal_economic_metrics': terminal_metrics,
    'implied_valuation_controls': matched_controls,
    'reconciliation': {'comparisons': len(errors), 'maximum_absolute_error': max(errors)},
    'limits': [
        'All diagnostics are owned stresses of a known model; they are not independently forecast outcomes, calibrated confidence intervals or probability weights.',
        'The terminal-return control changes only2041onward investment. It deliberately leaves large2031-2040growth and inherited2040profit intact, so it does not test full franchise failure or all competitive erosion.',
        'The terminal-return control does not stack a newg/ROICcharge on existingreinvestment: it replaces the selected terminalnetinvestment once.',
        'Removingnewcreditsalso removespairedtaxbasislosscostsandthecreditedcashaccumulatedbefore2030; oldreceivables remain.',
        'No revised recommendation is mechanically inferred from a stress target or the arbitrary choice of a hurdle.',
    ],
}
(OUT / 'reconstruction_results.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps({k: result[k] for k in ['scenario_summary', 'terminal_economic_metrics', 'implied_valuation_controls', 'reconciliation']}, indent=2))

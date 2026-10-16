from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import math

OUT = Path(__file__).resolve().parent
RUN = OUT.parent
FILES = {
    'quarterly_result': RUN / 'root/quarterly_cash_results.json',
    'quarter_policy': RUN / 'root/quarterly_cash_policy_before_calculation.json',
    'annual_result': RUN / 'root/integrated_results.json',
    'delivery': RUN / 'quarterly/selected_quarterly_forecast.json',
    'treasury_policy': OUT / 'treasury_calendar_policy_before_calculation.json',
    'finance': RUN.parent / 'intel_competition_screen_2026_11_04/financial_claims_and_treasury_policy_2026_11_04.json',
}
HASHES = {name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in FILES.items()}
D = {name: json.loads(path.read_text()) for name, path in FILES.items()}
A = D['annual_result']['cases']['preferred']['annual_rows']
POLICY = D['quarter_policy']
T = D['treasury_policy']
F = D['finance']['treasury_2027_2030']
CPU = {(r['year'], r['quarter']): r for r in D['delivery']['CPU_quarterly']}
CLIENT = {(r['year'], r['quarter']): r for r in D['delivery']['client_quarterly']}


def build(stress: bool, tax_shield_in_q4: bool = False, interest_weights: dict | None = None) -> list[dict]:
    timing = T['policy']['concentrated_cash_stress' if stress else 'uniform_base']
    rows = []
    cash = D['finance']['opening_2027_forecast']['opening_liquid_assets_B']
    debt = D['finance']['opening_2027_forecast']['opening_debt_B']
    for year in range(2027, 2031):
        a, i = A[str(year)], year - 2027
        year_rows = []
        for quarter in range(1, 5):
            q = quarter - 1
            c, pc = CPU[year, quarter], CLIENT[year, quarter]
            server_revenue = D['delivery']['anchors']['CPU_Q42026_revenue_B'] * c['unit_index_Q4_2026_100'] * c['ASP_index_Q4_2026_100'] / 10000
            pc_revenue = D['delivery']['anchors']['client_Q42026_revenue_B'] * pc['unit_index_Q4_2026_100'] * pc['ASP_index_Q4_2026_100'] / 10000
            other_dcai = a['Other_DCAI_B'] * POLICY['revenue']['Other_DCAI_weights'][q]
            ccpg_revenue = pc_revenue + a['Other_CCPG_B'] / 4
            dcai_profit = a['DCAI_profit_B'] / 4 + .5 * (server_revenue - a['CPU_revenue_B'] / 4) + .2 * (other_dcai - a['Other_DCAI_B'] / 4)
            pc_profit = a['CCPG_profit_B'] / 4 + .5 * (ccpg_revenue - a['CCPG_revenue_B'] / 4)
            pack_weight = POLICY['revenue']['gross_and_shadow_packaging_weights'][q]
            ebit = dcai_profit + pc_profit + a['Foundry_profit_B'] / 4 + a['Other_profit_less_corporate_B'] / 4 + a['net_packaging_profit_B'] * pack_weight
            total_revenue = server_revenue + other_dcai + ccpg_revenue + a['legacy_external_Foundry_B'] / 4 + a['net_All_Other_B'] / 4 + a['gross_new_packaging_B'] * pack_weight
            year_rows.append({'year': year, 'quarter': quarter, 'CPU_revenue_B': server_revenue, 'client_revenue_B': pc_revenue,
                              'consolidated_revenue_B': total_revenue, 'DCAI_profit_B': dcai_profit,
                              'CCPG_profit_B': pc_profit, 'EBIT_B': ebit})
        positive_profit = sum(max(row['EBIT_B'], 0) for row in year_rows)
        for q, row in enumerate(year_rows):
            quarter = q + 1
            ordinary_tax = a['ordinary_operating_tax_B'] * max(row['EBIT_B'], 0) / positive_profit
            capex_weight = [.4, .3, .2, .1][q] if stress else POLICY['investment']['physical_capex_weights'][q]
            capex = capex_weight * a['physical_capex_B']
            wc = a['WC_cash_use_B'] * POLICY['investment']['WC_cash_use_weights'][q]
            da = a['DA_B'] / 4
            credit_weight = float(quarter == 4) if stress else .25
            unlevered = row['EBIT_B'] - ordinary_tax + da - capex - wc - (a['lease_cash_B'] + a['minority_cash_B'] + a['credit_basis_loss_tax_B']) / 4 + credit_weight * (a['old_credit_collection_B'] + a['new_credit_collection_B'])
            weights = interest_weights[year] if interest_weights else timing['ordinary_interest_weights']
            interest = F['ordinary_cash_interest_B'][i] * weights[q]
            capital_interest = F['capitalized_cash_interest_inside_total_PPE_B'][i] * (weights[q] if interest_weights else timing['capitalized_interest_weights'][q])
            income = F['cash_interest_income_B'][i] * timing['cash_interest_income_weights'][q]
            shield = a['financing_shield_B'] * (float(quarter == 4) if tax_shield_in_q4 else .25)
            owner_cash = unlevered - interest - capital_interest + income * (1 - a['tax_rate']) + shield
            principal = 0.
            for instrument in T['instruments']:
                if instrument['year'] != year:
                    continue
                month = instrument['earliest_optional_tender_month'] if stress and instrument['earliest_optional_tender_month'] else instrument['month']
                if (month - 1) // 3 + 1 == quarter:
                    principal += instrument['principal_B']
            acquisition = F['Classiq_cash_B'][i] * timing.get(f'Classiq_{year}_weights', [0, 0, 0, 0])[q]
            escrow = F['government_escrow_cash_B'][i] * timing['escrow_cash_weights'][q]
            cash += owner_cash + escrow - acquisition - principal
            debt -= principal
            row.update({'ordinary_operating_tax_B': ordinary_tax, 'physical_capex_B': capex, 'DA_B': da, 'WC_cash_use_B': wc,
                        'parent_unlevered_cash_B': unlevered, 'owner_cash_B': owner_cash, 'principal_B': principal,
                        'ending_cash_B': cash, 'ending_debt_B': debt})
        for field in ['CPU_revenue_B', 'client_revenue_B', 'EBIT_B', 'consolidated_revenue_B', 'parent_unlevered_cash_B']:
            assert abs(math.fsum(r[field] for r in year_rows) - a[field]) < 1e-9
        rows.extend(year_rows)
    return rows


def minimum(rows: list[dict]) -> dict:
    row = min(rows, key=lambda r: r['ending_cash_B'])
    return {'year': row['year'], 'quarter': row['quarter'], 'economic_cash_B': row['ending_cash_B'],
            'headroom_over_owned20B_buffer_B': row['ending_cash_B'] - 20,
            'additional_liquidity_needed_for_owned_buffer_B': max(0, 20 - row['ending_cash_B']),
            'negative_cash': row['ending_cash_B'] < 0}


comparisons, errors = [], []
for name, stress in [('base', False), ('concentrated_timing_stress', True)]:
    rows = build(stress)
    expected = {(r['year'], r['quarter']): r for r in D['quarterly_result'][name]['quarterly_rows']}
    case_errors = [abs(value - expected[row['year'], row['quarter']][field]) for row in rows for field, value in row.items() if field not in ('year', 'quarter')]
    comparisons.append({'case': name, 'comparisons': len(case_errors), 'maximum_error_B': max(case_errors), 'independent_minimum': minimum(rows)})
    errors.extend(case_errors)
delayed_shield = build(True, tax_shield_in_q4=True)
output = {
    'audited_utc': datetime.now(timezone.utc).isoformat(), 'input_hashes': HASHES,
    'method': 'Independent quarter engine, no root function imports. Reconstruct revenue from unit and ASP indices; allocate profit by deviations from annual quarterly averages; use sourced principal instruments directly and independent timing-policy inputs.',
    'comparisons': comparisons, 'all_compared_values_match': max(errors) < 1e-9,
    'additional_same_annual_total_control': {'name': 'Concentrated timing plus all annual financing tax benefit realized in Q4', 'minimum': minimum(delayed_shield),
                                          'status': 'Analyst timing stress, not a statement of tax-filing due dates. Annual totals and year-end cash unchanged.'},
    'findings': [
        'The concentrated timing case remains cash-positive but breaches the analyst-owned 20B economic buffer. It is not a disclosed covenant failure or insolvency result.',
        'No commitment to borrow or guaranteed funding is assumed. If the buffer is binding, management could use cash below it, retime discretionary payments or arrange financing; each action requires an explicit policy and financing costs.',
        'The stress combines several adverse timing assumptions while annual economics are fixed. Its peak funding need is not a statistically calibrated event probability.',
        'Current quarter-end figures reserve economic SBC and minority claims, and therefore are not literal consolidated bank balances or proof of unrestricted cash access.',
        'The base allocates financing tax benefits uniformly even in the concentrated-interest stress. Delaying them to Q4 is a transparent additional timing control; it modestly increases the buffer shortfall.',
    ],
    'verification': {'all_annual_operating_totals_match': True, 'all_principal_dates_independently_rebuilt': True,
                     'no_extra_grant_or_SBC_charge': True, 'all_inputs_unchanged': all(hashlib.sha256(p.read_bytes()).hexdigest() == HASHES[k] for k, p in FILES.items())},
}
(OUT / 'independent_quarterly_cash_audit.json').write_text(json.dumps(output, indent=2) + '\n')
print(json.dumps({k: output[k] for k in ['comparisons', 'all_compared_values_match', 'additional_same_annual_total_control', 'verification']}, indent=2))

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


OUT = Path(__file__).resolve().parent
RUN = OUT.parent
PATHS = {
    'annual': OUT / 'integrated_results.json',
    'delivery': RUN / 'quarterly/selected_quarterly_forecast.json',
    'treasury': RUN / 'consolidation/quarterly_treasury_calendar.json',
    'policy': OUT / 'quarterly_cash_policy_before_calculation.json',
}
D = {k: json.loads(p.read_text()) for k, p in PATHS.items()}
ANNUAL = {int(y): r for y, r in D['annual']['cases']['preferred']['annual_rows'].items()}
CPU = {(r['year'], r['quarter']): r for r in D['delivery']['CPU_quarterly']}
CLIENT = {(r['year'], r['quarter']): r for r in D['delivery']['client_quarterly']}
P = D['policy']


def build(stress: bool = False) -> dict:
    schedule = D['treasury']['concentrated_timing_stress' if stress else 'base']['quarterly_rows']
    funding = {(r['year'], r['quarter']): r for r in schedule}
    rows = []
    cash, debt = 50.839, 50.134
    annual_errors = []
    for y in range(2027, 2031):
        a = ANNUAL[y]
        year_rows = []
        cpu_retained_cost = .5 * a['CPU_revenue_B'] + .2 * a['Other_DCAI_B'] - a['DCAI_profit_B']
        ccpg_retained_cost = .5 * a['CCPG_revenue_B'] - a['CCPG_profit_B']
        for q in range(1, 5):
            k = q - 1
            cpu, client, f = CPU[y, q], CLIENT[y, q], funding[y, q]
            pack_weight = P['revenue']['gross_and_shadow_packaging_weights'][k]
            other_weight = P['revenue']['Other_DCAI_weights'][k]
            row = {
                'year': y, 'quarter': q, 'CPU_revenue_B': cpu['CPU_revenue_B'],
                'client_revenue_B': client['client_revenue_B'],
                'CPU_unit_index': cpu['unit_index_Q4_2026_100'], 'CPU_ASP_index': cpu['ASP_index_Q4_2026_100'],
                'client_unit_index': client['unit_index_Q4_2026_100'], 'client_ASP_index': client['ASP_index_Q4_2026_100'],
                'Other_DCAI_B': a['Other_DCAI_B'] * other_weight,
                'Other_CCPG_B': a['Other_CCPG_B'] / 4,
                'legacy_external_Foundry_B': a['legacy_external_Foundry_B'] / 4,
                'net_All_Other_B': a['net_All_Other_B'] / 4,
                'gross_new_packaging_B': a['gross_new_packaging_B'] * pack_weight,
            }
            row['DCAI_revenue_B'] = row['CPU_revenue_B'] + row['Other_DCAI_B']
            row['CCPG_revenue_B'] = row['client_revenue_B'] + row['Other_CCPG_B']
            row['Products_revenue_B'] = row['DCAI_revenue_B'] + row['CCPG_revenue_B']
            row['consolidated_revenue_B'] = row['Products_revenue_B'] + row['legacy_external_Foundry_B'] + row['net_All_Other_B'] + row['gross_new_packaging_B']
            row['DCAI_profit_B'] = .5 * row['CPU_revenue_B'] + .2 * row['Other_DCAI_B'] - cpu_retained_cost / 4
            row['CCPG_profit_B'] = .5 * row['CCPG_revenue_B'] - ccpg_retained_cost / 4
            row['Foundry_profit_B'] = a['Foundry_profit_B'] / 4
            row['net_packaging_profit_B'] = a['net_packaging_profit_B'] * pack_weight
            row['Other_profit_less_corporate_B'] = a['Other_profit_less_corporate_B'] / 4
            row['EBIT_B'] = sum(row[t] for t in ('DCAI_profit_B', 'CCPG_profit_B', 'Foundry_profit_B', 'net_packaging_profit_B', 'Other_profit_less_corporate_B'))
            year_rows.append(row)
        positive_ebit = sum(max(r['EBIT_B'], 0) for r in year_rows)
        for k, row in enumerate(year_rows):
            f = funding[y, k + 1]
            row['ordinary_operating_tax_B'] = a['ordinary_operating_tax_B'] * max(row['EBIT_B'], 0) / positive_ebit if positive_ebit else 0
            capex_weights = [.4, .3, .2, .1] if stress else P['investment']['physical_capex_weights']
            credit_weight = (1 if k == 3 else 0) if stress else .25
            row['physical_capex_B'] = a['physical_capex_B'] * capex_weights[k]
            row['DA_B'] = a['DA_B'] / 4
            row['WC_cash_use_B'] = a['WC_cash_use_B'] * P['investment']['WC_cash_use_weights'][k]
            for field in ('lease_cash_B', 'minority_cash_B', 'credit_basis_loss_tax_B', 'financing_shield_B'):
                row[field] = a[field] / 4
            for field in ('old_credit_collection_B', 'new_credit_collection_B'):
                row[field] = a[field] * credit_weight
            row['net_operating_investment_B'] = row['physical_capex_B'] - row['DA_B'] + row['WC_cash_use_B']
            row['parent_unlevered_cash_B'] = (row['EBIT_B'] - row['ordinary_operating_tax_B'] - row['net_operating_investment_B']
                                             - row['lease_cash_B'] - row['minority_cash_B'] + row['old_credit_collection_B']
                                             + row['new_credit_collection_B'] - row['credit_basis_loss_tax_B'])
            row['ordinary_interest_B'] = f['ordinary_cash_interest_B']
            row['capitalized_interest_B'] = f['capitalized_cash_interest_inside_total_PPE_B']
            row['cash_income_B'] = f['cash_interest_income_B']
            row['owner_cash_B'] = (row['parent_unlevered_cash_B'] - row['ordinary_interest_B'] - row['capitalized_interest_B']
                                    + row['cash_income_B'] * (1 - a['tax_rate']) + row['financing_shield_B'])
            row['escrow_cash_B'] = f['government_escrow_cash_B']
            row['Classiq_cash_B'] = f['Classiq_cash_B']
            row['principal_B'] = f['scheduled_principal_B']
            row['opening_cash_B'], row['opening_debt_B'] = cash, debt
            cash += row['owner_cash_B'] + row['escrow_cash_B'] - row['Classiq_cash_B'] - row['principal_B']
            debt -= row['principal_B']
            row['ending_cash_B'], row['ending_debt_B'] = cash, debt
        for field in ('CPU_revenue_B', 'client_revenue_B', 'consolidated_revenue_B', 'DCAI_profit_B', 'CCPG_profit_B', 'EBIT_B', 'ordinary_operating_tax_B', 'physical_capex_B', 'DA_B', 'WC_cash_use_B', 'parent_unlevered_cash_B'):
            annual_errors.append({'year': y, 'field': field, 'absolute_error_B': abs(sum(r[field] for r in year_rows) - a[field])})
        treasury = D['annual']['cases']['preferred']['treasury'][str(y)]
        for field in ('ending_cash_B', 'ending_debt_B'):
            annual_errors.append({'year': y, 'field': field, 'absolute_error_B': abs(year_rows[-1][field] - treasury[field])})
        rows.extend(year_rows)
    assert max(r['absolute_error_B'] for r in annual_errors) < 1e-9
    minimum = min(rows, key=lambda r: r['ending_cash_B'])
    return {'quarterly_rows': rows, 'annual_reconciliation': annual_errors,
            'minimum_quarter_end_cash_B': minimum['ending_cash_B'],
            'minimum_cash_period': f"Q{minimum['quarter']} {minimum['year']}",
            'headroom_over_owned20B_cash_floor_B': minimum['ending_cash_B'] - 20,
            'requires_financing_extension': minimum['ending_cash_B'] < 20}


result = {'computed_utc': datetime.now(timezone.utc).isoformat(),
          'input_files': {k: {'path': str(p), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for k, p in PATHS.items()},
          'base': build(), 'concentrated_timing_stress': build(True),
          'limits': ['Timing conventions are explicit; only scheduled principal dates are fully source-anchored.', 'Quarter-end liquidity is not daily liquidity, unrestricted cash access, or an available credit commitment.', 'Mobileye grant working capital is included once inside the envelope.', 'This is an operating cash model, not a complete projected GAAP balance sheet or cash-flow statement.']}
(OUT / 'quarterly_cash_results.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps({key: {k: v for k, v in result[key].items() if k not in ('quarterly_rows', 'annual_reconciliation')} for key in ('base', 'concentrated_timing_stress')}, indent=2))

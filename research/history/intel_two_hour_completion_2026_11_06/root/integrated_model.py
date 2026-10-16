import copy
import hashlib
import json
import math
from datetime import date, datetime, timezone
from pathlib import Path


OUT = Path(__file__).resolve().parent
RUN = OUT.parent
RESEARCH = RUN.parent
FILES = {
    'raw': RESEARCH / 'pricing_and_competition_review_2026_11_04/intel_ASP20_mature_margin35_valuation.json',
    'host': RESEARCH / 'pricing_and_competition_review_2026_11_04/intel_server_ASP_mix_operating_policy.json',
    'pack': RESEARCH / 'intel_competition_screen_2026_11_04/external_packaging_operating_policy_2026_11_04.json',
    'prior': RESEARCH / 'intel_edge_resolution_2026_11_06/price/price_refresh_52_25_overlay.json',
    'cpu': RUN / 'quarterly/quarterly_delivery_results.json',
    'client': RUN / 'quarterly/client_quarterly_results.json',
    'quarters': RUN / 'quarterly/quarterly_2027_2030_results.json',
    'selected_quarters': RUN / 'quarterly/selected_quarterly_forecast.json',
    'margin': RUN / 'margin/selected_margin_policy.json',
    'policy': OUT / 'integration_policy_before_calculation.json',
}
DATA = {k: json.loads(p.read_text()) for k, p in FILES.items()}
RAW = {r['year']: r for r in DATA['raw']['annual_operating_rows']}
HOST = {r['year']: r for r in DATA['host']['annual_rows']}
PACK = {r['year']: r for r in DATA['pack']['annual_rows']}
FUND = {r['year']: r for r in DATA['raw']['treasury_rows']}
SHIELD = {r['year']: r['financing_tax_benefit_B'] for r in DATA['raw']['financing_tax_benefit_rows']}
P = DATA['margin']['preferred']
R, G, SHARES, ENTRY = .11555, .03, 5.51, 52.25
NET_OTHER = 4.502
YEARS = (date(2030, 12, 31) - date(2026, 11, 5)).days / 365.25


def close_cash(row: dict) -> None:
    row['ordinary_operating_tax_B'] = max(row['EBIT_B'], 0) * row['tax_rate']
    row['NOPAT_B'] = row['EBIT_B'] - row['ordinary_operating_tax_B']
    row['net_operating_investment_B'] = row['physical_capex_B'] - row['DA_B'] + row['WC_cash_use_B']
    row['parent_unlevered_cash_B'] = (
        row['NOPAT_B'] - row['net_operating_investment_B'] - row['lease_cash_B']
        - row['minority_cash_B'] + row['old_credit_collection_B']
        + row['new_credit_collection_B'] - row['credit_basis_loss_tax_B']
    )


def value(rows: dict, opening_cash_delta: float = 0) -> dict:
    cash = FUND[2027]['opening_economic_cash_B'] + opening_cash_delta
    debt = FUND[2027]['opening_ordinary_debt_B']
    treasury = {}
    for y in range(2027, 2031):
        r, f = rows[y], FUND[y]
        owner = (r['parent_unlevered_cash_B'] - f['ordinary_interest_B']
                 - f['capitalized_interest_B'] + f['cash_income_B'] * (1 - r['tax_rate'])
                 + r['financing_shield_B'])
        opening_cash, opening_debt = cash, debt
        cash += owner + f['escrow_cash_B'] - f['Classiq_cash_B'] - f['principal_B']
        debt -= f['principal_B']
        treasury[y] = {
            'year': y, 'opening_cash_B': opening_cash, 'opening_debt_B': opening_debt,
            'owner_cash_B': owner, 'ordinary_interest_B': f['ordinary_interest_B'],
            'capitalized_interest_B': f['capitalized_interest_B'], 'cash_income_B': f['cash_income_B'],
            'escrow_cash_B': f['escrow_cash_B'], 'Classiq_cash_B': f['Classiq_cash_B'],
            'principal_B': f['principal_B'], 'ending_cash_B': cash, 'ending_debt_B': debt,
        }
    values = {}
    for endpoint in (2026, 2030):
        explicit = math.fsum(r['parent_unlevered_cash_B'] / (1 + R) ** (y - endpoint)
                             for y, r in rows.items() if endpoint < y <= 2040)
        terminal = rows[2041]['parent_unlevered_cash_B'] / (R - G) / (1 + R) ** (2040 - endpoint)
        shield = math.fsum(r['financing_shield_B'] / (1 + R) ** (y - endpoint)
                           for y, r in rows.items() if endpoint < y <= 2040)
        shield += rows[2041]['financing_shield_B'] / R / (1 + R) ** (2040 - endpoint)
        cash_value = FUND[2027]['opening_economic_cash_B'] + opening_cash_delta if endpoint == 2026 else treasury[2030]['ending_cash_B']
        debt_value = FUND[2027]['opening_ordinary_debt_B'] if endpoint == 2026 else treasury[2030]['ending_debt_B']
        escrow = math.fsum(f['escrow_cash_B'] / (1 + R) ** (y - endpoint) for y, f in FUND.items() if endpoint < y <= 2030)
        acquisition = math.fsum(f['Classiq_cash_B'] / (1 + R) ** (y - endpoint) for y, f in FUND.items() if endpoint < y <= 2030)
        equity = explicit + terminal + shield + cash_value - debt_value + NET_OTHER + escrow - acquisition
        values[endpoint] = {
            'explicit_operating_PV_B': explicit, 'terminal_operating_PV_B': terminal,
            'total_operating_value_B': explicit + terminal, 'financing_shield_PV_B': shield,
            'cash_B': cash_value, 'debt_B': debt_value, 'net_other_assets_B': NET_OTHER,
            'remaining_escrow_PV_B': escrow, 'remaining_acquisition_PV_B': acquisition,
            'equity_B': equity, 'price_USD': equity / SHARES,
        }
    return {'annual_rows': rows, 'treasury': treasury, 'values': values,
            'minimum_annual_cash_B': min(r['ending_cash_B'] for r in treasury.values()),
            'requires_financing_extension': min(r['ending_cash_B'] for r in treasury.values()) < 20}


def old_rows() -> dict:
    rows = {}
    for y, raw in RAW.items():
        h, p = HOST[y], PACK[y]
        phase = min(max((y - 2030) / 10, 0), 1)
        dcai_profit = (h['DCAI_margin'] + .08 * phase) * h['DCAI_revenue_B']
        ebit = raw['EBIT_after_economic_SBC_B'] + .05 * phase * h['DCAI_revenue_B']
        group_residual = ebit - dcai_profit - h['CCPG_operating_profit_B'] - h['Foundry_operating_profit_B'] - p['net_incremental_operating_profit_B']
        row = {
            'year': y, 'CPU_revenue_B': h['server_CPU_revenue_proxy_B'],
            'client_revenue_B': h['client_revenue_B'], 'Other_CCPG_B': h['Other_CCPG_revenue_B'],
            'Other_DCAI_B': h['Other_DCAI_revenue_B'], 'DCAI_revenue_B': h['DCAI_revenue_B'],
            'CCPG_revenue_B': h['CCPG_revenue_B'], 'Products_revenue_B': h['Products_revenue_B'],
            'All_Other_gross_B': h['root_Other_revenue_for_capital_denominator_B'],
            'All_Other_internal_B': 0, 'legacy_external_Foundry_B': 0,
            'gross_new_packaging_B': p['gross_external_packaging_revenue_B'],
            'shadow_packaging_B': p['existing_embedded_packaging_revenue_allowance_B'],
            'net_new_packaging_B': p['incremental_external_packaging_revenue_B'],
            'consolidated_revenue_B': raw['external_revenue_B'],
            'host_capital_revenue_B': h['consolidated_external_revenue_for_capital_denominator_B'],
            'CPU_margin': (dcai_profit - .2 * h['Other_DCAI_revenue_B']) / h['server_CPU_revenue_proxy_B'],
            'Other_DCAI_margin': .2, 'DCAI_profit_B': dcai_profit,
            'CCPG_margin': h['CCPG_margin'], 'CCPG_profit_B': h['CCPG_operating_profit_B'],
            'Foundry_profit_B': h['Foundry_operating_profit_B'],
            'net_packaging_profit_B': p['net_incremental_operating_profit_B'],
            'Other_profit_less_corporate_B': group_residual,
            'EBIT_B': ebit, 'physical_capex_B': raw['physical_cash_capex_B'],
            'DA_B': raw['DA_B'], 'WC_cash_use_B': raw['WC_cash_use_B'],
            'tax_rate': raw['tax_rate'], 'lease_cash_B': raw['lease_cash_B'],
            'minority_cash_B': raw['minority_cash_B'],
            'old_credit_collection_B': raw['old_credit_collection_B'],
            'new_credit_collection_B': raw['new_credit_collection_B'],
            'credit_basis_loss_tax_B': raw['credit_basis_loss_tax_B'],
            'financing_shield_B': SHIELD[y],
        }
        close_cash(row)
        rows[y] = row
    return rows


def build_case(delivery: str = 'old', revised_other: bool = False,
               component_margin: bool = False, normalized_growth: bool = False,
               cpu_margin: float | None = None, other_margin: float = .2,
               response: float = .5, capital_turnover: float = .8,
               foundry_terminal_ratio: float | None = None,
               anchor_case: dict | None = None) -> dict:
    rows = old_rows()
    control = 'preferred' if delivery == 'annual_control' else delivery
    cpu_source = DATA['selected_quarters']['annual_rows'] if delivery == 'preferred' else DATA['cpu']['cases'].get(control, {}).get('annual_2027_2030', [])
    cpu_input = {r['year']: r for r in cpu_source}
    client_input = {r['year']: r for r in DATA['client']['cases'].get(control, {}).get('annual_2027_2030', [])}
    anchor_annual = {r['year']: r for r in anchor_case['annual_rows']} if anchor_case else {}
    for y, r in rows.items():
        h, p = HOST[y], PACK[y]
        if delivery != 'old':
            if y <= 2030:
                r['CPU_revenue_B'] = cpu_input[y]['CPU_revenue_B']
                r['client_revenue_B'] = client_input[y]['client_revenue_B']
            else:
                prior = rows[y - 1]
                cpu_factor = 1.03 if y == 2041 else (1.02 ** 2 if normalized_growth else (1 + h['server_unit_growth']) * (1 + h['server_ASP_growth']))
                r['CPU_revenue_B'] = prior['CPU_revenue_B'] * cpu_factor
                r['client_revenue_B'] = prior['client_revenue_B'] * (1 + h['client_unit_growth']) * (1 + h['client_ASP_growth'])
        if revised_other:
            prior_other = 5.19 if y == 2027 else rows[y - 1]['Other_DCAI_B']
            growth = P['Other_DCAI_growth_2027_2030'][y - 2027] if y <= 2030 else h['Other_DCAI_growth']
            r['Other_DCAI_B'] = prior_other * (1 + growth)
        if anchor_case and y <= 2030:
            r['CPU_revenue_B'] = anchor_annual[y]['CPU_revenue_B']
            r['client_revenue_B'] = anchor_annual[y]['client_revenue_B']
            r['Other_DCAI_B'] = anchor_annual[y]['Other_DCAI_B']
        r['DCAI_revenue_B'] = r['CPU_revenue_B'] + r['Other_DCAI_B']
        r['CCPG_revenue_B'] = r['client_revenue_B'] + r['Other_CCPG_B']
        r['Products_revenue_B'] = r['DCAI_revenue_B'] + r['CCPG_revenue_B']
        multiplier = 1.03 ** max(y - 2030, 0)
        r['All_Other_internal_B'] = .020 * multiplier
        r['legacy_external_Foundry_B'] = .934 * multiplier
        r['net_All_Other_B'] = r['All_Other_gross_B'] - r['All_Other_internal_B']
        r['consolidated_revenue_B'] = r['Products_revenue_B'] + r['net_All_Other_B'] + r['legacy_external_Foundry_B'] + r['gross_new_packaging_B']
        r['host_capital_revenue_B'] = r['consolidated_revenue_B'] - r['net_new_packaging_B']
        cpu_delta = r['CPU_revenue_B'] - h['server_CPU_revenue_proxy_B']
        client_delta = r['client_revenue_B'] - h['client_revenue_B']
        other_delta = r['Other_DCAI_B'] - h['Other_DCAI_revenue_B']
        if y <= 2030:
            r['DCAI_profit_B'] += response * cpu_delta + .2 * other_delta
            r['CCPG_profit_B'] += response * client_delta
            r['CCPG_margin'] = r['CCPG_profit_B'] / r['CCPG_revenue_B']
            r['CPU_margin'] = (r['DCAI_profit_B'] - .2 * r['Other_DCAI_B']) / r['CPU_revenue_B']
        elif component_margin:
            phase = min((y - 2030) / 10, 1)
            start = rows[2030]
            mature_cpu = P['mature_CPU_margin'] if cpu_margin is None else cpu_margin
            r['CPU_margin'] = start['CPU_margin'] + phase * (mature_cpu - start['CPU_margin'])
            r['Other_DCAI_margin'] = .2 + phase * (other_margin - .2)
            r['DCAI_profit_B'] = r['CPU_margin'] * r['CPU_revenue_B'] + r['Other_DCAI_margin'] * r['Other_DCAI_B']
            r['CCPG_margin'] = start['CCPG_margin'] + phase * (.28 - start['CCPG_margin'])
            r['CCPG_profit_B'] = r['CCPG_margin'] * r['CCPG_revenue_B']
            start_ratio = start['Foundry_profit_B'] / start['Products_revenue_B']
            final_ratio = start_ratio if foundry_terminal_ratio is None else foundry_terminal_ratio
            r['Foundry_profit_B'] = (start_ratio + phase * (final_ratio - start_ratio)) * r['Products_revenue_B']
        else:
            retention = .5 - .01 * min(y - 2030, 10)
            r['DCAI_profit_B'] += retention * cpu_delta + .2 * other_delta
            r['CCPG_profit_B'] += h['CCPG_margin'] * client_delta
            r['CCPG_margin'] = r['CCPG_profit_B'] / r['CCPG_revenue_B']
            r['CPU_margin'] = (r['DCAI_profit_B'] - .2 * r['Other_DCAI_B']) / r['CPU_revenue_B']
        r['DCAI_margin'] = r['DCAI_profit_B'] / r['DCAI_revenue_B']
        r['EBIT_B'] = (r['DCAI_profit_B'] + r['CCPG_profit_B'] + r['Foundry_profit_B']
                       + r['net_packaging_profit_B'] + r['Other_profit_less_corporate_B'])
        if y <= 2030:
            sales_delta = cpu_delta + client_delta + other_delta
            prior_delta = (anchor_case['Q4_2026']['net_consolidated_revenue_delta_B'] if anchor_case else 0) if y == 2027 else rows[y - 1]['revenue_delta_vs_old_B']
            r['WC_cash_use_B'] += .1 * (sales_delta - prior_delta)
            r['revenue_delta_vs_old_B'] = sales_delta
        else:
            host_growth = r['host_capital_revenue_B'] - rows[y - 1]['host_capital_revenue_B']
            r['DA_B'] = h['DA_fraction_of_Products_revenue'] * r['Products_revenue_B'] + p['incremental_DA_B']
            r['WC_cash_use_B'] = .1 * host_growth + p['incremental_WC_cash_use_B']
            investment = host_growth / capital_turnover + p['incremental_net_operating_investment_B']
            r['physical_capex_B'] = r['DA_B'] + investment - r['WC_cash_use_B']
        close_cash(r)
    return value(rows, anchor_case['Q4_2026']['opening2027_economic_cash_delta_B'] if anchor_case else 0)


def main() -> None:
    baseline = value(old_rows())
    errors = []
    for endpoint in (2026, 2030):
        expected = DATA['prior']['base_valuation_unchanged'][str(endpoint)]
        for key in ('price_USD', 'equity_B', 'explicit_operating_PV_B', 'terminal_operating_PV_B'):
            error = abs(baseline['values'][endpoint][key] - expected[key])
            errors.append(error)
            assert error < 1e-9, (endpoint, key, error)
    cases = {
        'prior_frozen': baseline,
        'accounting_completed': build_case(),
        'quarterly_delivery_only': build_case(delivery='preferred'),
        'delivery_and_other_mix': build_case(delivery='preferred', revised_other=True),
        'retained_margin_components': build_case(delivery='preferred', revised_other=True, component_margin=True),
        'preferred': build_case(delivery='preferred', revised_other=True, component_margin=True, normalized_growth=True),
        'annual_growth_control': build_case(delivery='annual_control', revised_other=True, component_margin=True, normalized_growth=True),
        'slower_delivery': build_case(delivery='slower', revised_other=True, component_margin=True, normalized_growth=True),
        'preferred_capital_turnover_060': build_case(delivery='preferred', revised_other=True, component_margin=True, normalized_growth=True, capital_turnover=.6),
        'preferred_CPU_margin35': build_case(delivery='preferred', revised_other=True, component_margin=True, normalized_growth=True, cpu_margin=.35),
        'preferred_Other_margin10': build_case(delivery='preferred', revised_other=True, component_margin=True, normalized_growth=True, other_margin=.1),
        'lost_sales_response75': build_case(delivery='preferred', revised_other=True, component_margin=True, normalized_growth=True, response=.75),
    }
    summary = []
    for name, case in cases.items():
        target = case['values'][2030]['price_USD']
        rows = case['annual_rows']
        summary.append({
            'case': name, 'planning_value_USD': case['values'][2026]['price_USD'],
            'target2030_USD': target, 'annual_price_return': (target / ENTRY) ** (1 / YEARS) - 1,
            'total_price_return': target / ENTRY - 1,
            'revenue2027_B': rows[2027]['consolidated_revenue_B'],
            'revenue2030_B': rows[2030]['consolidated_revenue_B'],
            'EBIT2030_B': rows[2030]['EBIT_B'], 'DCAI_margin2040': rows[2040].get('DCAI_margin'),
            'owner_cash2027to2030_B': sum(r['owner_cash_B'] for r in case['treasury'].values()),
            'minimum_annual_cash_B': case['minimum_annual_cash_B'],
            'requires_financing_extension': case['requires_financing_extension'],
        })
        if name == 'prior_frozen':
            assert abs(rows[2041]['parent_unlevered_cash_B'] / rows[2040]['parent_unlevered_cash_B'] - 1.03) < 1e-10
        else:
            next_ebit = rows[2041]['EBIT_B'] * 1.03
            next_host_investment = .03 * rows[2041]['host_capital_revenue_B'] / (.6 if name == 'preferred_capital_turnover_060' else .8)
            next_pack_investment = .03 * rows[2041]['net_new_packaging_B']
            next_cash = next_ebit * (1 - rows[2041]['tax_rate']) - next_host_investment - next_pack_investment - 1.03 * (rows[2041]['lease_cash_B'] + rows[2041]['minority_cash_B'])
            assert abs(next_cash / rows[2041]['parent_unlevered_cash_B'] - 1.03) < 1e-10, name
    preferred = cases['preferred']
    quarter_errors = []
    for y in range(2027, 2031):
        for quarter_key, revenue_key in [('CPU_quarterly', 'CPU_revenue_B'), ('client_quarterly', 'client_revenue_B')]:
            total = sum(r[revenue_key] for r in DATA['selected_quarters'][quarter_key] if r['year'] == y)
            quarter_errors.append(abs(total - preferred['annual_rows'][y][revenue_key]))
    assert max(quarter_errors) < 1e-9
    end = preferred['annual_rows'][2041]
    tail_metrics = {
        'terminal_growth_over_reinvestment_fraction': G / (end['net_operating_investment_B'] / end['NOPAT_B']),
        'terminal_reinvestment_fraction': end['net_operating_investment_B'] / end['NOPAT_B'],
        'after2040_share_operating_value': preferred['values'][2026]['terminal_operating_PV_B'] / preferred['values'][2026]['total_operating_value_B'],
        'after2030_share_operating_value': (preferred['values'][2030]['total_operating_value_B'] / (1 + R) ** 4) / preferred['values'][2026]['total_operating_value_B'],
        'scope': 'Implied incremental economics, not measured historical or total-company ROIC.',
    }
    result = {
        'computed_utc': datetime.now(timezone.utc).isoformat(),
        'input_files': {k: {'path': str(p), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for k, p in FILES.items()},
        'parameters': {'rate': R, 'g': G, 'shares_B': SHARES, 'entry_USD': ENTRY, 'holding_years': YEARS, 'net_other_assets_B': NET_OTHER},
        'prior_reconciliation': {'comparisons': len(errors), 'maximum_error': max(errors)},
        'selected_quarter_reconciliation': {'comparisons': len(quarter_errors), 'maximum_error': max(quarter_errors)},
        'summary': summary, 'cases': cases, 'terminal_metrics': tail_metrics,
        'decision_hurdles': [
            {'chosen_annual_return': h, 'entry_ceiling_USD': preferred['values'][2030]['price_USD'] / (1 + h) ** YEARS}
            for h in (.08, .10, .12, .15)
        ],
        'forecast_comparison': {'SP_consensus2027_revenue_B': 69.27, 'preferred_difference_B': preferred['annual_rows'][2027]['consolidated_revenue_B'] - 69.27, 'preferred_difference_pct': preferred['annual_rows'][2027]['consolidated_revenue_B'] / 69.27 - 1, 'scope': 'Published company revenue proxy, not a CPU consensus or uniquely price-implied expectation.'},
        'limits': ['Future forecasts are owned assumptions, not verified outcomes.', 'Cases are unweighted diagnostics, not confidence bounds.', 'Annual liquidity is not a quarterly or daily funding proof; separate quarterly schedule required.', 'Frozen prior revenue was a capital denominator, not fully consolidated sales.'],
    }
    (OUT / 'integrated_results.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: result[k] for k in ('prior_reconciliation', 'summary', 'terminal_metrics', 'decision_hurdles', 'forecast_comparison')}, indent=2))


if __name__ == '__main__':
    main()

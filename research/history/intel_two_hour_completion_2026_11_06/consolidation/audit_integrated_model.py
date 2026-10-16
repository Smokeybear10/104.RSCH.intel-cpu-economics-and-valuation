from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import math

OUT = Path(__file__).resolve().parent
RUN = OUT.parent
BASE = RUN.parent
RESULT_PATH = RUN / 'root/integrated_results.json'
RESULT = json.loads(RESULT_PATH.read_text())
FILES = {name: Path(info['path']) for name, info in RESULT['input_files'].items()}
FILES.update({
    'finance': BASE / 'intel_competition_screen_2026_11_04/financial_claims_and_treasury_policy_2026_11_04.json',
    'corporate': BASE / 'intel_competition_screen_2026_11_04/corporate_other_policy.json',
    'grant': OUT / 'mobileye_grant_cohort_diagnostic.json',
    'consolidation': OUT / 'completed_revenue_bridge.json',
    'treasury_calendar': OUT / 'quarterly_treasury_calendar.json',
})
HASHES = {name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in FILES.items()}
DATA = {name: json.loads(path.read_text()) for name, path in FILES.items()}
STALE = [name for name, item in RESULT['input_files'].items() if HASHES[name] != item['sha256']]
H = {row['year']: row for row in DATA['host']['annual_rows']}
RAW = {row['year']: row for row in DATA['raw']['annual_operating_rows']}
PACK = {row['year']: row for row in DATA['pack']['annual_rows']}
CORP = {row['year']: row for row in DATA['corporate']['policy_rows']}
FIN = DATA['finance']
F = FIN['treasury_2027_2030']
M = DATA['margin']['preferred']
PARAMETERS = RESULT['parameters']


def forward_sales(delivery: str, revised_other: bool, normalized: bool) -> dict:
    source_case = 'preferred' if delivery == 'annual_control' else delivery
    cpu = {row['year']: row['CPU_revenue_B'] for row in DATA['cpu']['cases'].get(source_case, {}).get('annual_2027_2030', [])}
    client = {row['year']: row['client_revenue_B'] for row in DATA['client']['cases'].get(source_case, {}).get('annual_2027_2030', [])}
    if delivery == 'preferred' and 'selected_quarters' in DATA:
        cpu = {y: math.fsum(r['CPU_revenue_B'] for r in DATA['selected_quarters']['CPU_quarterly'] if r['year'] == y) for y in range(2027, 2031)}
        client = {y: math.fsum(r['client_revenue_B'] for r in DATA['selected_quarters']['client_quarterly'] if r['year'] == y) for y in range(2027, 2031)}
    rows = {}
    for year in range(2027, 2042):
        h = H[year]
        if delivery == 'old':
            server, pc = h['server_CPU_revenue_proxy_B'], h['client_revenue_B']
        elif year <= 2030:
            server, pc = cpu[year], client[year]
        else:
            server_factor = 1.03 if year == 2041 else 1.0404 if normalized else (1 + h['server_unit_growth']) * (1 + h['server_ASP_growth'])
            server = rows[year - 1]['CPU_revenue_B'] * server_factor
            pc = rows[year - 1]['client_revenue_B'] * (1 + h['client_unit_growth']) * (1 + h['client_ASP_growth'])
        if revised_other:
            previous_other = M['Other_DCAI_2026_revenue_B'] if year == 2027 else rows[year - 1]['Other_DCAI_B']
            growth = M['Other_DCAI_growth_2027_2030'][year - 2027] if year <= 2030 else h['Other_DCAI_growth']
            other = previous_other * (1 + growth)
        else:
            other = h['Other_DCAI_revenue_B']
        rows[year] = {'CPU_revenue_B': server, 'client_revenue_B': pc, 'Other_DCAI_B': other,
                      'DCAI_revenue_B': server + other, 'CCPG_revenue_B': pc + h['Other_CCPG_revenue_B']}
        rows[year]['Products_revenue_B'] = rows[year]['DCAI_revenue_B'] + rows[year]['CCPG_revenue_B']
    return rows


def independently_build(config: dict) -> dict:
    delivery = config.get('delivery', 'old')
    sales = forward_sales(delivery, config.get('other', False), config.get('normalized', False))
    rows = {}
    last_delta = 0.
    for year, revenue in sales.items():
        h, raw, pack = H[year], RAW[year], PACK[year]
        phase = min(max((year - 2030) / 10, 0), 1)
        dcai = h['DCAI_operating_profit_B'] + .08 * phase * h['DCAI_revenue_B']
        ccpg = h['CCPG_operating_profit_B']
        foundry = h['Foundry_operating_profit_B']
        delta_cpu = revenue['CPU_revenue_B'] - h['server_CPU_revenue_proxy_B']
        delta_pc = revenue['client_revenue_B'] - h['client_revenue_B']
        delta_other = revenue['Other_DCAI_B'] - h['Other_DCAI_revenue_B']
        if year <= 2030:
            dcai += config.get('response', .5) * delta_cpu + .2 * delta_other
            ccpg += config.get('response', .5) * delta_pc
        elif config.get('components', False):
            start = rows[2030]
            initial_cpu_margin = (start['DCAI_profit_B'] - .2 * start['Other_DCAI_B']) / start['CPU_revenue_B']
            final_cpu_margin = config.get('cpu_margin', (7.055 - .2 * 3.3) / (18.632 - 3.3))
            cpu_margin = initial_cpu_margin * (1 - phase) + final_cpu_margin * phase
            other_margin = .2 * (1 - phase) + config.get('other_margin', .2) * phase
            dcai = revenue['CPU_revenue_B'] * cpu_margin + revenue['Other_DCAI_B'] * other_margin
            initial_pc_margin = start['CCPG_profit_B'] / start['CCPG_revenue_B']
            ccpg = revenue['CCPG_revenue_B'] * (initial_pc_margin * (1 - phase) + .28 * phase)
            foundry = start['Foundry_profit_B'] / start['Products_revenue_B'] * revenue['Products_revenue_B']
        else:
            dcai += (.5 - .01 * min(year - 2030, 10)) * delta_cpu + .2 * delta_other
            ccpg += h['CCPG_margin'] * delta_pc
        corporate_net = CORP[year]['other_segment_operating_profit_B'] - CORP[year]['corporate_total_expense_B'] if year <= 2030 else (.7 - 5.15) * 1.03 ** (year - 2030)
        ebit = dcai + ccpg + foundry + corporate_net + pack['net_incremental_operating_profit_B']
        correction = (.934 - .020) * 1.03 ** max(year - 2030, 0) + pack['existing_embedded_packaging_revenue_allowance_B']
        complete = not config.get('frozen', False)
        consolidated = revenue['Products_revenue_B'] + h['root_Other_revenue_for_capital_denominator_B'] + pack['incremental_external_packaging_revenue_B'] + (correction if complete else 0)
        host_sales = consolidated - pack['incremental_external_packaging_revenue_B']
        capex, depreciation, wc = raw['physical_cash_capex_B'], raw['DA_B'], raw['WC_cash_use_B']
        if year <= 2030:
            total_delta = delta_cpu + delta_pc + delta_other
            wc += .1 * (total_delta - last_delta)
            last_delta = total_delta
        elif complete:
            host_growth = host_sales - rows[year - 1]['host_capital_revenue_B']
            investment = host_growth / config.get('turnover', .8) + pack['incremental_net_operating_investment_B']
            depreciation = h['DA_fraction_of_Products_revenue'] * revenue['Products_revenue_B'] + pack['incremental_DA_B']
            wc = host_growth / 10 + pack['incremental_WC_cash_use_B']
            capex = investment + depreciation - wc
        tax = max(ebit, 0) * raw['tax_rate']
        net_investment = capex - depreciation + wc
        cash = ebit - tax - net_investment - raw['lease_cash_B'] - raw['minority_cash_B'] + raw['old_credit_collection_B'] + raw['new_credit_collection_B'] - raw['credit_basis_loss_tax_B']
        end_debt = FIN['opening_2027_forecast']['opening_debt_B'] - sum(F['scheduled_principal_B'])
        ordinary_interest = F['ordinary_cash_interest_B'][year - 2027] if year <= 2030 else .052 * end_debt - 1
        capital_deduction = min(max(year - 2027, 0), 8) / 8
        shield = raw['tax_rate'] * (ordinary_interest + capital_deduction)
        assert 0 <= shield <= tax
        rows[year] = {**revenue, 'host_capital_revenue_B': host_sales, 'consolidated_revenue_B': consolidated,
                      'DCAI_profit_B': dcai, 'CCPG_profit_B': ccpg, 'Foundry_profit_B': foundry,
                      'Other_profit_less_corporate_B': corporate_net, 'EBIT_B': ebit, 'ordinary_operating_tax_B': tax,
                      'DA_B': depreciation, 'physical_capex_B': capex, 'WC_cash_use_B': wc,
                      'net_operating_investment_B': net_investment, 'parent_unlevered_cash_B': cash,
                      'financing_shield_B': shield}
    return rows


def independently_value(rows: dict) -> tuple[dict, dict]:
    cash = FIN['opening_2027_forecast']['opening_liquid_assets_B']
    debt = FIN['opening_2027_forecast']['opening_debt_B']
    treasury = {}
    for index, year in enumerate(range(2027, 2031)):
        owner_cash = rows[year]['parent_unlevered_cash_B'] - F['ordinary_cash_interest_B'][index] - F['capitalized_cash_interest_inside_total_PPE_B'][index] + F['cash_interest_income_B'][index] * (1 - RAW[year]['tax_rate']) + rows[year]['financing_shield_B']
        cash += owner_cash + F['government_escrow_cash_B'][index] - F['Classiq_cash_B'][index] - F['scheduled_principal_B'][index]
        debt -= F['scheduled_principal_B'][index]
        treasury[year] = {'owner_cash_B': owner_cash, 'ending_cash_B': cash, 'ending_debt_B': debt}
    values = {}
    r = PARAMETERS['rate']
    for endpoint in (2026, 2030):
        operating = math.fsum(rows[y]['parent_unlevered_cash_B'] / (1 + r) ** (y - endpoint) for y in range(endpoint + 1, 2041))
        terminal = rows[2041]['parent_unlevered_cash_B'] / (r - .03) / (1 + r) ** (2040 - endpoint)
        shields = math.fsum(rows[y]['financing_shield_B'] / (1 + r) ** (y - endpoint) for y in range(endpoint + 1, 2041))
        shields += rows[2041]['financing_shield_B'] / r / (1 + r) ** (2040 - endpoint)
        escrow = sum(F['government_escrow_cash_B'][y - 2027] / (1 + r) ** (y - endpoint) for y in range(max(2027, endpoint + 1), 2031))
        acquisition = sum(F['Classiq_cash_B'][y - 2027] / (1 + r) ** (y - endpoint) for y in range(max(2027, endpoint + 1), 2031))
        cash_value = FIN['opening_2027_forecast']['opening_liquid_assets_B'] if endpoint == 2026 else treasury[2030]['ending_cash_B']
        debt_value = FIN['opening_2027_forecast']['opening_debt_B'] if endpoint == 2026 else treasury[2030]['ending_debt_B']
        net_other = FIN['other_assets_and_claims']['net_other_assets_B'] - DATA['prior']['base_valuation_unchanged']['2026']['added_claim_reserve_B']
        equity = operating + terminal + shields + cash_value - debt_value + net_other + escrow - acquisition
        values[endpoint] = {'explicit_operating_PV_B': operating, 'terminal_operating_PV_B': terminal,
                            'financing_shield_PV_B': shields, 'equity_B': equity,
                            'price_USD': equity / FIN['shares']['root_selected_economic_claims_B']}
    return values, treasury


CONFIGS = {
    'prior_frozen': {'frozen': True},
    'accounting_completed': {},
    'quarterly_delivery_only': {'delivery': 'preferred'},
    'delivery_and_other_mix': {'delivery': 'preferred', 'other': True},
    'retained_margin_components': {'delivery': 'preferred', 'other': True, 'components': True},
    'preferred': {'delivery': 'preferred', 'other': True, 'components': True, 'normalized': True},
    'annual_growth_control': {'delivery': 'annual_control', 'other': True, 'components': True, 'normalized': True},
    'slower_delivery': {'delivery': 'slower', 'other': True, 'components': True, 'normalized': True},
    'preferred_capital_turnover_060': {'delivery': 'preferred', 'other': True, 'components': True, 'normalized': True, 'turnover': .6},
    'preferred_CPU_margin35': {'delivery': 'preferred', 'other': True, 'components': True, 'normalized': True, 'cpu_margin': .35},
    'preferred_Other_margin10': {'delivery': 'preferred', 'other': True, 'components': True, 'normalized': True, 'other_margin': .1},
    'lost_sales_response75': {'delivery': 'preferred', 'other': True, 'components': True, 'normalized': True, 'response': .75},
}
comparisons, errors = [], []
for name, config in CONFIGS.items():
    if name not in RESULT['cases']:
        continue
    rows = independently_build(config)
    values, treasury = independently_value(rows)
    expected = RESULT['cases'][name]
    case_errors = []
    for year, row in rows.items():
        for field, value in row.items():
            if field in expected['annual_rows'][str(year)]:
                case_errors.append(abs(value - expected['annual_rows'][str(year)][field]))
    for endpoint, value in values.items():
        for field, number in value.items():
            case_errors.append(abs(number - expected['values'][str(endpoint)][field]))
    for year, row in treasury.items():
        for field, value in row.items():
            case_errors.append(abs(value - expected['treasury'][str(year)][field]))
    comparisons.append({'case': name, 'numeric_comparisons': len(case_errors), 'max_absolute_error': max(case_errors),
                        'independent_planning_value_USD': values[2026]['price_USD'], 'independent_target_USD': values[2030]['price_USD'],
                        'independent_minimum_annual_economic_cash_B': min(r['ending_cash_B'] for r in treasury.values())})
    errors.extend(case_errors)

result = {
    'audited_utc': datetime.now(timezone.utc).isoformat(),
    'root_output_computed_utc': RESULT['computed_utc'],
    'root_output_sha256': hashlib.sha256(RESULT_PATH.read_bytes()).hexdigest(),
    'method': 'Separate implementation from selected source data; no import or execution of root engine functions. Corporate expense is reconstructed from corporate policy, tax shields from financing policy and the capitalized-interest deduction convention, claims from treasury policy and prior claim reserve. All annual cash and APV values are recalculated.',
    'source_hashes': HASHES,
    'root_source_hash_mismatches': STALE,
    'case_comparisons': comparisons,
    'max_absolute_error': max(errors),
    'all_compared_values_match': max(errors) < 1e-9,
    'unreviewed_cases': sorted(set(RESULT['cases']) - set(CONFIGS)),
    'accounting_conclusions': [
        'Consolidation includes Products, net All Other, legacy external Foundry and gross new packaging once. Shadow and net packaging are not both added on top of gross sales.',
        'Existing external services receive no new EBIT. Corporate economic SBC is included once. No second standalone Mobileye SBC deduction appears.',
        'After 2030, host growth is funded at the selected turnover including working capital, and net incremental packaging is funded separately. D&A is added once and offsets the maintenance component in capex.',
        'Finite capex and D&A remain unchanged after delivery revisions; working-capital corrections use changes in the annual revenue delta, avoiding repeated deductions of the same stock.',
        'Grant receivable changes remain inside aggregate operating-capital cash use; there is no extra grant income, capital-tax collection or duplicate asset addition.',
        'Ordinary and capitalized financing interest are excluded from unlevered operations and deducted once in finite treasury. Debt, escrow shares, acquisition cash and the 1.215B extra claim reserve are not duplicated.',
    ],
    'limits': [
        'A consistent cash-flow model is not a complete linked income statement, balance sheet and cash-flow forecast. It does not independently validate capacity, capex sufficiency, future margins, grant eligibility or future receivable recovery.',
        'Quarterly treasury calendar is complete as a separate input. Root still needs to integrate operating timing and inspect interim economic liquidity; calendar-year aggregate totals cannot prove intrayear access.',
        'Preferred CPU and client revenue were reconstructed by summing selected quarterly rows, independently of the annual rows consumed by the root engine. The earlier unused-quarter-input issue is resolved in this version.',
        'The integration policy had a manually estimated timestamp inconsistent with calculation time. Its correction retains the erroneous value and separately records filesystem evidence; exact selection time is not claimed.',
    ],
    'verification': {'frozen_sources_unchanged_during_audit': all(hashlib.sha256(p.read_bytes()).hexdigest() == HASHES[name] for name, p in FILES.items())},
}
(OUT / 'independent_integrated_audit.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps({k: result[k] for k in ('root_output_computed_utc', 'root_source_hash_mismatches', 'case_comparisons', 'max_absolute_error', 'all_compared_values_match', 'unreviewed_cases', 'verification')}, indent=2))

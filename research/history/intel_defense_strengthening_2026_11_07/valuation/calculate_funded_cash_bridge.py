import copy
import hashlib
import importlib.util
import json
import math
import sys
from datetime import date, datetime, timezone
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path('/Users/thomasou/Documents/Codex/2026-11-02/lo')
RESEARCH = ROOT / 'work/three_hour/active_research'
OUT = Path(__file__).resolve().parent
SHARES, RATE = 5.51, .11555
HORIZON = (date(2030, 12, 31) - date(2026, 11, 6)).days / 365.25
PATHS = {
    'active': RESEARCH / 'intel_market_share_thesis_2026_11_06/root/active_case.json',
    'delivery': RESEARCH / 'intel_weakness_repair_2026_11_06/valuation/calculate_delivery_joint.py',
    'quarterly': RESEARCH / 'intel_weakness_repair_2026_11_06/valuation/calculate_quarterly_overlay.py',
    'funding': RESEARCH / 'intel_valuation_resolution_2026_11_06/claims/calculate_claims_and_funding.py',
    'funding_policy': RESEARCH / 'intel_valuation_resolution_2026_11_06/claims/policy_before_calculation.json',
    'quarterly_source': RESEARCH / 'intel_market_share_thesis_2026_11_06/root/owned_quarterly_cash_results.json',
    'quarterly_policy': RESEARCH / 'intel_two_hour_completion_2026_11_06/root/quarterly_cash_policy_before_calculation.json',
    'prior_funding_results': RESEARCH / 'intel_valuation_resolution_2026_11_06/claims/claims_and_funding_results.json',
    'CPU_delay': RESEARCH / 'intel_weakness_repair_2026_11_06/cpu/cpu_ramp_results.json',
    'prior_adversarial': RESEARCH / 'intel_adversarial_review_2026_11_06/valuation/decision_recheck_results.json',
}


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


sys.path.insert(0, str(PATHS['delivery'].parent))
delivery = load_module('delivery', PATHS['delivery'])
quarterly = load_module('quarterly', PATHS['quarterly'])
funding = load_module('funding', PATHS['funding'])
ACTIVE = json.loads(PATHS['active'].read_text())
BASE = {int(y): r for y, r in ACTIVE['annual_rows'].items()}
TREASURY = {int(y): r for y, r in ACTIVE['treasury'].items()}
CPU = json.loads(PATHS['CPU_delay'].read_text())['delay_no_catchup']


def close_cash(row: dict) -> None:
    row['ordinary_operating_tax_B'] = max(row['EBIT_B'], 0) * row['tax_rate']
    row['NOPAT_B'] = row['EBIT_B'] - row['ordinary_operating_tax_B']
    row['net_operating_investment_B'] = row['physical_capex_B'] - row['DA_B'] + row['WC_cash_use_B']
    row['parent_unlevered_cash_B'] = (row['NOPAT_B'] - row['net_operating_investment_B']
        - row['lease_cash_B'] - row['minority_cash_B'] + row['old_credit_collection_B']
        + row['new_credit_collection_B'] - row['credit_basis_loss_tax_B'])


def joint(rows: dict, capital060: bool = False) -> dict:
    rows = copy.deepcopy(rows)
    for y, row in rows.items():
        profit = {2027: -4, 2028: -2.5, 2029: -1}.get(y, 0)
        row['EBIT_B'] += profit - row['Foundry_profit_B']
        row['Foundry_profit_B'] = profit
        close_cash(row)
        if capital060 and 2031 <= y <= 2040:
            sales_change = row['host_capital_revenue_B'] - rows[y - 1]['host_capital_revenue_B']
            row['physical_capex_B'] += sales_change * (1 / .6 - 1 / .8)
            close_cash(row)
    row = rows[2041]
    row['physical_capex_B'] += .03 * row['NOPAT_B'] / .15 - row['net_operating_investment_B']
    close_cash(row)
    return rows


def apv(rows: dict, rate: float) -> dict:
    explicit = math.fsum(rows[y]['parent_unlevered_cash_B'] / (1 + rate) ** (y - 2030)
                         for y in range(2031, 2041))
    terminal = rows[2041]['parent_unlevered_cash_B'] / (rate - .03) / (1 + rate) ** 10
    shield = math.fsum(rows[y]['financing_shield_B'] / (1 + rate) ** (y - 2030) for y in range(2031, 2041))
    shield += rows[2041]['financing_shield_B'] / rate / (1 + rate) ** 10
    cash = ACTIVE['values']['2030']['cash_B'] + math.fsum(rows[y]['parent_unlevered_cash_B'] - BASE[y]['parent_unlevered_cash_B'] for y in range(2027, 2031))
    equity = explicit + terminal + shield + cash - ACTIVE['values']['2030']['debt_B'] + 4.502
    return {'explicit_operating_PV_B': explicit, 'terminal_operating_PV_B': terminal,
            'financing_shield_PV_B': shield, 'cash_B_before_new_funding': cash,
            'debt_B_before_new_funding': ACTIVE['values']['2030']['debt_B'],
            'net_other_assets_B': 4.502, 'equity_B_before_new_funding': equity,
            'target_USD_before_new_funding': equity / SHARES}


def cash_bridge(row: dict) -> dict:
    net_credits = row['old_credit_collection_B'] + row['new_credit_collection_B'] - row['credit_basis_loss_tax_B']
    normalized = row['parent_unlevered_cash_B'] - net_credits
    return {'EBIT_B': row['EBIT_B'], 'ordinary_operating_tax_B': row['ordinary_operating_tax_B'],
            'NOPAT_B': row['NOPAT_B'], 'physical_capex_B': row['physical_capex_B'], 'DA_B': row['DA_B'],
            'WC_cash_use_B': row['WC_cash_use_B'], 'net_operating_investment_B': row['net_operating_investment_B'],
            'lease_and_minority_cash_B': row['lease_cash_B'] + row['minority_cash_B'],
            'normalized_parent_operating_cash_B': normalized, 'net_finite_credits_B': net_credits,
            'parent_unlevered_cash_B': row['parent_unlevered_cash_B']}


delayed = delivery.delivery_rows({int(y): v for y, v in CPU['annual_CPU_B'].items()})
cases = {'core': BASE, 'selected_joint': joint(BASE), 'joint_plus_CPU_delay': joint(delayed),
         'joint_plus_CPU_delay_plus_2031_2040_capital060': joint(delayed, True)}
prior = json.loads(PATHS['prior_adversarial'].read_text())
assert abs(apv(BASE, .10625)['target_USD_before_new_funding'] - 82.47015162680005) < 1e-10
assert abs(apv(cases['joint_plus_CPU_delay'], RATE)['target_USD_before_new_funding'] - prior['business_news_test']['selected_joint_plus_existing_CPU_delay_before_funding_cost']['target_USD']) < 1e-10

results = {}
for name, rows in cases.items():
    no_funding = apv(rows, RATE)
    quarters = quarterly.build(rows, 'concentrated_timing_stress', name.startswith('joint_plus_CPU'))
    financed = funding.funded_case(quarters['quarterly_rows'], .08, 0)
    target = no_funding['target_USD_before_new_funding'] + financed['Dec2030_per_share_delta_USD']
    cash_sums = {k: math.fsum(cash_bridge(rows[y])[k] for y in range(2027,2031)) for k in cash_bridge(rows[2027])}
    results[name] = {
        'APV_at11_555pct': no_funding,
        'funded_target_USD': target,
        'funded_annual_return_at40': (target / 40) ** (1 / HORIZON) - 1,
        'funded_annual_return_at56_28': (target / 56.28) ** (1 / HORIZON) - 1,
        'diagnostic_entry12_not_adopted_USD': target / 1.12 ** HORIZON,
        'cash_bridge': {str(y): cash_bridge(rows[y]) for y in (2027, 2028, 2029, 2030, 2031, 2040, 2041)},
        'cumulative_2027_2030_cash_bridge': cash_sums,
        'cash2030_after_new_funding_B': no_funding['cash_B_before_new_funding'] + financed['Dec2030_equity_value_delta_B'],
        'operating_quarter_cash_before_funding': {k: v for k, v in quarters.items() if k != 'quarterly_rows'},
        'funding': financed,
        '2031_2040_net_investment_B': math.fsum(rows[y]['net_operating_investment_B'] for y in range(2031,2041))
    }

assert results['joint_plus_CPU_delay']['funding'] == results['joint_plus_CPU_delay_plus_2031_2040_capital060']['funding']
assert abs(results['selected_joint']['funded_target_USD'] - prior['selected_funded_joint']['target_USD']) < 1e-10
bridge_errors = [abs(r['NOPAT_B'] - r['net_operating_investment_B'] - r['lease_and_minority_cash_B'] - r['normalized_parent_operating_cash_B']) for c in results.values() for r in c['cash_bridge'].values()]
assert max(bridge_errors) < 1e-10

output = {'computed_utc': datetime.now(timezone.utc).isoformat(), 'input_files': {k: {'path': str(p), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for k,p in PATHS.items()},
          'scope': 'One combined downside control and conditional financing overlay. No new central forecast, hurdle, or adopted entry. Reuses checked quarterly timing/funding code; independently recomputes combined annual cash and APV.',
          'horizon_years': HORIZON, 'cases': results,
          'new_triple_case_assumptions': [
              'Existing one-quarter CPU delay causes8.044835% persistent revenue-level loss; existing growth path remains.',
              'Foundry profit is-4/-2.5/-1/0B in2027–30 and zero afterward. Near-term physical capex124.5B retained.',
              'Host incremental sales/net-investment0.6 in2031–40 only; applies to the lower delayed revenue path, not unchanged core revenue.',
              'Terminal2041 net investment=3%*changed NOPAT/15%; terminal cash unchanged versus CPUdelay/factory joint.',
              'Operating rate11.555%,3%terminalgrowth,5.51Bshares. All baseline named claims and cash-income conventions retained.',
              'Concentrated inherited quarter timing,20Bquarter-endbuffer,8%borrowrate,no immediate taxbenefit. Full-quarter interest on newdraws; repay excess cash before accumulating more cash.',
          ],
          'checks': {'bridge_max_error_B': max(bridge_errors), 'selected_funded_joint_reproduced': True, 'new_triple_case_has_same_pre2031_funding_as_joint_CPU': True, 'annual_quarter_reconciliation_max_error_B': max(v['operating_quarter_cash_before_funding']['annual_reconciliation_max_error_B'] for v in results.values())},
          'limitations': ['Future credit-facility access and pricing are conditional;fees unmodeled. No daily-liquidity conclusion.',
                         'Parent operating cash includes reserves for leases and minorities but no instrument-level refresh of those economic assumptions.',
                         'Reinvestment control is a sensitivity, not evidence0.6 is the true capital ratio. No scenario probability assigned.',
                         'Funding restores liquidity, not lost economic value. All new equity effects are net of matching debt; no borrowing-proceeds uplift.',
                         'Forecast cash bridges are not observed earnings or cash. Reported CPU mix and cost improvement support a mechanism, not durable2031–2041returns.']}
(OUT/'funded_cash_bridge_results.json').write_text(json.dumps(output,indent=2)+'\n')
print(json.dumps({k:{'target':v['funded_target_USD'],'return40':v['funded_annual_return_at40'],'entry12':v['diagnostic_entry12_not_adopted_USD'],'minimum_cash_unfunded':v['operating_quarter_cash_before_funding']['minimum_quarter_cash_B'],'peak_draw':v['funding']['peak_revolver_B'],'interest_B':v['funding']['total_gross_interest_B'],'repaid':v['funding']['fully_repaid_period'],'cash2030_B':v['cash2030_after_new_funding_B'],'cashbridge2030':v['cash_bridge']['2030']} for k,v in results.items()},indent=2))

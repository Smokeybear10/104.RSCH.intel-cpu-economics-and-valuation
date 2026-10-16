import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


OUT = Path(__file__).resolve().parent
RESEARCH = OUT.parents[1]
policy_path = OUT / 'explicit_claims_overlay_policy.json'
policy = json.loads(policy_path.read_text())
reserve = policy['claims_B']['total_additional_reserve']
ns = {'__file__': str(OUT / 'extended_scenarios.py')}
exec((OUT / 'extended_scenarios.py').read_text().split('\ncases = ')[0], ns)
shares, entry, years = ns['SHARES'], ns['ENTRY'], ns['YEARS']
deduction = reserve / shares
old_other_assets = ns['OTHER_ASSETS']
ns['OTHER_ASSETS'] -= reserve
value, close_cash = ns['value'], ns['close_cash']
extended = json.loads((OUT / 'extended_scenario_results.json').read_text())
reconstruction = json.loads((OUT / 'reconstruction_results.json').read_text())
paired_path = RESEARCH / 'intel_benchmark_rebuild_2026_11_05/return_value_bridge.json'
paired = json.loads(paired_path.read_text())['paired_scenarios']
source_files = [policy_path, OUT / 'extended_scenarios.py', OUT / 'extended_scenario_results.json', OUT / 'reconstruction_results.json', paired_path]
cases, checks = {}, []


def adjusted_summary(planning: float, target: float) -> dict:
    new_planning, new_target = planning - deduction, target - deduction
    return {
        'before_Dec2026_planning_value_USD': planning,
        'before_Dec2030_target_USD': target,
        'December2026_planning_value_USD': new_planning,
        'December2030_target_USD': new_target,
        'annual_price_return_from52_22': (new_target / entry) ** (1 / years) - 1,
        'total_price_return_from52_22': new_target / entry - 1,
        'planning_value_change_from52_22': new_planning / entry - 1,
        'per_share_claim_deduction_USD': deduction,
    }


def add_full_case(name: str, original: dict) -> None:
    rows = {int(y): row for y, row in original['rows'].items()}
    revised = value(copy.deepcopy(rows))
    summary = adjusted_summary(original['values']['2026']['price_USD'], original['values']['2030']['price_USD'])
    for endpoint, field in [(2026, 'December2026_planning_value_USD'), (2030, 'December2030_target_USD')]:
        error = revised['values'][endpoint]['price_USD'] - summary[field]
        checks.append(error)
        assert abs(error) < 1e-10
        for unchanged in ['explicit_operating_PV_B', 'terminal_operating_PV_B', 'financing_shield_PV_B', 'economic_cash_B', 'ordinary_debt_B']:
            if unchanged in original['values'][str(endpoint)]:
                assert abs(revised['values'][endpoint][unchanged] - original['values'][str(endpoint)][unchanged]) < 1e-10
    cases[name] = {'summary': summary, 'values': revised['values'], 'minimum_economic_cash_before_named_claim_payment_B': min(r['ending_economic_cash_B'] for r in revised['treasury'].values()), 'method': 'Independent APV recalculation with only net other assets reduced.'}


for name, original in extended['cases'].items():
    add_full_case(name, original)
for name, original in reconstruction['diagnostic_cases'].items():
    add_full_case(name, original)
for name, original in zip(['joint_downside', 'persistent_lower_CPU_demand', 'mature_only_margin35', 'paired_base_crosscheck', 'favorable_maturing_risk'], paired):
    cases[name] = {'summary': adjusted_summary(original['December2026_planning_value_USD'], original['December2030_target_USD']), 'method': 'Explicit endpoint claims subtraction from authoritative paired scenario; operations, cash and risk path unchanged.'}
weak_path = RESEARCH / 'intel_hour_verification_2026_11_04/weak_demand_results.json'
joint_path = RESEARCH / 'intel_directional_build_2026_11_05/joint_downside_results.json'
source_files.extend([weak_path, joint_path])
weak_minimum = json.loads(weak_path.read_text())['checks']['minimum_ending_cash_through2030_B']
joint_minimum = json.loads(joint_path.read_text())['checks']['minimum_2027_2030_economic_cash_B']
for name, minimum in [('persistent_lower_CPU_demand', weak_minimum), ('joint_downside', joint_minimum)]:
    cases[name]['minimum_economic_cash_before_named_claim_payment_B'] = minimum
    cases[name]['minimum_annual_cash_less_full_claim_reserve_B'] = minimum - reserve
    assert minimum - reserve > 20

other_path = OUT / 'other_DCAI_scenario_results.json'
source_files.append(other_path)
for name, assumptions in json.loads(other_path.read_text())['results'].items():
    for retention, original in assumptions.items():
        full = {'rows': original['cash_rows'], 'values': original['values']}
        add_full_case(f'{name}_retention{retention}', full)


def margin_value(path_name: str, productivity: float, margin: float, endpoint: int = 2026) -> float:
    rows = {int(y): copy.deepcopy(row) for y, row in extended['cases'][path_name]['rows'].items()}
    for year, row in rows.items():
        if year < 2031:
            continue
        current_sales = ns['host'][year]['consolidated_external_revenue_for_capital_denominator_B'] + row['CPU_revenue_delta_B']
        prior_sales = ns['host'][year - 1]['consolidated_external_revenue_for_capital_denominator_B'] + rows[year - 1]['CPU_revenue_delta_B']
        investment_change = (current_sales - prior_sales) * (1 / productivity - 1 / .8)
        row['net_operating_investment_B'] += investment_change
        row['physical_capex_B'] += investment_change
        margin_change = (margin - .4) * min((year - 2030) / 10, 1)
        row['EBIT_B'] += margin_change * row['DCAI_revenue_B']
        row['DCAI_product_margin'] += margin_change
        close_cash(row)
    return value(rows)['values'][endpoint]['price_USD']


def solve_margin(path_name: str, productivity: float, desired: float, endpoint: int = 2026) -> float:
    low, high = .2, .7
    assert margin_value(path_name, productivity, low, endpoint) < desired < margin_value(path_name, productivity, high, endpoint)
    for _ in range(80):
        mid = (low + high) / 2
        if margin_value(path_name, productivity, mid, endpoint) < desired:
            low = mid
        else:
            high = mid
    return (low + high) / 2


reverse_roots = []
for path_name in ['base', 'CPU_growth_normalizes_2031']:
    for productivity in [.6, .8, 1.0]:
        root = solve_margin(path_name, productivity, entry)
        reverse_roots.append({'CPU_path': path_name, 'host_capital_productivity': productivity, 'mature_DCAI_margin_matching52_22_Dec2026_planning_value': root, 'value_at_root_USD': margin_value(path_name, productivity, root), 'planning_value_at40percent_margin_USD': margin_value(path_name, productivity, .4)})

base_target = cases['base']['summary']['December2030_target_USD']
entry_ceilings = []
for hurdle in [.08, .10, .12, .15]:
    required_target = entry * (1 + hurdle) ** years
    required_margin = solve_margin('base', .8, required_target, 2030)
    entry_ceilings.append({'chosen_annual_price_return': hurdle, 'maximum_entry_with_base_target_USD': base_target / (1 + hurdle) ** years, 'required2030_target_at52_22_USD': required_target, 'conditional_mature_DCAI_margin_for_required_target': required_margin, 'target_reconstruction_error_USD': margin_value('base', .8, required_margin, 2030) - required_target})

apv = {}
for endpoint, values in cases['base']['values'].items():
    operating = values['explicit_operating_PV_B'] + values['terminal_operating_PV_B']
    apv[endpoint] = {**values, 'total_operating_value_B': operating, 'net_financial_claims_and_tax_benefit_B': values['equity_B'] - operating, 'net_other_assets_after_added_claims_B': ns['OTHER_ASSETS'], 'added_claim_reserve_B': reserve}

base_rows = copy.deepcopy(ns['base_rows'])
selected_rate = ns['RATE']
low, high = .08, .16
for _ in range(80):
    mid = (low + high) / 2
    ns['RATE'] = mid
    if value(base_rows)['values'][2026]['price_USD'] > entry:
        low = mid
    else:
        high = mid
implied_rate = (low + high) / 2
ns['RATE'] = implied_rate
rate_values = value(base_rows)['values']
ns['RATE'] = selected_rate

output = {
    'computed_utc': datetime.now(timezone.utc).isoformat(),
    'policy_sha256': hashlib.sha256(policy_path.read_bytes()).hexdigest(),
    'input_sha256': {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in source_files},
    'policy': policy,
    'additional_reserve_B': reserve,
    'shares_B': shares,
    'per_share_claim_deduction_USD': deduction,
    'net_other_assets_before_B': old_other_assets,
    'net_other_assets_after_B': ns['OTHER_ASSETS'],
    'holding_years': years,
    'cases': cases,
    'base_APV': apv,
    'entry_ceilings_and_return_hurdles': entry_ceilings,
    'conditional_reverse_margin_roots': reverse_roots,
    'conditional_quote_matching_constant_rate': {'rate': implied_rate, 'change_from_selected_rate_bp': (implied_rate - selected_rate) * 10000, 'planning_value_USD': rate_values[2026]['price_USD'], '2030target_USD': rate_values[2030]['price_USD'], 'interpretation': 'One-variable quote match at the December2026 planning date, not an identified market expectation or revised selected discount rate.'},
    'checks': {'independent_APV_vs_common_subtraction_checks': len(checks), 'max_price_discrepancy_USD': max(abs(x) for x in checks), 'all_operating_and_financing_PVs_and_before_settlement_treasury_balances_unchanged': True, 'frozen_model_files_not_written': True},
    'limits': ['No probabilities, settlement dates, tax benefits or maximum legal loss are inferred.', 'The explicit reserve is not spendable cash; reported treasury balances precede settlement against the reserve.', 'If settlement cash is deducted later, release the same reserve once to preserve the identity.', 'Annualcash less the full reserve is a liquidity arithmetic diagnostic, not a quarterly liquidity forecast or an assumed settlement schedule.', 'EC is not charged again while its funded restricted cash remains excluded; no presumed excess is credited.', 'The quote precedes the planning valuation date by56days.'],
}
(OUT / 'explicit_claims_overlay_results.json').write_text(json.dumps(output, indent=2) + '\n')
print(json.dumps({
    'per_share_claim_deduction_USD': deduction,
    'main_scenarios': {name: cases[name]['summary'] for name in ['base', 'foundry_recovery_delayed_one_year', 'profit_retention_erosion_from_2028', 'CPU_growth_normalizes_2031', 'persistent_lower_CPU_demand', 'joint_downside', 'temporary_2027_unit_shortfall_restore_2028', 'mature_only_margin35', 'favorable_maturing_risk']},
    'entry_ceilings': entry_ceilings,
    'reverse_roots': reverse_roots,
    'base_APV': apv,
    'checks': output['checks'],
}, indent=2))

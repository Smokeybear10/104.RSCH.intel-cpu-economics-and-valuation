import copy
import hashlib
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path


OUT = Path(__file__).resolve().parent
RUN = OUT.parent
POLICY = OUT / 'favorable_cross_stress_policy.json'
ANCHOR = RUN / 'quarterly/anchor_valuation_overlay_results.json'
RISK = RUN / 'risk_policy/calculate_risk_robustness.py'
PACK_SCRIPT = OUT / 'packaging_scale_audit.py'
policy = json.loads(POLICY.read_text())


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


pack = load_module('cross_stress_packaging', PACK_SCRIPT)
risk = load_module('cross_stress_risk', RISK)
model = pack.model
source = json.loads(ANCHOR.read_text())['cases'][policy['favorable_case']]
rows = {int(y): copy.deepcopy(r) for y, r in source['annual_rows'].items()}
opening_delta = source['values']['2026']['cash_B'] - model.FUND[2027]['opening_economic_cash_B']
base = model.value(rows, opening_delta)
baseline_errors = []
for endpoint in [2026, 2030]:
    for field in ['price_USD', 'equity_B', 'explicit_operating_PV_B', 'terminal_operating_PV_B', 'cash_B', 'debt_B']:
        error = base['values'][endpoint][field] - source['values'][str(endpoint)][field]
        baseline_errors.append(abs(error))
        assert abs(error) < 1e-9, (endpoint, field, error)

cases = {'favorable_unchanged': base}
pack_rows = {}
for name, avoid in [('missing_program_proportional_cash_cost_avoidance', True), ('missing_program_no_cash_cost_avoidance', False)]:
    result = pack.calculate(avoid, base)
    cases[name] = result['case']
    pack_rows[name] = result['packaging_rows']

delay = json.loads((OUT / 'foundry_stress_policy.json').read_text())['scenarios']['two_year_recovery_delay']
delayed_rows = copy.deepcopy(rows)
normalized_ratio = 2.5 / rows[2032]['Products_revenue_B']
for year, row in delayed_rows.items():
    profit = delay['annual_host_Foundry_profit_2027_2032_B'][year - 2027] if year <= 2032 else normalized_ratio * row['Products_revenue_B']
    delta = profit - rows[year]['Foundry_profit_B']
    row['Foundry_profit_B'] = profit
    row['EBIT_B'] += delta
    model.close_cash(row)
    assert abs(row['EBIT_B'] - rows[year]['EBIT_B'] - delta) < 1e-12
    for field in ['Products_revenue_B', 'DCAI_profit_B', 'CCPG_profit_B', 'net_packaging_profit_B', 'physical_capex_B', 'DA_B', 'WC_cash_use_B']:
        assert row[field] == rows[year][field]
cases['two_year_Foundry_cost_recovery_delay'] = model.value(delayed_rows, opening_delta)

evaluations = {}
for name, case in cases.items():
    serialized = json.loads(json.dumps(case))
    evaluations[name] = risk.evaluate(serialized, rate=policy['rate'])

base_value = evaluations['favorable_unchanged']
assert abs(base_value['planning_value_USD'] - 56.1392858456) < 1e-8
assert abs(base_value['target2030_USD'] - 82.4701516268) < 1e-8
summaries = {}
for name, value in evaluations.items():
    case = cases[name]
    summaries[name] = {
        'planning_value_USD': value['planning_value_USD'],
        'planning_value_minus_entry_USD': value['planning_value_USD'] - model.ENTRY,
        'planning_value_over_entry_minus_one': value['planning_value_USD'] / model.ENTRY - 1,
        'planning_value_change_vs_favorable_USD': value['planning_value_USD'] - base_value['planning_value_USD'],
        'target2030_USD': value['target2030_USD'],
        'annual_price_return': value['annual_price_return'],
        'ending2030_cash_B': case['treasury'][2030]['ending_cash_B'],
        'owner_cash2027to2030_B': sum(r['owner_cash_B'] for r in case['treasury'].values()),
        'minimum_annual_cash_B': case['minimum_annual_cash_B'],
        'requires_financing_extension': case['requires_financing_extension'],
        '2030_Foundry_profit_B': case['annual_rows'][2030]['Foundry_profit_B'],
        '2030_net_packaging_profit_B': case['annual_rows'][2030]['net_packaging_profit_B'],
        '2030_group_EBIT_B': case['annual_rows'][2030]['EBIT_B'],
    }

result = {
    'computed_utc': datetime.now(timezone.utc).isoformat(),
    'input_sha256': {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in [POLICY, ANCHOR, RISK, PACK_SCRIPT, OUT / 'packaging_scale_stress_policy.json', OUT / 'foundry_stress_policy.json', *model.FILES.values()]},
    'policy': policy,
    'favorable_opening2027_cash_delta_B': opening_delta,
    'baseline_reconciliation': {'comparisons': len(baseline_errors), 'maximum_error_B_or_USD': max(baseline_errors)},
    'summaries': summaries,
    'risk_valuations': evaluations,
    'reconstructed_cases_before_rate_change': cases,
    'packaging_operating_bridges': pack_rows,
    'checks': {
        'favorable_operating_rows_reconstructed_before_stress': True,
        'favorable_anchor_cash_preserved': True,
        'ordinary_tax_and_treasury_recomputed_before_rerating': True,
        'same_rounded10625_rate_used_for_all_cases': True,
        'no_selected_case_value_deltas_transferred': True,
        'terminal_growth_reinvestment_recomputed_from_stressed_2040': True,
    },
    'limits': [
        'Planning value is at December 31, 2026; the reference quote is November 5. The difference is not a contemporaneous margin of safety or guaranteed realized return.',
        'The lower ERP methodology and favorable operating assumptions are a joint hypothesis, not established probabilities.',
        'Missing customer-family stress is not news of a canceled contract. Cash-cost flexibility is not identified from public customer data.',
        'Annual cash-floor checks do not establish intrayear liquidity under adverse receipt or spending timing.',
    ],
}
(OUT / 'favorable_cross_stress_results.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps({'baseline_reconciliation': result['baseline_reconciliation'], 'summaries': summaries}, indent=2))

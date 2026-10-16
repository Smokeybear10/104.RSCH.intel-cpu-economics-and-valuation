import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / 'tmp/intel_quarterly_deps'))

import numpy as np
from scipy.optimize import linprog

OUT = Path(__file__).resolve().parent
RESEARCH = ROOT / 'work/three_hour/active_research'
policy_path = OUT / 'quarterly_policy_before_calculation.json'
policy = json.loads(policy_path.read_text())
old_policy = json.loads((RESEARCH / 'pricing_and_competition_review_2026_11_04/intel_server_ASP_mix_operating_policy.json').read_text())
prior_identification_path = RESEARCH / 'intel_two_hour_comparison_2026_11_05/model_audit/ASP_carryover_identification_policy.json'
reported = json.loads(prior_identification_path.read_text())['reported_inputs']

segments = np.array(reported['2026_DCAI_revenue_B'])
prior_segments = np.array(reported['2025_DCAI_revenue_B'])
other_first_two = reported['Other_DCAI_2026_Q1_Q2_B']
other_increase = np.array(reported['Other_DCAI_increase_Q1_Q2_Q3_B'])
unit_changes = reported['unit_growth_Q1_Q2_Q3_H1_YTD']
asp_changes = reported['ASP_growth_Q1_Q2_Q3_H1_YTD']
groups = [(0,), (1,), (2,), (0, 1), (0, 1, 2)]


def constraints(other_q3: float) -> tuple | None:
    other = np.array([*other_first_two, other_q3])
    current_cpu = segments - other
    prior_cpu = prior_segments - (other - other_increase)
    rows = []
    for group, units, asp in zip(groups, unit_changes, asp_changes):
        positions = list(group)
        revenue_ratio = current_cpu[positions].sum() / prior_cpu[positions].sum()
        low = max(1 + units - .005, revenue_ratio / (1 + asp + .005))
        high = min(1 + units + .005, revenue_ratio / (1 + asp - .005))
        if low > high:
            return None
        upper, lower = np.zeros(6), np.zeros(6)
        for index in group:
            upper[index], upper[index + 3] = -high, 1
            lower[index], lower[index + 3] = low, -1
        rows.extend([upper, lower])
    return np.array(rows), current_cpu, prior_cpu


def identify(other_q3: float, objective: str) -> dict | None:
    values = constraints(other_q3)
    if values is None:
        return None
    matrix, current_cpu, prior_cpu = values
    cost = np.array([0., 0, 0, 1, 1, 1])
    if objective == 'maximum':
        cost *= -1
    if objective == 'equal_current_quarters':
        cost = np.array([0.] * 6 + [1., 1.])
        matrix = np.pad(matrix, ((0, 0), (0, 2)))
        extra = []
        limits = []
        for variable, slack in [(3, 6), (4, 7)]:
            upper = np.zeros(8)
            upper[variable], upper[slack] = 1, -1
            lower = np.zeros(8)
            lower[variable], lower[slack] = -1, -1
            extra.extend([upper, lower])
            limits.extend([1., -1.])
        right = np.array([0.] * len(matrix) + limits)
        matrix = np.vstack([matrix, extra])
        bounds = [(1e-9, None)] * 6 + [(0, None)] * 2
    else:
        right = np.zeros(len(matrix))
        bounds = [(1e-9, None)] * 6
    equality = [0., 0, 0, 0, 0, 1] + ([0., 0] if len(cost) == 8 else [])
    solution = linprog(cost, A_ub=matrix, b_ub=right, A_eq=[equality], b_eq=[1], bounds=bounds, method='highs')
    if not solution.success:
        return None
    prior_units, current_units = solution.x[:3], solution.x[3:6]
    checks = []
    for group, units, asp in zip(groups, unit_changes, asp_changes):
        positions = list(group)
        actual_units = current_units[positions].sum() / prior_units[positions].sum()
        actual_asp = (current_cpu[positions].sum() / current_units[positions].sum()) / (prior_cpu[positions].sum() / prior_units[positions].sum())
        assert abs(actual_units - 1 - units) <= .00500001
        assert abs(actual_asp - 1 - asp) <= .00500001
        checks.append({'quarters': [i + 1 for i in group], 'unit_growth': float(actual_units - 1), 'ASP_growth': float(actual_asp - 1)})
    return {
        'Q3_Other_B': other_q3,
        'current_CPU_revenue_B': current_cpu.tolist(),
        'prior_CPU_revenue_B': prior_cpu.tolist(),
        'current_units_over_2026Q3': current_units.tolist(),
        'prior_units_over_2026Q3': prior_units.tolist(),
        'current_YTD_units_over_2026Q3': float(current_units.sum()),
        'unit_deviation_from_equal_current_quarters': float(np.abs(current_units[:2] - 1).sum()),
        'ratio_checks': checks,
        'maximum_constraint_error': float(max(np.max(matrix @ solution.x - right), 0)),
    }


strict_other_q3 = 3.3 - sum(other_first_two)
strict_test = identify(strict_other_q3, 'minimum')
grid = np.linspace(1.364, 1.441, 1001)
minimum_solutions = [row for other in grid if (row := identify(float(other), 'minimum'))]
maximum_solutions = [row for other in grid if (row := identify(float(other), 'maximum'))]
assert minimum_solutions and maximum_solutions
feasible_other = [row['Q3_Other_B'] for row in minimum_solutions]
chosen_other = (min(feasible_other) + max(feasible_other)) / 2
chosen = identify(chosen_other, 'equal_current_quarters')
assert chosen is not None
q4_units_over_q3 = policy['Q4_2026_anchor']['Q4_units_over_Q3_for_chosen_calibration']
q4_revenue = policy['Q4_2026_anchor']['CPU_revenue_B']
history = []
for quarter, (revenue, units) in enumerate(zip(chosen['current_CPU_revenue_B'], chosen['current_units_over_2026Q3']), 1):
    unit_index = units / q4_units_over_q3 * 100
    asp_index = revenue / q4_revenue / (unit_index / 100) * 100
    history.append({'year': 2026, 'quarter': quarter, 'CPU_revenue_B': revenue, 'unit_index_Q4_2026_100': unit_index, 'ASP_index_Q4_2026_100': asp_index, 'classification': 'One interval-consistent calibration, not reported quantities or ASP levels'})
history.append({'year': 2026, 'quarter': 4, 'CPU_revenue_B': q4_revenue, 'unit_index_Q4_2026_100': 100., 'ASP_index_Q4_2026_100': 100., 'classification': 'Analyst Q4 forecast; not actual'})
history_units = sum(row['unit_index_Q4_2026_100'] for row in history)
history_revenue = sum(row['CPU_revenue_B'] for row in history)
old_2026_revenue = 21.8577
history_weighted_asp = history_revenue / history_units
allocation_basis_asp = old_2026_revenue / history_units


def build_case(name: str) -> dict:
    schedule = policy[f'{name}_2027_QoQ']
    unit_index = asp_index = 100.
    quarterly = []
    for quarter, (unit_growth, asp_growth) in enumerate(zip(schedule['units'], schedule['ASP']), 1):
        unit_index *= 1 + unit_growth
        asp_index *= 1 + asp_growth
        revenue = q4_revenue * unit_index / 100 * asp_index / 100
        quarterly.append({'year': 2027, 'quarter': quarter, 'unit_growth_QoQ': unit_growth, 'ASP_growth_QoQ': asp_growth, 'unit_index_Q4_2026_100': unit_index, 'ASP_index_Q4_2026_100': asp_index, 'CPU_revenue_B': revenue})
    units = sum(row['unit_index_Q4_2026_100'] for row in quarterly)
    revenue = sum(row['CPU_revenue_B'] for row in quarterly)
    weighted_asp = revenue / units
    annual_units_growth = units / history_units - 1
    annual_asp_growth_on_allocation = weighted_asp / allocation_basis_asp - 1
    assert abs(old_2026_revenue * (1 + annual_units_growth) * (1 + annual_asp_growth_on_allocation) - revenue) < 1e-10
    annual = [{'year': 2027, 'CPU_revenue_B': revenue, 'unit_growth': annual_units_growth, 'ASP_growth': annual_asp_growth_on_allocation, 'base_classification': 'Derived from explicitly selected Q4 calibration and original annual revenue allocation; not identified historical unit growth'}]
    for year, ug, ag in zip(range(2028, 2031), policy[f'{name}_2028_2030_annual']['unit_growth'], policy[f'{name}_2028_2030_annual']['ASP_growth']):
        revenue *= (1 + ug) * (1 + ag)
        annual.append({'year': year, 'CPU_revenue_B': revenue, 'unit_growth': ug, 'ASP_growth': ag, 'base_classification': 'Owned analyst forecast'})
    previous_new_revenue = previous_old_revenue = old_2026_revenue
    for row in annual:
        old = next(value for value in old_policy['annual_rows'] if value['year'] == row['year'])
        old_revenue = old['server_CPU_revenue_proxy_B']
        row['old_CPU_revenue_B'] = old_revenue
        row['revenue_delta_vs_old_B'] = row['CPU_revenue_B'] - old_revenue
        row['revenue_delta_vs_old_fraction'] = row['CPU_revenue_B'] / old_revenue - 1
        carry = (previous_new_revenue - previous_old_revenue) * (1 + old['server_unit_growth']) * (1 + old['server_ASP_growth'])
        volume = previous_new_revenue * (row['unit_growth'] - old['server_unit_growth']) * (1 + old['server_ASP_growth'])
        asp = previous_new_revenue * (1 + row['unit_growth']) * (row['ASP_growth'] - old['server_ASP_growth'])
        row['ordered_revenue_bridge_B'] = {'prior_level_carry_at_old_growth': carry, 'units_at_old_ASP_factor': volume, 'ASP_on_new_units_factor': asp, 'sum': carry + volume + asp, 'boundary': 'Arithmetic attribution; 2027 unit/ASP allocation depends on chosen historical calibration and is not causal cost evidence.'}
        assert abs(carry + volume + asp - row['revenue_delta_vs_old_B']) < 1e-8
        previous_new_revenue, previous_old_revenue = row['CPU_revenue_B'], old_revenue
    h1_revenue = sum(row['CPU_revenue_B'] for row in quarterly[:2])
    h2_revenue = sum(row['CPU_revenue_B'] for row in quarterly[2:])
    h1_units = sum(row['unit_index_Q4_2026_100'] for row in quarterly[:2])
    h2_units = sum(row['unit_index_Q4_2026_100'] for row in quarterly[2:])
    return {'quarterly_2027': quarterly, 'annual_2027_2030': annual, '2027_unit_growth_calibrated': annual_units_growth, '2027_ASP_growth_calibrated_original_allocation': annual_asp_growth_on_allocation, '2027_ASP_growth_vs_feasible_history': weighted_asp / history_weighted_asp - 1, 'H2_vs_H1': {'revenue_growth': h2_revenue / h1_revenue - 1, 'unit_growth': h2_units / h1_units - 1, 'weighted_ASP_growth': (h2_revenue / h2_units) / (h1_revenue / h1_units) - 1}, 'flat_Q4_2027_exit_carryover_into_2028': {'unit_growth_if_each2028quarter_equals2027Q4': 4 * unit_index / units - 1, 'ASP_growth_if_each2028quarter_equals2027Q4': (q4_revenue / 100 * asp_index / 100) / weighted_asp - 1}, '2027_sales_vs_flat_Q4_2026_runrate': annual[0]['CPU_revenue_B'] / (4 * q4_revenue) - 1}


cases = {name: build_case(name) for name in ['preferred', 'slower']}
interval_sensitivities = []
for q4_ratio in [.9, 1., 1.05, 1.1, 1.2]:
    for name, case in cases.items():
        future_units = sum(row['unit_index_Q4_2026_100'] for row in case['quarterly_2027']) / 100
        future_revenue = case['annual_2027_2030'][0]['CPU_revenue_B']
        observations = []
        for row in minimum_solutions + maximum_solutions:
            old_units = row['current_YTD_units_over_2026Q3'] / q4_ratio + 1
            annual_ug = future_units / old_units - 1
            annual_ag = (future_revenue / old_2026_revenue) / (1 + annual_ug) - 1
            observations.append((annual_ug, annual_ag))
        interval_sensitivities.append({'case': name, 'assumed_Q4_2026_units_over_Q3': q4_ratio, '2027_unit_growth_min': min(v[0] for v in observations), '2027_unit_growth_max': max(v[0] for v in observations), '2027_ASP_growth_min_on_owned_revenue_allocation': min(v[1] for v in observations), '2027_ASP_growth_max_on_owned_revenue_allocation': max(v[1] for v in observations), 'boundary': 'Conditional interval arithmetic, not confidence bounds; annual revenue unchanged across calibration.'})

old_target = policy['old_annual_case']['2027_CPU_revenue_B']
preferred_h1 = sum(row['CPU_revenue_B'] for row in cases['preferred']['quarterly_2027'][:2])
target_hurdles = []
for sequential_asp in [0, .05, .10, .15, .20]:
    target_hurdles.append({'assumed_H2_weighted_ASP_vs_H1': sequential_asp, 'required_H2_units_vs_H1_for_old_target': (old_target - preferred_h1) / preferred_h1 / (1 + sequential_asp) - 1})

preferred_h2 = sum(row['CPU_revenue_B'] for row in cases['preferred']['quarterly_2027'][2:])
old_target_h2_multiplier = (old_target - preferred_h1) / preferred_h2
old_target_schedule = []
previous_units = 100.
for row in cases['preferred']['quarterly_2027']:
    multiplier = old_target_h2_multiplier if row['quarter'] >= 3 else 1.
    revised = dict(row)
    revised['unit_index_Q4_2026_100'] *= multiplier
    revised['CPU_revenue_B'] *= multiplier
    revised['unit_growth_QoQ'] = revised['unit_index_Q4_2026_100'] / previous_units - 1
    previous_units = revised['unit_index_Q4_2026_100']
    old_target_schedule.append(revised)
assert abs(sum(row['CPU_revenue_B'] for row in old_target_schedule) - old_target) < 1e-9
old_target_units = sum(row['unit_index_Q4_2026_100'] for row in old_target_schedule)

old_exact_unit_sum = history_units * 1.20
old_exact_h1_units = sum(row['unit_index_Q4_2026_100'] for row in cases['preferred']['quarterly_2027'][:2])
old_exact_h2_units = old_exact_unit_sum - old_exact_h1_units
old_exact_h2_asp = (old_target - preferred_h1) / (q4_revenue / 10000) / old_exact_h2_units
old_exact_h1_asp = preferred_h1 / (q4_revenue / 10000) / old_exact_h1_units

result = {
    'computed_utc': datetime.now(timezone.utc).isoformat(),
    'policy_sha256': hashlib.sha256(policy_path.read_bytes()).hexdigest(),
    'strict_history_center_test': {'owned_YTD_CPU_B': 15.332, 'implied_Q3_Other_B': strict_other_q3, 'feasible_at_direct_million_centers': strict_test is not None, 'reason': 'At the exact rounded-YTD allocation, Q3 CPU revenue ratio is above the largest ratio permitted by reported unit+10% and ASP+54% rounding bands. Do not interpret rounded centers as exact measurements.', 'robust_million_rounding_check': {'minimum_Q3_revenue_ratio_allowing_generous_0_5M_centers': 5.9025 / 3.448, 'maximum_units_times_ASP_ratio': 1.105 * 1.545}},
    'conditional_identification': {'feasible_grid_points': len(minimum_solutions), 'total_grid_points': len(grid), 'Q3_Other_feasible_grid_min_max_B': [min(feasible_other), max(feasible_other)], 'calibration_method': 'Midpoint of feasible Other interval, then minimize absolute departure of2026Q1/Q2units fromQ3units. This avoids importing unsupported quarterly seasonality; it is not an estimator or observed shipment table.', 'selected_witness': chosen, 'Q4_2026_unit_ratio_assumption': q4_units_over_q3},
    'historical_calibration': history,
    'history_revenue_reconciliation': {'original_2026_CPU_allocation_B': old_2026_revenue, 'interval_consistent_history_plus_ownedQ4_B': history_revenue, 'allocation_difference_B': history_revenue - old_2026_revenue, 'handling': 'Retain originalannualallocation for valuation comparison; do not rewrite history as observed. Annual unit/ASP decomposition is a calibration. Sequential2027forecast dollars do not depend on reconstructed2026weights.'},
    'cases': cases,
    'calibration_interval_sensitivities': interval_sensitivities,
    'old_target_with_preferred_H1': {'H1_CPU_sales_B': preferred_h1, 'required_H2_CPU_sales_B': old_target - preferred_h1, 'required_H2_quarterly_average_B': (old_target - preferred_h1) / 2, 'required_H2_vs_H1_revenue_growth': (old_target - preferred_h1) / preferred_h1 - 1, 'unit_ASP_combinations': target_hurdles, 'favorable_target_hold_schedule': old_target_schedule, 'required_H2_units_multiplier_vs_preferred': old_target_h2_multiplier, 'calibrated_annual_units_growth': old_target_units / history_units - 1, 'calibrated_annual_ASP_growth': (old_target / old_target_units) / allocation_basis_asp - 1, 'exact_old_20_20_under_chosen_history': {'required_H2_unit_index_sum': old_exact_h2_units, 'required_H2_units_vs_H1_growth': old_exact_h2_units / old_exact_h1_units - 1, 'required_H2_weighted_ASP_index': old_exact_h2_asp, 'required_H2_weighted_ASP_vs_H1_growth': old_exact_h2_asp / old_exact_h1_asp - 1}, 'classification': 'Reverse hurdle, not an independently validated delivery forecast. H1 held fixed; faster H2 units can preserve old annual revenue without changing preferred ASP path.'},
    'accounting_guards': ['Q4anchor alreadyincludesFab28; preferredQ1retains similarlevel, no additional blanket300Mdeduction','No2027demandmissisautomaticallyrecapturedin2028','No separatewafergrowthorcorecountmultiplier','No additionalFoundryabsorptionbenefitattachedtoCPUvolumeincrease','Noequityvaluationcalculated','ASP/unitbandsareconditionalcommon-scoperoundingbounds, notstatisticalconfidenceintervals'],
}
(OUT / 'quarterly_delivery_results.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps({'strict_history_feasible': strict_test is not None, 'chosen_historical_units': chosen['current_units_over_2026Q3'], 'historical_allocation_difference_B': history_revenue - old_2026_revenue, 'cases': {name: {'quarters_B': [r['CPU_revenue_B'] for r in case['quarterly_2027']], 'annual_B': [r['CPU_revenue_B'] for r in case['annual_2027_2030']], 'annual2027_units': case['2027_unit_growth_calibrated'], 'annual2027_ASP': case['2027_ASP_growth_calibrated_original_allocation'], '2028carryover': case['flat_Q4_2027_exit_carryover_into_2028']} for name, case in cases.items()}}, indent=2))

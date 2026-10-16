import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy.optimize import linprog, minimize_scalar


OUT = Path(__file__).resolve().parent
policy_path = OUT / 'ASP_carryover_identification_policy.json'
policy = json.loads(policy_path.read_text())
inputs = policy['reported_inputs']
current_segments = np.array(inputs['2026_DCAI_revenue_B'])
previous_segments = np.array(inputs['2025_DCAI_revenue_B'])
current_other_first_two = inputs['Other_DCAI_2026_Q1_Q2_B']
other_increase = np.array(inputs['Other_DCAI_increase_Q1_Q2_Q3_B'])
units = inputs['unit_growth_Q1_Q2_Q3_H1_YTD']
asps = inputs['ASP_growth_Q1_Q2_Q3_H1_YTD']
groups = [(0,), (1,), (2,), (0, 1), (0, 1, 2)]
o_low = max(1.35, 3.25 - sum(current_other_first_two), 1.95 + sum(other_increase) - sum(current_other_first_two))
o_high = min(1.45, 3.35 - sum(current_other_first_two), 2.05 + sum(other_increase) - sum(current_other_first_two))


def solve(other_q3: float, direction: str) -> dict | None:
    current_other = np.array([*current_other_first_two, other_q3])
    current_cpu = current_segments - current_other
    previous_cpu = previous_segments - (current_other - other_increase)
    constraints = []
    for group, unit, asp in zip(groups, units, asps):
        revenue_ratio = current_cpu[list(group)].sum() / previous_cpu[list(group)].sum()
        low = max(1 + unit - .005, revenue_ratio / (1 + asp + .005))
        high = min(1 + unit + .005, revenue_ratio / (1 + asp - .005))
        if low > high:
            return None
        upper, lower = np.zeros(6), np.zeros(6)
        for index in group:
            upper[index], upper[index + 3] = -high, 1
            lower[index], lower[index + 3] = low, -1
        constraints.extend([upper, lower])
    coefficients = np.array([0., 0, 0, 1, 1, 1])
    if direction == 'max':
        coefficients *= -1
    result = linprog(coefficients, A_ub=np.array(constraints), b_ub=np.zeros(len(constraints)), A_eq=[[0, 0, 0, 0, 0, 1]], b_eq=[1], bounds=[(1e-10, None)] * 6, method='highs')
    if not result.success:
        return None
    past_units, present_units = result.x[:3], result.x[3:]
    details = []
    for group in groups:
        gi = list(group)
        unit_factor = present_units[gi].sum() / past_units[gi].sum()
        revenue_factor = current_cpu[gi].sum() / previous_cpu[gi].sum()
        details.append({'quarters': [i + 1 for i in gi], 'unit_growth': unit_factor - 1, 'ASP_growth': revenue_factor / unit_factor - 1})
    ratio = present_units.sum()
    return {'Q3_Other_revenue_B': other_q3, '2026_quarter_CPU_revenue_B': current_cpu.tolist(), '2025_quarter_CPU_revenue_B': previous_cpu.tolist(), '2025_units_normalized_to_2026Q3_1': past_units.tolist(), '2026_units_normalized_to_Q3_1': present_units.tolist(), 'YTD_units_over_Q3_units': ratio, 'Q3_ASP_over_YTD_ASP_minus1': current_cpu[2] / current_cpu.sum() * ratio - 1, 'ratio_checks': details, 'max_constraint_residual': float(np.max(np.array(constraints) @ result.x))}


grid = np.linspace(o_low, o_high, 1001)
solutions = {direction: [result for other in grid if (result := solve(float(other), direction))] for direction in ['min', 'max']}
assert solutions['min'], 'No interval-consistent solution; do not publish a carryover estimate.'
extremes = {}
for direction in ['min', 'max']:
    best = (min if direction == 'min' else max)(solutions[direction], key=lambda result: result['Q3_ASP_over_YTD_ASP_minus1'])
    index = int(np.argmin(abs(grid - best['Q3_Other_revenue_B'])))
    bounds = (float(grid[max(0, index - 2)]), float(grid[min(1000, index + 2)]))
    def objective(other: float) -> float:
        row = solve(other, direction)
        if row is None:
            return 1e6
        return row['Q3_ASP_over_YTD_ASP_minus1'] * (1 if direction == 'min' else -1)
    refined = minimize_scalar(objective, bounds=bounds, method='bounded', options={'xatol': 1e-13})
    candidate = solve(refined.x, direction)
    if candidate and objective(refined.x) < objective(best['Q3_Other_revenue_B']):
        best = candidate
    extremes[direction] = best

carryover = []
for q4_units in [.9, 1, 1.1, 1.2]:
    row = {'assumed_Q4_over_Q3_units': q4_units, 'owned_Q4_CPU_revenue_B': 6.5257}
    values = []
    for direction in ['min', 'max']:
        candidates = []
        for result in solutions[direction]:
            current_ytd_revenue = sum(result['2026_quarter_CPU_revenue_B'])
            candidate = 6.5257 / (current_ytd_revenue + 6.5257) * (result['YTD_units_over_Q3_units'] / q4_units + 1) - 1
            candidates.append((candidate, result['Q3_Other_revenue_B']))
        selected = (min if direction == 'min' else max)(candidates)
        row[f'{direction}_flat_Q4_ASP_carryover_2027'] = selected[0]
        row[f'{direction}_witness_Q3_Other_B'] = selected[1]
    carryover.append(row)

result = {'computed_utc': datetime.now(timezone.utc).isoformat(), 'policy_sha256': hashlib.sha256(policy_path.read_bytes()).hexdigest(), 'policy': policy, 'candidate_Q3_Other_interval_B': [o_low, o_high], 'feasible_grid_count': len(solutions['min']), 'grid_count': 1001, 'Q3_ASP_over_YTD_bounds': extremes, 'Q4_flat_exit_carryover_diagnostic': carryover, 'interpretation': 'These are necessary interval-consistent bounds under the stated common-scope and rounding assumptions, conditional on an ownedQ4revenue estimate. They are not measuredcarryover, not evidence for same-SKUpricing, and not a forecast of2027unitmix. Unlike simply comparing YoYASP54%toYTD44%, they respect shipment weights and all quarterly/aggregate ratio identities. Endpoints should not be treated as probabilistic or equally likely.'}
(OUT / 'ASP_carryover_identification_results.json').write_text(json.dumps(result, indent=2) + '\n')
print('feasible', len(solutions['min']), 'of1001')
for k, v in extremes.items():
    print(k, v['Q3_ASP_over_YTD_ASP_minus1'], 'Q3Other', v['Q3_Other_revenue_B'], 'weights', v['2026_units_normalized_to_Q3_1'])
print(json.dumps(carryover, indent=2))

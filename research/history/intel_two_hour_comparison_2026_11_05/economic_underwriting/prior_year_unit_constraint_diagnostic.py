import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy.optimize import linprog

root = Path(__file__).resolve().parent
policy_path = root / 'prior_year_unit_constraint_policy.json'
policy = json.loads(policy_path.read_text())
base = json.loads((root.parent / 'model_audit/ASP_carryover_identification_policy.json').read_text())
inputs = base['reported_inputs']
groups = [(0,), (1,), (2,), (0, 1), (0, 1, 2)]
other_first_two = inputs['Other_DCAI_2026_Q1_Q2_B']
other_delta = np.array(inputs['Other_DCAI_increase_Q1_Q2_Q3_B'])
low = max(1.35, 3.25 - sum(other_first_two), 1.95 + sum(other_delta) - sum(other_first_two))
high = min(1.45, 3.35 - sum(other_first_two), 2.05 + sum(other_delta) - sum(other_first_two))


def solve(other: float, band: float, maximize: bool) -> dict | None:
    revenue_2026 = np.array(inputs['2026_DCAI_revenue_B']) - [*other_first_two, other]
    revenue_2025 = np.array(inputs['2025_DCAI_revenue_B']) - (np.array([*other_first_two, other]) - other_delta)
    rows = []

    def constrain(offset: int, group: tuple, lower: float, upper: float) -> None:
        upper_row = np.zeros(9)
        lower_row = np.zeros(9)
        for i in group:
            upper_row[offset + i] = -upper
            upper_row[offset + 3 + i] = 1
            lower_row[offset + i] = lower
            lower_row[offset + 3 + i] = -1
        rows.extend([upper_row, lower_row])

    for group, unit, asp in zip(groups, inputs['unit_growth_Q1_Q2_Q3_H1_YTD'], inputs['ASP_growth_Q1_Q2_Q3_H1_YTD']):
        indices = list(group)
        revenue_ratio = revenue_2026[indices].sum() / revenue_2025[indices].sum()
        lower = max(1 + unit - .005, revenue_ratio / (1 + asp + .005))
        upper = min(1 + unit + .005, revenue_ratio / (1 + asp - .005))
        if lower > upper:
            return None
        constrain(3, group, lower, upper)
    for group, growth in zip(groups, [.16, .13, 0, .15, .10]):
        tolerance = band if group == (2,) else .005
        constrain(0, group, 1 + growth - tolerance, 1 + growth + tolerance)
    objective = np.array([0.] * 6 + [1.] * 3) * (-1 if maximize else 1)
    equality = np.zeros((1, 9))
    equality[0, 8] = 1
    fit = linprog(objective, A_ub=rows, b_ub=np.zeros(len(rows)), A_eq=equality, b_eq=[1.], bounds=[(1e-10, None)] * 9, method='highs')
    if not fit.success:
        return None
    units = fit.x.reshape(3, 3)
    ratios = []
    for group in groups:
        indices = list(group)
        ratios.append({'quarters': [i + 1 for i in group], 'unit_growth_2025': units[1, indices].sum() / units[0, indices].sum() - 1, 'unit_growth_2026': units[2, indices].sum() / units[1, indices].sum() - 1})
    return {'other_Q3_B': other, 'units_2024_to_2026_normalized': units.tolist(), 'revenue_2026_CPU_B': revenue_2026.tolist(), 'Q3_ASP_over_YTD_minus1': revenue_2026[2] * units[2].sum() / revenue_2026.sum() - 1, 'unit_ratio_checks': ratios, 'max_constraint_violation': max(0., float(np.max(np.array(rows) @ fit.x)))}


results = []
for band in policy['roughly_flat_bands_to_test']:
    rows = [solve(float(o), band, maximize) for o in np.linspace(low, high, 1001) for maximize in [False, True]]
    feasible = [r for r in rows if r]
    if not feasible:
        results.append({'band': band, 'status': 'No feasible point on grid'})
        continue
    carryover = []
    for q4_units in [.9, 1., 1.1, 1.2]:
        values = [6.5257 / (sum(r['revenue_2026_CPU_B']) + 6.5257) * (sum(r['units_2024_to_2026_normalized'][2]) / q4_units + 1) - 1 for r in feasible]
        carryover.append({'Q4_units_over_Q3': q4_units, 'min': min(values), 'max': max(values)})
    results.append({'band': band, 'feasible_grid_endpoints': len(feasible), 'min_Q3_witness': min(feasible, key=lambda r: r['Q3_ASP_over_YTD_minus1']), 'max_Q3_witness': max(feasible, key=lambda r: r['Q3_ASP_over_YTD_minus1']), 'Q4_flat_exit_carryover': carryover})
output = {'computed_utc': datetime.now(timezone.utc).isoformat(), 'policy_sha256': hashlib.sha256(policy_path.read_bytes()).hexdigest(), 'policy': policy, 'results': results, 'conclusion_boundary': 'Numerical feasible-set diagnostic conditional on common server-volume scope and analyst rounding bands. Not a forecast or statistical confidence interval. Q4 remains unobserved.'}
(root / 'prior_year_unit_constraint_results.json').write_text(json.dumps(output, indent=2) + '\n')
for r in results:
    print(r['band'], r.get('min_Q3_witness', {}).get('Q3_ASP_over_YTD_minus1'), r.get('max_Q3_witness', {}).get('Q3_ASP_over_YTD_minus1'))
    print(r.get('Q4_flat_exit_carryover'))

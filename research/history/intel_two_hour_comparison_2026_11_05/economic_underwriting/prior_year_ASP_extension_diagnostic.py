import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy.optimize import linprog

root = Path(__file__).resolve().parent
policy_path = root / 'prior_year_ASP_extension_policy.json'
policy = json.loads(policy_path.read_text())
prior = json.loads((root / 'prior_year_unit_constraint_results.json').read_text())
base = json.loads((root.parent / 'model_audit/ASP_carryover_identification_policy.json').read_text())['reported_inputs']
groups = [(0,), (1,), (2,), (0, 1), (0, 1, 2)]
dcai_2024 = np.array(policy['scope_check']['recast_2024_DCAI_revenue_B'])


def extend(witness, band, strict_margin=0.0):
    units_2025 = np.array(witness['units_2024_to_2026_normalized'][1])
    units_2026 = np.array(witness['units_2024_to_2026_normalized'][2])
    other_2026 = np.array([*base['Other_DCAI_2026_Q1_Q2_B'], witness['other_Q3_B']])
    other_2025 = other_2026 - np.array(base['Other_DCAI_increase_Q1_Q2_Q3_B'])
    rev_2025 = np.array(base['2025_DCAI_revenue_B']) - other_2025
    rev_2026 = np.array(witness['revenue_2026_CPU_B'])
    constraints = []
    bounds = []
    labels = []

    def add(row, bound, label):
        constraints.append(row)
        bounds.append(bound)
        labels.append(label)

    for group, units_growth, asp_growth in zip(groups, policy['new_reported_inputs']['unit_growth_2025_vs_2024'], policy['new_reported_inputs']['ASP_growth_2025_vs_2024']):
        tolerance = (band if group == (2,) else 0.005) - strict_margin
        u25 = units_2025[list(group)].sum()
        r25 = rev_2025[list(group)].sum()
        unit_row = np.zeros(6)
        unit_row[list(group)] = 1
        add(unit_row, u25 / (1 + units_growth - tolerance), f'{group} units lower growth')
        add(-unit_row, -u25 / (1 + units_growth + tolerance), f'{group} units upper growth')
        asp_upper = np.zeros(6)
        asp_lower = np.zeros(6)
        for i in group:
            asp_upper[i] = r25 / u25
            asp_upper[i + 3] = -(1 + asp_growth + tolerance)
            asp_lower[i] = -r25 / u25
            asp_lower[i + 3] = 1 + asp_growth - tolerance
        add(asp_upper, 0, f'{group} ASP upper')
        add(asp_lower, 0, f'{group} ASP lower')
    revenue_band = band - strict_margin
    revenue_row = np.zeros(6)
    revenue_row[5] = 1
    add(revenue_row, rev_2025[2] / (1 - revenue_band), 'Q3 roughly flat server revenue lower growth')
    add(-revenue_row, -rev_2025[2] / (1 + revenue_band), 'Q3 roughly flat server revenue upper growth')
    for group in [(0, 1), (0, 1, 2)]:
        row = np.zeros(6)
        for i in group:
            row[i + 3] = -1
        lower = dcai_2024[list(group)].sum() - other_2025[list(group)].sum()
        add(row, -lower, f'{group} Other revenue increased')
    row = np.zeros(6)
    row[5] = 1
    add(row, dcai_2024[2] - other_2025[2], 'Q3 Other revenue decreased')
    fit = linprog(np.zeros(6), A_ub=constraints, b_ub=bounds, bounds=[(1e-10, None)] * 3 + [(1e-10, d) for d in dcai_2024], method='highs')
    if not fit.success:
        return {'status': 'infeasible endpoint extension', 'solver_status': fit.status, 'solver_message': fit.message}
    units_2024, rev_2024 = fit.x[:3], fit.x[3:]
    checks = []
    for group in groups:
        idx = list(group)
        u24, u25 = units_2024[idx].sum(), units_2025[idx].sum()
        r24, r25 = rev_2024[idx].sum(), rev_2025[idx].sum()
        checks.append({'quarters': [i + 1 for i in group], '2025_unit_growth': u25 / u24 - 1, '2025_ASP_growth': (r25 / u25) / (r24 / u24) - 1, '2025_CPU_revenue_growth': r25 / r24 - 1, 'Other_revenue_2025_minus_2024_B': other_2025[idx].sum() - (dcai_2024[idx] - rev_2024[idx]).sum()})
    carryover = []
    for q4_units in [0.9, 1, 1.1, 1.2]:
        carryover.append({'Q4_units_over_Q3': q4_units, 'flat_Q4_ASP_2027_carryover': 6.5257 / (rev_2026.sum() + 6.5257) * (units_2026.sum() / q4_units + 1) - 1})
    violation = np.array(constraints) @ fit.x - np.array(bounds)
    return {'status': 'feasible endpoint extension', 'units_2024_to_2026_normalized': [units_2024.tolist(), units_2025.tolist(), units_2026.tolist()], 'CPU_revenue_2024_to_2026_B': [rev_2024.tolist(), rev_2025.tolist(), rev_2026.tolist()], 'Other_revenue_2024_B': (dcai_2024 - rev_2024).tolist(), 'ratio_and_direction_checks': checks, 'carryover': carryover, 'max_linear_constraint_violation': max(0.0, float(violation.max())), 'original_2026_witness': witness}


results = []
for old_result in prior['results']:
    band = old_result['band']
    for side in ['min_Q3_witness', 'max_Q3_witness']:
        row = {'roughly_flat_band': band, 'old_endpoint': side, 'prior_carryover_bounds': old_result['Q4_flat_exit_carryover'], **extend(old_result[side], band)}
        results.append(row)
def target_2026_witness(other, objective):
    followup = policy['followup_interior_witness_policy']
    tolerance = 0.005 - followup['strict_rounding_margin']
    other26 = np.array([*base['Other_DCAI_2026_Q1_Q2_B'], other])
    rev26 = np.array(base['2026_DCAI_revenue_B']) - other26
    rev25 = np.array(base['2025_DCAI_revenue_B']) - (other26 - np.array(base['Other_DCAI_increase_Q1_Q2_Q3_B']))
    rows = []
    for group, unit, asp in zip(groups, base['unit_growth_Q1_Q2_Q3_H1_YTD'], base['ASP_growth_Q1_Q2_Q3_H1_YTD']):
        idx = list(group)
        ratio = rev26[idx].sum() / rev25[idx].sum()
        lo = max(1 + unit - tolerance, ratio / (1 + asp + tolerance))
        hi = min(1 + unit + tolerance, ratio / (1 + asp - tolerance))
        if lo > hi:
            return None
        up = np.zeros(6)
        down = np.zeros(6)
        for i in group:
            up[i], up[3+i] = -hi, 1
            down[i], down[3+i] = lo, -1
        rows.extend([up, down])
    q4 = followup['assumed_Q4_Q3_unit_factor']
    target = followup['target_carryover']
    target_sum = ((1 + target) * (rev26.sum() + 6.5257) / 6.5257 - 1) * q4
    ae = np.zeros((2,6)); ae[0,5] = 1; ae[1,3:] = 1
    fit = linprog(objective, A_ub=rows, b_ub=np.zeros(len(rows)), A_eq=ae, b_eq=[1,target_sum], bounds=[(1e-10,None)]*6, method='highs')
    if not fit.success:
        return None
    return {'other_Q3_B':other,'units_2024_to_2026_normalized':[[None]*3,fit.x[:3].tolist(),fit.x[3:].tolist()],'revenue_2026_CPU_B':rev26.tolist(),'max_2026_linear_constraint_violation':max(0,float((np.array(rows)@fit.x).max()))}


interior_attempts=[]
interior_witness=None
objectives=[np.zeros(6)] + [sign*np.eye(6)[i] for i in range(5) for sign in [-1,1]]
for other in policy['followup_interior_witness_policy']['candidate_Other_Q3_B']:
    for i, objective in enumerate(objectives):
        candidate=target_2026_witness(other,objective)
        if candidate is None:
            interior_attempts.append({'other_Q3_B':other,'objective_index':i,'status':'2026target LP infeasible'})
            continue
        extended=extend(candidate,0.005,policy['followup_interior_witness_policy']['strict_rounding_margin'])
        interior_attempts.append({'other_Q3_B':other,'objective_index':i,'status':extended['status']})
        if extended['status']=='feasible endpoint extension':
            interior_witness=extended
            break
    if interior_witness is not None:
        break

output = {'computed_utc': datetime.now(timezone.utc).isoformat(), 'policy_sha256': hashlib.sha256(policy_path.read_bytes()).hexdigest(), 'policy': policy, 'endpoint_extension_results': results, 'interior_target_attempts': interior_attempts, 'interior_20pct_carryover_witness': interior_witness, 'initial_endpoint_result_file': 'prior_year_ASP_extension_endpoint_results_initial.json', 'no_new_valuation': True, 'interpretation_boundary': 'These are numerical feasible witness extensions. Feasible old endpoints prove those values remain possible under the added2025constraints. Failed endpoint extensions alone do not locate a new global extremum. No empirical probability or actualQ4ASP is implied.'}
(root / 'prior_year_ASP_extension_results.json').write_text(json.dumps(output, indent=2) + '\n')
print('INTERIOR',interior_attempts)
for r in results:
    print(r['roughly_flat_band'], r['old_endpoint'], r['status'])
    if 'carryover' in r:
        print(r['carryover'])
        print(r['ratio_and_direction_checks'])

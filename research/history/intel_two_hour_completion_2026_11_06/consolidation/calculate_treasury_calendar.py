from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import math

OUT = Path(__file__).resolve().parent
BASE = OUT.parents[1]
FILES = {
    'policy': OUT / 'treasury_calendar_policy_before_calculation.json',
    'annual_treasury': BASE / 'intel_competition_screen_2026_11_04/financial_claims_and_treasury_policy_2026_11_04.json',
}
HASHES = {k: hashlib.sha256(p.read_bytes()).hexdigest() for k, p in FILES.items()}
DATA = {k: json.loads(p.read_text()) for k, p in FILES.items()}
POLICY = DATA['policy']
ANNUAL = DATA['annual_treasury']['treasury_2027_2030']
FIELDS = {
    'ordinary_cash_interest_B': 'ordinary_interest_weights',
    'capitalized_cash_interest_inside_total_PPE_B': 'capitalized_interest_weights',
    'cash_interest_income_B': 'cash_interest_income_weights',
    'government_escrow_cash_B': 'escrow_cash_weights',
}


def calendar(name: str) -> dict:
    weights = POLICY['policy'][name]
    rows, annual_checks = [], []
    for index, year in enumerate(ANNUAL['years']):
        principal = [0., 0., 0., 0.]
        events = {q: [] for q in range(1, 5)}
        for instrument in POLICY['instruments']:
            if instrument['year'] != year:
                continue
            month = instrument['month']
            if name == 'concentrated_cash_stress' and instrument['earliest_optional_tender_month']:
                month = instrument['earliest_optional_tender_month']
            quarter = (month - 1) // 3 + 1
            principal[quarter - 1] += instrument['principal_B']
            events[quarter].append({**instrument, 'selected_cash_month': month})
        residual = ANNUAL['scheduled_principal_B'][index] - math.fsum(principal)
        assert abs(residual) < 1e-12
        acquisition_weights = weights.get(f'Classiq_{year}_weights', [0., 0., 0., 0.])
        cumulative = 0.
        annual_rows = []
        for q in range(1, 5):
            row = {'year': year, 'quarter': q, 'scheduled_principal_B': principal[q - 1], 'principal_events': events[q]}
            for field, weight_key in FIELDS.items():
                assert abs(sum(weights[weight_key]) - 1) < 1e-12
                row[field] = ANNUAL[field][index] * weights[weight_key][q - 1]
            row['Classiq_cash_B'] = ANNUAL['Classiq_cash_B'][index] * acquisition_weights[q - 1]
            row['net_treasury_cash_before_tax_shields_and_operating_cash_B'] = (
                row['cash_interest_income_B'] + row['government_escrow_cash_B']
                - row['ordinary_cash_interest_B'] - row['capitalized_cash_interest_inside_total_PPE_B']
                - row['Classiq_cash_B'] - row['scheduled_principal_B']
            )
            cumulative += row['net_treasury_cash_before_tax_shields_and_operating_cash_B']
            row['within_year_cumulative_treasury_cash_B'] = cumulative
            annual_rows.append(row)
        checks = {'year': year, 'unlocated_principal_B': residual}
        for field in [*FIELDS, 'Classiq_cash_B', 'scheduled_principal_B']:
            error = math.fsum(r[field] for r in annual_rows) - ANNUAL[field][index]
            assert abs(error) < 1e-12
            checks[f'{field}_annual_sum_error'] = error
        annual_checks.append(checks)
        rows.extend(annual_rows)
    return {'name': name, 'quarterly_rows': rows, 'annual_reconciliation': annual_checks}


base = calendar('uniform_base')
stress = calendar('concentrated_cash_stress')
comparison = []
for b, s in zip(base['quarterly_rows'], stress['quarterly_rows']):
    delta = s['within_year_cumulative_treasury_cash_B'] - b['within_year_cumulative_treasury_cash_B']
    comparison.append({'year': b['year'], 'quarter': b['quarter'], 'stress_minus_base_cumulative_treasury_cash_B': delta})
    if b['quarter'] == 4:
        assert abs(delta) < 1e-12
assert all(hashlib.sha256(p.read_bytes()).hexdigest() == HASHES[k] for k, p in FILES.items())
result = {
    'computed_utc': datetime.now(timezone.utc).isoformat(),
    'input_hashes': HASHES,
    'calendar_basis': 'Calendar quarters, with timing assumptions separated from disclosed principal dates.',
    'source_anchored_principal_calendar': [
        {'year': y, 'quarterly_principal_B': [r['scheduled_principal_B'] for r in base['quarterly_rows'] if r['year'] == y]}
        for y in ANNUAL['years']
    ],
    'base': base,
    'concentrated_timing_stress': stress,
    'within_year_comparison': comparison,
    'greatest_extra_interim_treasury_cash_need_B': -min(r['stress_minus_base_cumulative_treasury_cash_B'] for r in comparison),
    'scope_limit': 'This is an incremental treasury timing calendar, not a bank-liquidity or solvency result. Root must combine it with operating cash, capital receipts, taxes, economic SBC and minority reservations. Any actual interim draw changes interest and needs a financing-consistent rerun.',
    'verification': {'all_annual_inputs_preserved': True, 'all_principal_located_to_source_month': True, 'all_year_end_timing_differences_zero': True, 'all_frozen_input_hashes_unchanged': True},
}
(OUT / 'quarterly_treasury_calendar.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps({
    'principal_calendar': result['source_anchored_principal_calendar'],
    'greatest_extra_interim_treasury_cash_need_B': result['greatest_extra_interim_treasury_cash_need_B'],
    'within_year_comparison': comparison,
    'checks': result['verification'],
}, indent=2))

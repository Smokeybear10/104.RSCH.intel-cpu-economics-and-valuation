from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import math

OUT = Path(__file__).resolve().parent
FILES = {
    'policy': OUT / 'coupon_timing_policy_before_calculation.json',
    'cash': OUT.parent / 'root/quarterly_cash_results.json',
    'independent_audit': OUT / 'independent_quarterly_cash_audit.json',
}
HASHES = {name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in FILES.items()}
P, CASH, AUDIT = [json.loads(FILES[name].read_text()) for name in FILES]
assert AUDIT['all_compared_values_match']
assert AUDIT['input_hashes']['quarterly_result'] == HASHES['cash']
ANNUAL = P['annual_cash_interest_B']


def minimum(rows: list[dict]) -> dict:
    row = min(rows, key=lambda item: item['ending_cash_B'])
    return {'year': row['year'], 'quarter': row['quarter'], 'economic_cash_B': row['ending_cash_B'],
            'headroom_over_owned_20B_buffer_B': row['ending_cash_B'] - 20,
            'additional_liquidity_for_owned_buffer_B': max(0, 20 - row['ending_cash_B']),
            'negative_cash': row['ending_cash_B'] < 0}


known, details = {}, []
for year in range(2027, 2031):
    payments = [0.] * 4
    for note in P['verified_subset']:
        for month in note['coupon_months']:
            if (year, month) > (note['maturity_year'], note['maturity_month']):
                continue
            amount = note['principal_B'] * note['annual_coupon_rate'] / 2
            quarter = (month - 1) // 3
            payments[quarter] += amount
            details.append({'year': year, 'month': month, 'quarter': quarter + 1,
                            'cash_coupon_B': amount, 'note': note})
    assert math.fsum(payments) < ANNUAL
    known[year] = payments


def control(case: str, residual_weights: list[float], all_interest_q1: bool = False, tax_shield_q4: bool = False) -> dict:
    source = CASH[case]['quarterly_rows']
    rows = []
    for year in range(2027, 2031):
        residual = ANNUAL - math.fsum(known[year])
        payments = [ANNUAL, 0, 0, 0] if all_interest_q1 else [known[year][q] + residual * residual_weights[q] for q in range(4)]
        assert abs(math.fsum(payments) - ANNUAL) < 1e-12
        year_rows = [r for r in source if r['year'] == year]
        original_interest = math.fsum(r['ordinary_interest_B'] + r['capitalized_interest_B'] for r in year_rows)
        assert abs(original_interest - ANNUAL) < 1e-12
        annual_shield = math.fsum(r['financing_shield_B'] for r in year_rows)
        cumulative_delta = 0.
        for q, old in enumerate(year_rows):
            delta = old['ordinary_interest_B'] + old['capitalized_interest_B'] - payments[q]
            if tax_shield_q4:
                delta += (annual_shield if q == 3 else 0) - old['financing_shield_B']
            cumulative_delta += delta
            rows.append({'year': year, 'quarter': q + 1, 'known_coupon_B': known[year][q],
                         'total_cash_interest_B': payments[q], 'year_to_date_cash_change_B': cumulative_delta,
                         'ending_cash_B': old['ending_cash_B'] + cumulative_delta})
        assert abs(cumulative_delta) < 1e-12
    return {'minimum': minimum(rows), 'quarterly_rows': rows, 'all_year_end_cash_unchanged': True,
            'maximum_absolute_interim_change_B': max(abs(r['year_to_date_cash_change_B']) for r in rows)}


cases = {
    'source_coupons_plus_uniform_residual_base': control('base', [.25] * 4),
    'source_coupons_plus_Q1_Q3_residual_stress': control('concentrated_timing_stress', [.5, 0, .5, 0]),
    'source_coupons_plus_Q1_Q3_residual_stress_tax_shield_Q4': control('concentrated_timing_stress', [.5, 0, .5, 0], tax_shield_q4=True),
    'all_annual_interest_in_Q1_base_bound': control('base', [1, 0, 0, 0], all_interest_q1=True),
    'all_annual_interest_in_Q1_concentrated_bound': control('concentrated_timing_stress', [1, 0, 0, 0], all_interest_q1=True),
}
output = {
    'calculated_utc': datetime.now(timezone.utc).isoformat(),
    'input_hashes': HASHES,
    'method': 'Independent coupon calculation from stated principal, exact coupon and payment months. Adjust previously independently audited quarterly economic cash by cumulative payment-timing difference. No root function import or annual value change.',
    'source_coupon_schedule': {year: {'known_quarterly_coupon_B': values,
                                    'known_annual_coupon_B': math.fsum(values),
                                    'coverage_of_annual_cash_interest_envelope': math.fsum(values) / ANNUAL,
                                    'unmodeled_annual_residual_B': ANNUAL - math.fsum(values)} for year, values in known.items()},
    'source_instrument_payments': details,
    'cases': cases,
    'conclusions': [
        'Uniform quarterly interest timing does not create the base-case liquidity conclusion: even paying the entire annual cash-interest envelope in Q1 preserves the owned 20B buffer.',
        'The concentrated stress already pays all annual interest before Q4. Source-verified November and December coupons shift cash outflow later and modestly improve its Q3 trough; they do not remove the buffer shortfall.',
        'The stress retains positive economic cash. The 20B threshold is an analyst buffer, not a disclosed covenant, mandatory borrowing trigger or probability-calibrated failure point.',
        'This is a partial coupon-informed timing control, not a full forecast of every debt instrument, interest-rate swap, prepayment or capitalization designation. The unmodeled residual is explicitly allocated bookkeeping.',
        'No new financing, financing cost, valuation uplift or additional grant-receivable charge is introduced.'
    ],
    'verification': {'annual_interest_fixed_2_6B': True, 'all_year_end_cash_unchanged': True,
                     'base_matches_independently_audited_source': True,
                     'inputs_unchanged': all(hashlib.sha256(path.read_bytes()).hexdigest() == HASHES[name] for name, path in FILES.items())},
}
(OUT / 'coupon_timing_controls.json').write_text(json.dumps(output, indent=2) + '\n')
print(json.dumps({'schedule': output['source_coupon_schedule'], 'cases': {name: case['minimum'] for name, case in cases.items()}, 'verification': output['verification']}, indent=2))

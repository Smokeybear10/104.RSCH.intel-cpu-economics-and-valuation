from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import math

OUT = Path(__file__).resolve().parent
BASE = OUT.parents[1]
FILES = {
    'policy': OUT / 'mobileye_grant_policy_before_calculation.json',
    'model': BASE / 'pricing_and_competition_review_2026_11_04/intel_ASP20_mature_margin35_valuation.json',
    'cash_policy': BASE / 'intel_competition_screen_2026_11_04/cash_conversion_policy_2026_11_04.json',
    'corporate_policy': BASE / 'intel_competition_screen_2026_11_04/corporate_other_policy.json',
}
HASHES = {k: hashlib.sha256(p.read_bytes()).hexdigest() for k, p in FILES.items()}
DATA = {k: json.loads(p.read_text()) for k, p in FILES.items()}
P = DATA['policy']['analyst_policy']
MODEL = {r['year']: r for r in DATA['model']['annual_operating_rows']}


def cohorts(lag: int, include_opening_rsu: bool = True) -> list[dict]:
    recognized = {
        y: P['2027_to2030_annual_ordinary_grant_B'] * (1.03 ** max(0, y - 2030))
        for y in range(2027, 2042)
    }
    recognized[2026] = P['FY2026_cohort_ordinary_B']
    if include_opening_rsu:
        recognized[2026] += P['FY2026_cohort_RSU_related_B']
    asset = P['opening_2026_receivable_for_this_new_law_B']
    rows = []
    for y in range(2026, 2042):
        opening = asset
        cash = recognized.get(y - lag, 0.0)
        asset += recognized[y] - cash
        change = asset - opening
        identity_error = opening + recognized[y] - cash - asset
        assert abs(identity_error) < 1e-12
        assert asset >= 0
        r = {
            'year': y,
            'opening_grant_receivable_B': opening,
            'grant_already_recognized_in_operating_profit_B': recognized[y],
            'grant_realization_B': cash,
            'closing_grant_receivable_B': asset,
            'grant_receivable_cash_use_B': change,
            'receivable_identity_error_B': identity_error,
        }
        if y >= 2027:
            r['current_combined_operating_capital_cash_use_B'] = MODEL[y]['WC_cash_use_B']
            r['residual_operating_capital_cash_use_after_grant_allocation_B'] = MODEL[y]['WC_cash_use_B'] - change
            r['base_additional_cash_use_B'] = 0.0
            r['unfunded_grant_stress_cash_delta_B'] = -change
            r['cash_envelope_allocation_error_B'] = (
                r['residual_operating_capital_cash_use_after_grant_allocation_B']
                + change - MODEL[y]['WC_cash_use_B']
            )
            assert abs(r['cash_envelope_allocation_error_B']) < 1e-12
            assert r['residual_operating_capital_cash_use_after_grant_allocation_B'] > 0
        rows.append(r)
    assert abs(rows[1]['opening_grant_receivable_B'] - recognized[2026]) < 1e-12
    return rows


def operating_pv(cash: dict, endpoint: int) -> dict:
    rate = .11555
    explicit = math.fsum(cash.get(y, 0.) / (1 + rate) ** (y - endpoint) for y in range(endpoint + 1, 2041))
    terminal = cash[2041] / (rate - .03) / (1 + rate) ** (2040 - endpoint)
    assert abs(cash[2041] - cash[2040] * 1.03) < 1e-12
    return {
        'endpoint': endpoint,
        'operating_PV_delta_B': explicit + terminal,
        'per_share_operating_PV_delta_USD': (explicit + terminal) / 5.51,
        'scope': 'Isolated operating cash present value, with financing, opening cash, cash taxes and minority reserve held fixed. Not a revised stock target or endpoint treasury reconciliation.',
    }


base = cohorts(2)
by_year = {r['year']: r for r in base}
variants = []
for name, lag, opening_rsu in [('three_year_collection_lag', 3, True), ('four_year_collection_lag', 4, True), ('ordinary_opening_receivable_only', 2, False)]:
    rows = cohorts(lag, opening_rsu)
    cash_deltas = {r['year']: by_year[r['year']]['grant_receivable_cash_use_B'] - r['grant_receivable_cash_use_B'] for r in rows}
    variants.append({
        'name': name,
        'rows': rows,
        'cash_delta_vs_two_year_lag_if_residual_operating_capital_use_is_fixed': cash_deltas,
        'operating_PV_deltas': [operating_pv(cash_deltas, y) for y in (2026, 2030)],
    })

unfunded = {r['year']: r.get('unfunded_grant_stress_cash_delta_B', 0.) for r in base}
observed = DATA['policy']['observed_and_guided_inputs_B']
profit_bridge = {
    'FY2026_Mobileye_revenue_guidance_midpoint_B': (observed['FY2026_Mobileye_revenue_guidance_low'] + observed['FY2026_Mobileye_revenue_guidance_high']) / 2,
    'FY2026_Mobileye_adjusted_operating_profit_guidance_midpoint_B': (observed['FY2026_Mobileye_adjusted_operating_profit_low'] + observed['FY2026_Mobileye_adjusted_operating_profit_high']) / 2,
    'normalized_AllOther_segment_profit_B': .700,
    'owned_Mobileye_component_before_ordinary_grant_B': .400 - .190,
    'owned_ordinary_grant_component_within_AllOther_B': .190,
    'owned_residual_IMS_startups_other_profit_B': .700 - .400,
    'Q3_AllOther_minus_standalone_Mobileye_adjusted_profit_B': .179 - .089,
    'nine_months_AllOther_minus_standalone_Mobileye_adjusted_profit_B': .511 - .339,
    'Q3_residual_profit_annualized_B': (.179 - .089) * 4,
    'nine_months_residual_profit_annualized_B': (.511 - .339) * 4 / 3,
    'status': 'Component reasonableness check. Intel and standalone Mobileye reporting scopes are not exactly identical; the residual is not a disclosed IMS profit forecast.',
}
profit_bridge['AllOther_gross_revenue_less_Mobileye_guidance_midpoint_B'] = 2.8 - profit_bridge['FY2026_Mobileye_revenue_guidance_midpoint_B']
assert abs(profit_bridge['owned_Mobileye_component_before_ordinary_grant_B'] + profit_bridge['owned_ordinary_grant_component_within_AllOther_B'] + profit_bridge['owned_residual_IMS_startups_other_profit_B'] - .7) < 1e-12
assert all(hashlib.sha256(p.read_bytes()).hexdigest() == HASHES[k] for k, p in FILES.items())

result = {
    'computed_utc': datetime.now(timezone.utc).isoformat(),
    'input_hashes': HASHES,
    'base_rows': base,
    'profit_component_check': profit_bridge,
    'base_valuation_change_USD': 0.0,
    'unfunded_grant_stress_operating_PV_deltas': [operating_pv(unfunded, y) for y in (2026, 2030)],
    'collection_controls': variants,
    'integration_recommendation': [
        'Break the existing operating-capital cash use into grant receivable change and residual other operating-capital use. Sum remains exactly the prior envelope.',
        'Opening 2027 is an estimated 208M grant asset: approximately 190M ordinary plus 18M already recognized RSU-linked benefit. There is no 2025 cohort for this law.',
        'The 2027 asset build is 190M, not 398M. In 2028 the estimated 208M old cohort is collected against 190M newly accrued, releasing 18M; do not count the collection again as a separate subsidy.',
        'Base 0.7B Other profit contains the 190M ordinary benefit. Keep that assumption visible. A future loss of eligibility changes EBIT and cohort cash simultaneously; it is not only a collection-delay stress.',
        'Do not claim every cohort is contractually payable exactly two years later. Full settlement then is an owned timing approximation to guidance that collections begin in 2028.',
        'Do not apply a second Mobileye SBC expense or a second minority haircut. Intel central economic SBC and aggregate NCI reserve already cover these scopes.',
        'No extra valuation credit is supported by this work. A separate cash deduction requires showing that the original receivables budget excluded this asset or is fully consumed by other uses.',
    ],
    'verification': {
        'all_cohort_and_budget_identities_pass': True,
        'all_remaining_aggregate_operating_capital_budgets_positive': True,
        'all_terminal_delta_series_grow_at_three_percent': True,
        'all_source_hashes_unchanged': True,
        'base_no_incremental_EBIT_or_cash': True,
    },
}
(OUT / 'mobileye_grant_cohort_diagnostic.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps({
    'base_2027_to2032': [r for r in base if 2027 <= r['year'] <= 2032],
    'profit_component_check': profit_bridge,
    'unfunded_stress': result['unfunded_grant_stress_operating_PV_deltas'],
    'checks': result['verification'],
}, indent=2))

import hashlib
import json
from datetime import date, datetime, timezone
from pathlib import Path


OUT = Path(__file__).resolve().parent
POLICY = json.loads((OUT / 'policy_before_calculation.json').read_text())
INPUTS = {}
for name, source in POLICY['inputs'].items():
    path = Path(source['path'])
    assert hashlib.sha256(path.read_bytes()).hexdigest() == source['sha256']
    INPUTS[name] = json.loads(path.read_text())
SHARES = 5.51


def funded_case(quarterly: list, rate: float, tax: float) -> dict:
    debt = 0.0
    financing_cash = 0.0
    pretax_npv = 0.0
    shield_npv = 0.0
    rows = []
    quarter_rate = rate / 4
    for period, original in enumerate(quarterly, 1):
        opening_debt = debt
        cash_before_new_financing = original['ending_cash_B'] + financing_cash
        net_rate = quarter_rate * (1 - tax)
        needed = 20 - cash_before_new_financing + opening_debt * net_rate
        draw = max(needed / (1 - net_rate), 0)
        debt += draw
        interest = debt * quarter_rate
        tax_cash = interest * tax
        cash_before_repayment = cash_before_new_financing + draw - interest + tax_cash
        repayment = min(max(cash_before_repayment - 20, 0), debt)
        debt -= repayment
        financing_cash += draw - repayment - interest + tax_cash
        ending_cash = original['ending_cash_B'] + financing_cash
        pretax_npv += draw / (1 + quarter_rate) ** (period - 1)
        pretax_npv -= (interest + repayment) / (1 + quarter_rate) ** period
        shield_npv += tax_cash / (1 + quarter_rate) ** period
        assert ending_cash >= 20 - 1e-10
        assert debt <= 5 + 1e-10
        rows.append({
            'year': original['year'], 'quarter': original['quarter'],
            'no_draw_cash_B': original['ending_cash_B'], 'opening_revolver_B': opening_debt,
            'start_quarter_draw_B': draw, 'full_quarter_interest_B': interest,
            'conditional_cash_tax_benefit_B': tax_cash, 'end_quarter_repayment_B': repayment,
            'end_quarter_revolver_B': debt, 'end_quarter_cash_B': ending_cash,
            'net_cash_minus_revolver_delta_B': financing_cash - debt,
        })
    after_tax_cost = sum(r['full_quarter_interest_B'] - r['conditional_cash_tax_benefit_B'] for r in rows)
    assert abs(financing_cash - debt + after_tax_cost) < 1e-10
    assert abs(pretax_npv + debt / (1 + quarter_rate) ** len(rows)) < 1e-10
    assert debt < 1e-10
    used = [r for r in rows if r['start_quarter_draw_B'] > 1e-10 or r['opening_revolver_B'] > 1e-10]
    peak = max(r['opening_revolver_B'] + r['start_quarter_draw_B'] for r in rows)
    last = used[-1] if used else None
    if last:
        assert (last['year'], last['quarter']) < (2029, 3)
    return {
        'annual_simple_rate': rate, 'immediate_cash_tax_benefit_fraction': tax,
        'minimum_funded_quarter_cash_B': min(r['end_quarter_cash_B'] for r in rows),
        'peak_revolver_B': peak, 'peak_share_of_total15B_capacity': peak / 15,
        'peak_share_of_smaller5B_facility': peak / 5,
        'first_draw_period': f"Q{used[0]['quarter']} {used[0]['year']}" if used else None,
        'fully_repaid_period': f"Q{last['quarter']} {last['year']}" if last else None,
        'fully_repaid_before_both_disclosed_maturities': True,
        'total_gross_interest_B': sum(r['full_quarter_interest_B'] for r in rows),
        'total_conditional_cash_tax_benefit_B': sum(r['conditional_cash_tax_benefit_B'] for r in rows),
        'total_after_tax_interest_B': after_tax_cost,
        'ending_revolver_2030_B': debt,
        'Dec2030_equity_value_delta_B': financing_cash - debt,
        'Dec2030_per_share_delta_USD': (financing_cash - debt) / SHARES,
        'paired_pretax_financing_NPV_at_assumed_loan_rate_B': pretax_npv,
        'conditional_tax_shield_NPV_at_assumed_loan_rate_B': shield_npv,
        'conditional_tax_shield_per_share_USD': shield_npv / SHARES,
        'headline_Dec2026_planning_adjustment_credited_USD': 0,
        'quarterly_rows': rows,
    }


def main() -> None:
    overlays = INPUTS['quarterly_stresses']['cases']
    output = {'computed_utc': datetime.now(timezone.utc).isoformat(),
              'policy_sha256': hashlib.sha256((OUT / 'policy_before_calculation.json').read_bytes()).hexdigest(),
              'inputs': POLICY['inputs'], 'cases': {}}
    for name, timing_cases in overlays.items():
        variants = []
        for timing, stress in timing_cases.items():
            for rate in POLICY['rates']:
                for tax in POLICY['cash_tax_benefits']:
                    row = funded_case(stress['quarterly_rows'], rate, tax)
                    row['timing'] = timing
                    row['no_draw_minimum_cash_B'] = stress['minimum_quarter_cash_B']
                    row['no_draw_buffer_shortfall_B'] = stress['buffer_shortfall_B']
                    targets = []
                    for value in INPUTS['stress_valuations']['cases']:
                        matches = ('terminal_ROC_assumption' not in value) == name.startswith('one_quarter')
                        if not matches:
                            continue
                        new_target = value['target2030_USD'] + row['Dec2030_per_share_delta_USD']
                        years = (date(2030, 12, 31) - date(2026, 11, 6)).days / 365.25
                        targets.append({'case': value['case'], 'asset_rate': value['rate'],
                                        'terminal_ROC': value.get('terminal_ROC_assumption'),
                                        'original_Dec2030_target_USD': value['target2030_USD'],
                                        'funded_Dec2030_target_USD': new_target,
                                        'price_return_from_Nov6_56_28': (new_target / 56.28) ** (1 / years) - 1,
                                        '12pct_return_entry_ceiling_Nov6_USD': new_target / 1.12 ** years})
                    row['target_effects'] = targets
                    variants.append(row)
        output['cases'][name] = variants
    output['small_claim_mapping_checks'] = {
        'net_other_assets_identity_B': 8.798 + .478 - 3.1 - .459 - .215 - 1,
        'reported_tax_receivables_B': 7.4 + 2.5,
        'modeled_old_receivables_later_collections_B': sum(r['old_credit_collection_B'] for r in INPUTS['active_case']['annual_rows'].values()),
        'modeled_Q4_2026_collection_B': 1,
        'unallocated_reported_tax_receivable_residual_B': .9,
        'residual_face_value_per_share_ceiling_USD': .9 / SHARES,
        'residual_hypothetical2027_collection_PV_per_share_10_625pct_USD': .9 / 1.10625 / SHARES,
        'residual_status': 'Mapping residual only. Reported balance is primarily, not entirely, AMIC; Q4 CFO and ordinary tax budgets are not decomposed enough to exclude overlap. No automatic correction credited.',
        'debt_fair_value_gross_difference_B': 50.134 - 43.4,
        'debt_fair_value_gross_difference_per_share_USD': (50.134 - 43.4) / SHARES,
        'debt_status': 'Sept26 gross carrying-to-fair-value mark only; not a matched Dec2026 or Dec2030 financing bridge. Do not credit as corrected value.',
        'SLP_face_minus_carrying_B': .5 - .478,
        'SLP_face_minus_carrying_per_share_USD': (.5 - .478) / SHARES,
        'SLP_status': 'Collection is conversion of a recognized asset; adding cash requires removing receivable. Face accretion is not a fresh .5B asset.',
        'each_additional_1M_cash_fee_target_cost_USD_per_share_before_tax': .001 / SHARES,
        'justified_additional_asset_uplift_credited_B': 0,
    }
    output['interpretation'] = [
        'The funding response restores the chosen quarter-end buffer conditionally; it does not create operating value or improve the margin of safety.',
        'Facility capacity and maturities are reported; future availability and illustrative cost are not guaranteed.',
        'Tax shields are conditional and separately shown. No financing-derived uplift is credited to planning value.',
        'The after-tax interest reduction to the 2030 target is not a second interest subtraction from unlevered operating DCF.',
        'No contract fee schedule or daily liquidity path reconstructed. Original no-draw cases remain valid operating/timing stresses.',
    ]
    (OUT / 'claims_and_funding_results.json').write_text(json.dumps(output, indent=2) + '\n')
    for name, variants in output['cases'].items():
        for row in variants:
            if row['timing'] == 'concentrated_timing_stress':
                keys = ['annual_simple_rate', 'immediate_cash_tax_benefit_fraction', 'peak_revolver_B', 'total_after_tax_interest_B',
                        'Dec2030_per_share_delta_USD', 'first_draw_period', 'fully_repaid_period']
                print(name, {k: row[k] for k in keys})


if __name__ == '__main__':
    main()

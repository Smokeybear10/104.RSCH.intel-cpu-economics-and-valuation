import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


OUT = Path(__file__).resolve().parent
ns = {'__file__': str(OUT / 'extended_scenarios.py')}
exec((OUT / 'extended_scenarios.py').read_text().split('\ncases = ')[0], ns)
base_rows, host, packaging = ns['base_rows'], ns['host'], ns['packaging']
base = ns['value'](copy.deepcopy(base_rows))
funding = ns['funding']
policy_path = OUT / 'revenue_and_treasury_followup_policy.json'
policy = json.loads(policy_path.read_text())

historical = []
for quarter, products, foundry, external_foundry, other, eliminations, consolidated in [
    (1, 12.779, 5.421, .174, .628, 5.251, 13.577),
    (2, 15.139, 5.765, .293, .701, 5.477, 16.128),
    (3, 15.415, 6.697, .411, .692, 6.291, 16.513),
]:
    foundry_internal = foundry - external_foundry
    other_internal = eliminations - foundry_internal
    external_other = other - other_internal
    assert abs(products + external_foundry + external_other - consolidated) < 1e-12
    historical.append({'quarter2026': quarter, 'Products_external_B': products, 'Foundry_total_B': foundry, 'Foundry_external_B': external_foundry, 'Foundry_internal_B': foundry_internal, 'AllOther_segment_B': other, 'residual_Other_internal_B': other_internal, 'Other_external_B': external_other, 'consolidated_external_B': consolidated})

forecast = []
for year in [2027, 2028, 2029, 2030, 2031, 2040, 2041]:
    p, h = packaging[year], host[year]
    forecast.append({'year': year, 'Products_B': h['Products_revenue_B'], 'AllOther_proxy_B': h['root_Other_revenue_for_capital_denominator_B'], 'gross_packaging_B': p['gross_external_packaging_revenue_B'], 'shadow_packaging_B': p['existing_embedded_packaging_revenue_allowance_B'], 'existing_capital_denominator_B': base_rows[year]['capital_denominator_revenue_B'], 'sum_with_gross_packaging_before_unknown_legacy_and_Other_eliminations_B': h['Products_revenue_B'] + h['root_Other_revenue_for_capital_denominator_B'] + p['gross_external_packaging_revenue_B']})

unit_rows = copy.deepcopy(base_rows)
for year, row in unit_rows.items():
    if year < 2031:
        continue
    delta_revenue = .03 * 1.03 ** (year - 2031)
    incremental_investment = delta_revenue / .8
    row['net_operating_investment_B'] += incremental_investment
    row['WC_cash_use_B'] += .1 * delta_revenue
    row['physical_capex_B'] += incremental_investment - .1 * delta_revenue
    ns['close_cash'](row)
unit_value = ns['value'](unit_rows)
closed_form2030 = -.03 / .8 / (.11555 - .03) / 5.51
assert abs(unit_value['values'][2030]['price_USD'] - base['values'][2030]['price_USD'] - closed_form2030) < 1e-12

base_yield = 1 / funding[2027]['opening_economic_cash_B']
controls = {}
for name, debt_control, cash_yield in [
    ('base_fixed_budgets', False, None),
    ('5_2pct_opening_debt_cost', True, None),
    ('constant_opening_cash_yield', False, base_yield),
    ('joint_consistency_control', True, base_yield),
    ('cash_yield_plus100bp_unit_exposure', False, base_yield + .01),
]:
    cash = funding[2027]['opening_economic_cash_B']
    debt = funding[2027]['opening_ordinary_debt_B']
    rows, shield_pv_delta = [], 0
    for year in range(2027, 2031):
        f, op = funding[year], base_rows[year]
        opening_cash, opening_debt = cash, debt
        total_interest = .052 * debt if debt_control else 2.6
        ordinary_interest = total_interest - 1
        assert ordinary_interest > 0
        income = cash * cash_yield if cash_yield is not None else 1
        shield_delta = op['tax_rate'] * (ordinary_interest - 1.6)
        shield = op['financing_shield_B'] + shield_delta
        assert 0 < shield < op['ordinary_operating_tax_B']
        owner = op['parent_unlevered_cash_B'] - total_interest + income * (1 - op['tax_rate']) + shield
        cash += owner + f['escrow_cash_B'] - f['Classiq_cash_B'] - f['principal_B']
        debt -= f['principal_B']
        shield_pv_delta += shield_delta / 1.11555 ** (year - 2026)
        assert cash > 20
        rows.append({'year': year, 'opening_economic_cash_B': opening_cash, 'opening_carrying_debt_B': opening_debt, 'cash_income_B': income, 'income_over_opening_economic_cash': income / opening_cash, 'total_cash_interest_B': total_interest, 'total_interest_over_opening_carrying_debt': total_interest / opening_debt, 'ordinary_cash_interest_B': ordinary_interest, 'capitalized_cash_interest_B': 1., 'financing_shield_B': shield, 'owner_cash_B': owner, 'ending_economic_cash_B': cash, 'ending_ordinary_debt_B': debt})
    cash_delta = cash - base['treasury'][2030]['ending_economic_cash_B']
    target = base['values'][2030]['price_USD'] + cash_delta / 5.51
    controls[name] = {'rows': rows, '2030_cash_delta_B': cash_delta, '2030_target_delta_USD': cash_delta / 5.51, '2030_target_USD': target, 'annual_price_return': (target / 52.22) ** (1 / ns['YEARS']) - 1, 'mechanical_Dec2026_APV_shield_term_delta_USD_not_full_fair_value_change': shield_pv_delta / 5.51, 'same2031_onward_operating_and_financing_values': True}
assert abs(controls['base_fixed_budgets']['2030_cash_delta_B']) < 1e-12

result = {'computed_utc': datetime.now(timezone.utc).isoformat(), 'policy_sha256': hashlib.sha256(policy_path.read_bytes()).hexdigest(), 'policy': policy, 'historical2026_external_sales_reconciliation': historical, 'forecast_known_series': forecast, 'missing_sales_identity': 'True consolidated external sales = existing modeled capital denominator + shadow packaging sales + remaining legacy external Foundry sales − AllOther internal sales. The final two series are not forecast; no public disclosure uniquely supplies them.', 'missing_revenue_unit_exposure': {'for_each1B_unmodeled2030_sales_growing3pct_from2031': {'additional2031_net_investment_B': .03 / .8, '2030_target_delta_USD': closed_form2030, 'Dec2026_planning_value_delta_USD': unit_value['values'][2026]['price_USD'] - base['values'][2026]['price_USD']}, 'known2B_shadow2030_stream_target_delta_USD': closed_form2030 * 2, 'flat_nominal_missing_sales_stream_incremental_growth_investment_B': 0, 'scope': 'No new EBIT; assumed existing costs/D&A cover ongoing production. Flat-sales maintenance sufficiency is not independently established. This is a derivative of the model rule, not an empirical bound on future Foundry scale or physical capital.'}, 'treasury_controls': controls, 'source_interest_diagnostics': {'Q3_2026_interest_income_B': .461, 'Q3_end_liquid_assets_B': 54.005, 'Q2_end_liquid_assets_B': 29.727, 'annualized_Q3_income_divided_by_end_liquidity_NOT_realized_yield': .461 * 4 / 54.005, 'annualized_Q3_income_divided_by_two_endpoint_average_NOT_realized_yield': .461 * 4 / ((54.005 + 29.727) / 2), 'YTD_cash_interest_excluding_capitalized_B': 1.088, 'YTD_accounting_capitalized_interest_B': .806, 'annualized_sum_cash_interest_and_accounting_capitalization_approx_B': (1.088 + .806) * 4 / 3, 'capitalized_interest_cash_vs_accounting_limit': 'Cashflowordinaryinterestplusaccountingcapitalization is a scalecheck, not an exact totalcash-interestreconstruction.', '2031_base_total_interest_B': 37.097 * .052, '2030_base_total_interest_B': 2.6}, 'debt_claim_scope': {'2025_face_principal_B': 47.235, 'known2026_scheduled_principal_paid_B': 2.5, '2026_new_senior_notes_B': 6.5, 'implied_Sep2026_face_principal_B': 51.235, 'Sep2026_carrying_debt_B': 50.134, 'face_minus_carrying_B': 1.101, 'designated_interest_rate_swap_liability_B': .690, 'paired_debt_fair_value_hedge_basis_adjustment_B': .690, 'remaining_face2030_after_selected_principal_B': 38.198, 'remaining_modeled_carrying_debt2030_B': 37.097, 'plain_face_minus_carrying_per_share_NOT_complete_correction_USD': 1.101 / 5.51, 'all_non_escrow_derivatives_net_before_collateral_B': .914 - (14.695 - 13.705), 'reported_debt_fair_value_B': 43.4, 'interpretation': 'Carrying/par-runoff is an acknowledged proxy. Replacingcarryingwithfaceorfairvaluealone would ignorehedges,collateral,andotherfinancialassets/claims. Differenceisnotautomaticallyanadditivevaluationcorrection. Fourannualprincipalbuckets include tender/remarketing obligations; choosingcashrepaymentratherthanrollover is a forecast,not theonlycontractualoutcome.'}}
(OUT / 'revenue_and_treasury_followup_results.json').write_text(json.dumps(result, indent=2) + '\n')
print('salesunit', json.dumps(result['missing_revenue_unit_exposure']))
for name, row in controls.items():
    print(name, 'cashdelta', row['2030_cash_delta_B'], 'target', row['2030_target_USD'], 'APVshielddelta', row['mechanical_Dec2026_APV_shield_term_delta_USD_not_full_fair_value_change'])

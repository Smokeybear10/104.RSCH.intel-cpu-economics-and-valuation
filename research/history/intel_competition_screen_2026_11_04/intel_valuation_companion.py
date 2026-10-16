import hashlib
import json
import math
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
POLICY_HASH = '128d7fb23fa3a29a3a490d29354e3a77bbb90dad50d7d8ee271e829cbca53137'


def read(name: str) -> dict:
    return json.loads((ROOT / name).read_text())


def digest(name: str) -> str:
    return hashlib.sha256((ROOT / name).read_bytes()).hexdigest()


def main() -> None:
    policy_name = 'root_valuation_execution_policy_v2.json'
    assert digest(policy_name) == POLICY_HASH
    policy = read(policy_name)
    assert policy['nominal_unlevered_operating_rate'] == .12
    assert policy['post2030_debt_policy']['total_cash_coupon_rate'] == .052
    assert policy['post2030_debt_policy']['capitalized_interest_within_total_B'] == 1.0
    assert policy['new_capitalized_interest_tax_basis']['annual_B_from2027'] == 1.0
    assert policy['new_capitalized_interest_tax_basis']['economic_tax_recovery_years'] == 8
    for name, expected in policy['input_hashes'].items():
        assert digest(name) == expected, name
    finite = read('integrated_product_to_cash_forecast_2026_11_04.json')
    products = {row['year']: row for row in read('product_operating_forecast_2026_11_04.json')['annual_rows']}
    continuation = read('post2030_operating_capital_policy.json')
    continuation_rows = read('post2030_capital_transition_addendum.json')['annual_rows']
    tax_policy = read('root_corporate_tax_credit_valuation_policy.json')
    finance = read('financial_claims_and_treasury_policy_2026_11_04.json')
    treasury_policy = finance['treasury_2027_2030']
    opening = finance['opening_2027_forecast']
    claims = finance['shares']['root_selected_economic_claims_B']
    other_assets = finance['other_assets_and_claims']['net_other_assets_B']
    new_basis = {int(y): value for y, value in tax_policy['AMIC_new_eligible_investment_basis_B'].items()}
    old_collections = {int(y): value for y, value in tax_policy['AMIC_existing_receivable_collection_B'].items()}
    credit_rate = tax_policy['AMIC_credit_rate']
    basis_loss_rate = tax_policy['AMIC_new_credit_basis_loss_cash_tax_rate']
    g = continuation['adopted_terminal_assumptions']['nominal_growth']
    rows = []
    for old in finite['annual_rows']:
        y = old['year']
        i = y - 2027
        bridge = old['consolidated_operating_profit_bridge_B']
        cash = old['cash_conversion_B']
        rows.append({
            'year': y,
            'external_revenue_B': products[y]['Products_revenue_B'] + 2.8,
            'operating_EBIT_after_SBC_B': bridge['consolidated_EBIT_after_recurring_SBC'],
            'operating_DA_B': cash['total_normalized_DA_addback'],
            'physical_capex_B': treasury_policy['physical_unlevered_PPE_B'][i],
            'delta_WC_B': cash['cash_working_capital_use_including_supplier_advances'],
            'all_in_lease_cash_B': 1.0,
            'minority_cash_reserve_B': cash['minority_owner_cash_reserve'],
            'original_owner_cash_before_incentives_B': cash['pre_capital_incentive_owner_cash_proxy'],
        })
    for old in continuation_rows:
        y = old['year']
        growth = (1 + g) ** (y - 2030)
        ebit = old['Products_operating_profit_B'] + old['Foundry_operating_profit_B'] + (.7 - 5.15) * growth
        rows.append({
            'year': y,
            'external_revenue_B': old['consolidated_external_revenue_for_capital_denominator_B'],
            'operating_EBIT_after_SBC_B': ebit,
            'operating_DA_B': old['total_normalized_DA_B'],
            'physical_capex_B': old['physical_operating_gross_PPE_excluding_capitalized_interest_B'],
            'delta_WC_B': old['cash_operating_WC_use_B'],
            'all_in_lease_cash_B': growth,
            'minority_cash_reserve_B': 1.3 * growth,
        })
    base2040 = rows[-1]
    rows.append({key: (2041 if key == 'year' else value * (1 + g)) for key, value in base2040.items()})
    for row in rows:
        y = row['year']
        tax_rate = tax_policy['ordinary_operating_cash_tax_rates'][str(y)]
        op_tax = tax_rate * max(0.0, row['operating_EBIT_after_SBC_B'])
        old_credit = old_collections.get(y, 0.0)
        new_credit = new_basis.get(y - 1, 0.0) * credit_rate
        basis_loss = new_basis.get(y, 0.0) * credit_rate * basis_loss_rate
        pretax_cash = row['operating_EBIT_after_SBC_B'] + row['operating_DA_B'] - row['physical_capex_B'] - row['delta_WC_B'] - row['all_in_lease_cash_B'] - row['minority_cash_reserve_B']
        row.update({
            'ordinary_operating_tax_rate': tax_rate,
            'ordinary_unlevered_cash_tax_B': op_tax,
            'unlevered_cash_before_capital_incentives_B': pretax_cash - op_tax,
            'old_capital_tax_receivable_collection_B': old_credit,
            'new_capital_credit_collection_B': new_credit,
            'new_credit_basis_loss_tax_charge_B': basis_loss,
            'parent_attributable_unlevered_cash_B': pretax_cash - op_tax + old_credit + new_credit - basis_loss,
        })

    by_year = {row['year']: row for row in rows}

    def capitalized_deduction(year: int) -> float:
        return math.fsum(1.0 / 8 for vintage in range(2027, year) if 1 <= year - vintage <= 8)

    cash_balance = opening['opening_liquid_assets_B']
    ordinary_debt = opening['opening_debt_B']
    additional_debt = 0.0
    funding = []
    for y in range(2027, 2032):
        op = by_year[y]
        rate = op['ordinary_operating_tax_rate']
        start_cash, start_debt = cash_balance, ordinary_debt
        if y <= 2030:
            i = y - 2027
            ordinary_interest = treasury_policy['ordinary_cash_interest_B'][i] + .06 * additional_debt
            capitalized_interest = treasury_policy['capitalized_cash_interest_inside_total_PPE_B'][i]
            income = treasury_policy['cash_interest_income_B'][i]
            principal = treasury_policy['scheduled_principal_B'][i]
            escrow = treasury_policy['government_escrow_cash_B'][i]
            acquisition = treasury_policy['Classiq_cash_B'][i]
        else:
            total_interest = .052 * ordinary_debt
            assert total_interest >= 1
            capitalized_interest = 1.0
            ordinary_interest = total_interest - capitalized_interest
            income, principal, escrow, acquisition = 1.0, 0.0, 0.0, 0.0
        depreciation_shield = rate * capitalized_deduction(y)
        ordinary_shield = rate * ordinary_interest
        assert ordinary_shield + depreciation_shield < op['ordinary_unlevered_cash_tax_B']
        owner_cash = op['parent_attributable_unlevered_cash_B'] - ordinary_interest - capitalized_interest + income * (1 - rate) + ordinary_shield + depreciation_shield
        original_reconciliation_error = None
        if y <= 2030:
            original_equivalent = op['unlevered_cash_before_capital_incentives_B'] - ordinary_interest - capitalized_interest + income * (1 - rate) + ordinary_shield
            original_reconciliation_error = original_equivalent - op['original_owner_cash_before_incentives_B'] + .06 * additional_debt * (1 - rate)
            assert abs(original_reconciliation_error) < 1e-10
        before_draw = cash_balance + owner_cash + escrow - acquisition - principal
        draw = max(0.0, treasury_policy['minimum_economic_liquidity_B'] - before_draw)
        assert y <= 2030 or draw == 0.0
        cash_balance = before_draw + draw
        ordinary_debt = ordinary_debt - principal + draw
        additional_debt += draw
        identity_error = cash_balance - start_cash - owner_cash - escrow + acquisition + principal - draw
        assert abs(identity_error) < 1e-10
        funding.append({
            'year': y, 'opening_economic_cash_B': start_cash, 'opening_ordinary_debt_B': start_debt,
            'ordinary_cash_interest_B': ordinary_interest, 'capitalized_cash_interest_B': capitalized_interest,
            'cash_interest_income_B': income, 'ordinary_interest_tax_benefit_B': ordinary_shield,
            'new_capitalized_interest_tax_deduction_B': capitalized_deduction(y),
            'capitalized_interest_depreciation_tax_benefit_B': depreciation_shield,
            'owner_cash_after_financing_and_capital_incentives_B': owner_cash,
            'government_escrow_financing_cash_B': escrow, 'Classiq_cash_B': acquisition,
            'scheduled_principal_B': principal, 'new_borrowing_B': draw,
            'ending_economic_cash_B': cash_balance, 'ending_ordinary_debt_B': ordinary_debt,
            'ending_net_cash_B': cash_balance - ordinary_debt,
            'cash_identity_error_B': identity_error, 'original_owner_cash_reconciliation_error_B': original_reconciliation_error,
        })
    funding_by_year = {row['year']: row for row in funding}
    debt2030 = funding_by_year[2030]['ending_ordinary_debt_B']
    finance_benefits = []
    for y in range(2027, 2042):
        rate = by_year[y]['ordinary_operating_tax_rate']
        ordinary_interest = funding_by_year[y]['ordinary_cash_interest_B'] if y <= 2030 else .052 * debt2030 - 1
        benefit = rate * (ordinary_interest + capitalized_deduction(y))
        assert 0 <= benefit < by_year[y]['ordinary_unlevered_cash_tax_B']
        finance_benefits.append({'year': y, 'ordinary_debt_cash_interest_B': ordinary_interest,
                                 'capitalized_interest_tax_deduction_B': capitalized_deduction(y),
                                 'conditional_financing_tax_benefit_B': benefit})

    def valuation(endpoint: int, rate: float) -> dict:
        op_explicit = math.fsum(row['parent_attributable_unlevered_cash_B'] / (1 + rate) ** (row['year'] - endpoint) for row in rows if endpoint < row['year'] <= 2040)
        operating_terminal_2040 = by_year[2041]['parent_attributable_unlevered_cash_B'] / (rate - g)
        operating_terminal_pv = operating_terminal_2040 / (1 + rate) ** (2040 - endpoint)
        benefit_explicit = math.fsum(row['conditional_financing_tax_benefit_B'] / (1 + rate) ** (row['year'] - endpoint) for row in finance_benefits if endpoint < row['year'] <= 2040)
        benefit_terminal = finance_benefits[-1]['conditional_financing_tax_benefit_B'] / rate / (1 + rate) ** (2040 - endpoint)
        if endpoint == 2026:
            cash, debt = opening['opening_liquid_assets_B'], opening['opening_debt_B']
            escrow_pv = math.fsum(row['government_escrow_financing_cash_B'] / (1 + rate) ** (row['year'] - endpoint) for row in funding if row['year'] <= 2030)
            acquisition_pv = math.fsum(row['Classiq_cash_B'] / (1 + rate) ** (row['year'] - endpoint) for row in funding if row['year'] <= 2030)
        else:
            cash = funding_by_year[endpoint]['ending_economic_cash_B']
            debt = funding_by_year[endpoint]['ending_ordinary_debt_B']
            escrow_pv = math.fsum(row['government_escrow_financing_cash_B'] / (1 + rate) ** (row['year'] - endpoint) for row in funding if endpoint < row['year'] <= 2030)
            acquisition_pv = math.fsum(row['Classiq_cash_B'] / (1 + rate) ** (row['year'] - endpoint) for row in funding if endpoint < row['year'] <= 2030)
        operating = op_explicit + operating_terminal_pv
        benefits = benefit_explicit + benefit_terminal
        value_before_financing_benefits = operating + cash - debt + other_assets + escrow_pv - acquisition_pv
        equity = value_before_financing_benefits + benefits
        price = equity / claims
        result = {
            'date': f'{endpoint}-12-31', 'operating_rate': rate,
            'explicit_operating_cash_PV_B': op_explicit, 'terminal_operating_value_at2040_B': operating_terminal_2040,
            'terminal_operating_PV_B': operating_terminal_pv, 'parent_attributable_operating_value_B': operating,
            'future_financing_tax_benefit_PV_B': benefits, 'economic_cash_B': cash, 'ordinary_debt_B': debt,
            'net_other_assets_B': other_assets, 'future_escrow_financing_PV_B': escrow_pv,
            'future_Classiq_cash_PV_B': acquisition_pv, 'equity_before_financing_tax_benefits_B': value_before_financing_benefits,
            'equity_with_financing_tax_benefits_B': equity, 'planning_claims_B': claims,
            'price_before_financing_tax_benefits_USD': value_before_financing_benefits / claims,
            'price_with_financing_tax_benefits_USD': price,
            'terminal_fraction_of_operating_value': operating_terminal_pv / operating,
        }
        if endpoint != 2026:
            years = (date(endpoint, 12, 31) - date.fromisoformat(policy['entry']['date'])).days / 365.25
            result['holding_years_from_entry'] = years
            result['annual_price_appreciation_from_entry'] = (price / policy['entry']['price_USD']) ** (1 / years) - 1
        return result

    values = {str(y): valuation(y, .12) for y in [2026, 2029, 2030, 2031]}
    controls = {str(rate): valuation(2030, rate) for rate in policy['rate_controls']}
    direct_tail = math.fsum(by_year[2041]['parent_attributable_unlevered_cash_B'] * (1 + g) ** (y - 2041) / 1.12 ** (y - 2040) for y in range(2041, 2542))
    assert abs(direct_tail - values['2030']['terminal_operating_value_at2040_B']) < 1e-9
    terminal_investment = by_year[2041]['physical_capex_B'] - by_year[2041]['operating_DA_B'] + by_year[2041]['delta_WC_B']
    implied = (by_year[2041]['external_revenue_B'] - by_year[2040]['external_revenue_B']) / .60
    assert abs(terminal_investment - implied) < 1e-9
    assert abs(by_year[2041]['parent_attributable_unlevered_cash_B'] / by_year[2040]['parent_attributable_unlevered_cash_B'] - 1.03) < 1e-12
    for name, expected in policy['input_hashes'].items():
        assert digest(name) == expected, name
    result = {
        'computed_utc': datetime.now(timezone.utc).isoformat(),
        'scope': 'Single owned Intel operating, treasury, tax-credit and claim case. Conditional valuation, not probability-weighted expected return or an exact GAAP/statutory financial model.',
        'policy': policy_name, 'policy_sha256': POLICY_HASH, 'source_hashes': policy['input_hashes'],
        'reproducer_sha256': digest(Path(__file__).name),
        'entry': policy['entry'], 'operating_rows': rows, 'treasury_rows': funding,
        'financing_tax_benefit_rows': finance_benefits, 'values_at12pct': values,
        'end2030_rate_controls': controls,
        'checks': {
            'terminal_cash_growth': by_year[2041]['parent_attributable_unlevered_cash_B'] / by_year[2040]['parent_attributable_unlevered_cash_B'] - 1,
            'terminal_reinvestment_identity_error_B': terminal_investment - implied,
            'direct501_year_operating_tail_error_B': direct_tail - values['2030']['terminal_operating_value_at2040_B'],
            'minimum_year_end_economic_cash_B': min(row['ending_economic_cash_B'] for row in funding),
            'total_new_borrowing_B': math.fsum(row['new_borrowing_B'] for row in funding),
            'all_frozen_inputs_unchanged': True,
        },
        'limitations': [
            'End2026 reference value is not current November3 fair value; it uses an owned Q4 cash forecast.',
            'Annual treasury is economic owner cash after cash-equivalent SBC and minority reserves, not a literal bank statement or peak intra-year funding test.',
            'The5.51B denominator, private investment carrying values, pension claim, ordinary debt carrying value and normalized interest/tax policies remain approximations.',
            'Capital productivity, terminal margins and successful product/Foundry recovery are owned forecasts, not verified future outcomes.',
            'New capital-credit eligibility/collection and basis-loss timing are forecasts; no perpetual AMIC subsidy is capitalized.',
            'Capitalized-interest tax recovery is a separate eight-year normalization, not reconstructed statutory asset pools.',
            'Classiq costs are included without a separately valued incremental acquisition franchise; future distributions or financing changes require a paired update.',
            'No competition-winning probability or stock direction is inferred by the script.',
        ],
    }
    output = ROOT / 'owned_intel_valuation_2026_11_04.json'
    output.write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    print(json.dumps({'file': str(output), 'sha256': digest(output.name), 'values_at12pct': values,
                      'rate_controls': controls, 'checks': result['checks']}, indent=2))


if __name__ == '__main__':
    main()

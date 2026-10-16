import hashlib
import json
import math
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
INPUTS = {
    'external_packaging_operating_policy_2026_11_04.json': '896ca70ede809c52d30ea3a4919b7ab84218e5ce8fc8e99fbc2a42fbe2e4fcbb',
    'funded_bull_valuation_2026_11_04.json': '5a55146ce8cd7d4b20f52b85997fd616aa05573aa373eddd3905f35429471521',
    'owned_intel_valuation_2026_11_04.json': '1fad8340551c55d5299762686c1c56238e30f4bd718c0dd1d2f9f553630f92ca',
    'root_valuation_execution_policy_v2.json': '128d7fb23fa3a29a3a490d29354e3a77bbb90dad50d7d8ee271e829cbca53137',
    'financial_claims_and_treasury_policy_2026_11_04.json': 'bd1a4748331e35289d92508ab1ce9b5a848535a85f5478e6124fa1d369b7fbea',
    'root_corporate_tax_credit_valuation_policy.json': '56b6a542e53ac6a239b7a2a89752420c0022218f132f499e50334fc04c9c8031',
}
ENTRY = {'date': '2026-11-04', 'price_USD': 58.11,
         'time': '10:43 ET', 'provenance': 'Root-supplied dated intraday reference; not a closing price or independently retrieved by this calculator.'}


def digest(name: str) -> str:
    return hashlib.sha256((ROOT / name).read_bytes()).hexdigest()


def read(name: str) -> dict:
    return json.loads((ROOT / name).read_text())


def main() -> None:
    for name, expected in INPUTS.items():
        assert digest(name) == expected, name
    program = read('external_packaging_operating_policy_2026_11_04.json')
    host = read('funded_bull_valuation_2026_11_04.json')
    base = read('owned_intel_valuation_2026_11_04.json')
    finance = read('financial_claims_and_treasury_policy_2026_11_04.json')
    treasury = finance['treasury_2027_2030']
    opening = finance['opening_2027_forecast']
    claims = finance['shares']['root_selected_economic_claims_B']
    other_assets = finance['other_assets_and_claims']['net_other_assets_B']
    originals = {r['year']: r for r in base['operating_rows']}
    increments = {r['year']: r for r in program['annual_rows']}
    assert set(increments) == set(range(2027, 2042))
    host_rows, rows = [], []
    for h in host['operating_rows']:
        y = h['year']
        old, inc = originals[y], increments[y]
        assert inc['incremental_customer_or_partner_funding_B'] == 0
        assert inc['incremental_new_tax_credit_B'] == 0
        net_ebit = inc['gross_program_EBIT_after_direct_DA_B'] - inc['existing_foundry_profit_overlap_B'] - inc['incremental_central_cost_including_SBC_B']
        assert abs(net_ebit - inc['net_incremental_operating_profit_B']) < 1e-12
        host_row = {
            'year': y, 'external_revenue_B': h['external_revenue_B'],
            'EBIT_after_economic_SBC_B': h['EBIT_after_corporate_SBC_B'],
            'DA_B': h['DA_B'], 'physical_cash_capex_B': h['physical_capex_B'],
            'WC_cash_use_B': h['WC_B'], 'lease_cash_B': old['all_in_lease_cash_B'],
            'minority_cash_B': old['minority_cash_reserve_B'],
            'tax_rate': old['ordinary_operating_tax_rate'],
            'old_credit_collection_B': old['old_capital_tax_receivable_collection_B'],
            'new_credit_collection_B': old['new_capital_credit_collection_B'],
            'credit_basis_loss_tax_B': old['new_credit_basis_loss_tax_charge_B'],
        }
        row = dict(host_row)
        for field, delta in {
            'external_revenue_B': inc['incremental_external_packaging_revenue_B'],
            'EBIT_after_economic_SBC_B': net_ebit,
            'DA_B': inc['incremental_DA_B'],
            'physical_cash_capex_B': inc['incremental_physical_cash_capex_B'],
            'WC_cash_use_B': inc['incremental_WC_cash_use_B'],
            'lease_cash_B': inc['incremental_lease_cash_B'],
            'minority_cash_B': inc['incremental_minority_cash_B'],
        }.items():
            row[field] += delta
        for r in [host_row, row]:
            r['ordinary_operating_tax_B'] = max(0, r['EBIT_after_economic_SBC_B']) * r['tax_rate']
            r['parent_unlevered_cash_B'] = (r['EBIT_after_economic_SBC_B'] - r['ordinary_operating_tax_B']
                + r['DA_B'] - r['physical_cash_capex_B'] - r['WC_cash_use_B']
                - r['lease_cash_B'] - r['minority_cash_B'] + r['old_credit_collection_B']
                + r['new_credit_collection_B'] - r['credit_basis_loss_tax_B'])
        assert abs(host_row['parent_unlevered_cash_B'] - h['parent_unlevered_cash_B']) < 1e-10
        row['incremental_unlevered_cash_vs_host_B'] = row['parent_unlevered_cash_B'] - host_row['parent_unlevered_cash_B']
        host_rows.append(host_row)
        rows.append(row)

    def capitalized_deduction(year: int) -> float:
        return math.fsum(1 / 8 for vintage in range(2027, year) if 1 <= year - vintage <= 8)

    def fund(operating: list) -> tuple:
        by_year = {r['year']: r for r in operating}
        cash, debt = opening['opening_liquid_assets_B'], opening['opening_debt_B']
        added_debt = 0.0
        funding = []
        for y in range(2027, 2032):
            r = by_year[y]
            before_cash, before_debt = cash, debt
            if y <= 2030:
                i = y - 2027
                interest = treasury['ordinary_cash_interest_B'][i] + treasury['fallback_new_debt_rate'] * added_debt
                capital_interest = treasury['capitalized_cash_interest_inside_total_PPE_B'][i]
                income = treasury['cash_interest_income_B'][i]
                principal = treasury['scheduled_principal_B'][i]
                escrow, acquisition = treasury['government_escrow_cash_B'][i], treasury['Classiq_cash_B'][i]
            else:
                capital_interest, interest = 1.0, .052 * debt - 1.0
                income, principal, escrow, acquisition = 1.0, 0.0, 0.0, 0.0
            shield = r['tax_rate'] * (interest + capitalized_deduction(y))
            assert 0 <= shield < r['ordinary_operating_tax_B']
            owner_cash = r['parent_unlevered_cash_B'] - interest - capital_interest + income * (1 - r['tax_rate']) + shield
            before_draw = cash + owner_cash + escrow - acquisition - principal
            draw = max(0, treasury['minimum_economic_liquidity_B'] - before_draw)
            assert y <= 2030 or draw == 0
            cash, debt = before_draw + draw, debt - principal + draw
            added_debt += draw
            identity = cash - before_cash - owner_cash - escrow + acquisition + principal - draw
            assert abs(identity) < 1e-10
            funding.append({'year': y, 'opening_economic_cash_B': before_cash, 'opening_ordinary_debt_B': before_debt,
                'ordinary_interest_B': interest, 'capitalized_interest_B': capital_interest, 'cash_income_B': income,
                'financing_tax_benefit_B': shield, 'owner_cash_after_financing_and_incentives_B': owner_cash,
                'escrow_cash_B': escrow, 'Classiq_cash_B': acquisition, 'principal_B': principal,
                'new_borrowing_B': draw, 'ending_economic_cash_B': cash, 'ending_ordinary_debt_B': debt,
                'ending_net_cash_B': cash - debt, 'cash_identity_error_B': identity})
        f = {r['year']: r for r in funding}
        shields = []
        for y in range(2027, 2042):
            interest = f[y]['ordinary_interest_B'] if y <= 2030 else .052 * f[2030]['ending_ordinary_debt_B'] - 1
            benefit = by_year[y]['tax_rate'] * (interest + capitalized_deduction(y))
            assert 0 <= benefit < by_year[y]['ordinary_operating_tax_B']
            shields.append({'year': y, 'financing_tax_benefit_B': benefit})
        return funding, shields

    host_funding, host_shields = fund(host_rows)
    funding, shields = fund(rows)

    def value(operating: list, financed: list, benefits: list, endpoint: int, rate: float) -> dict:
        by_year = {r['year']: r for r in operating}
        f = {r['year']: r for r in financed}
        explicit = math.fsum(r['parent_unlevered_cash_B'] / (1 + rate) ** (r['year'] - endpoint)
                             for r in operating if endpoint < r['year'] <= 2040)
        terminal = by_year[2041]['parent_unlevered_cash_B'] / (rate - .03) / (1 + rate) ** (2040 - endpoint)
        shield_pv = math.fsum(r['financing_tax_benefit_B'] / (1 + rate) ** (r['year'] - endpoint)
                              for r in benefits if endpoint < r['year'] <= 2040)
        shield_pv += benefits[-1]['financing_tax_benefit_B'] / rate / (1 + rate) ** (2040 - endpoint)
        cash = opening['opening_liquid_assets_B'] if endpoint == 2026 else f[endpoint]['ending_economic_cash_B']
        debt = opening['opening_debt_B'] if endpoint == 2026 else f[endpoint]['ending_ordinary_debt_B']
        escrow = math.fsum(r['escrow_cash_B'] / (1 + rate) ** (r['year'] - endpoint) for r in financed if endpoint < r['year'] <= 2030)
        acquisition = math.fsum(r['Classiq_cash_B'] / (1 + rate) ** (r['year'] - endpoint) for r in financed if endpoint < r['year'] <= 2030)
        equity = explicit + terminal + shield_pv + cash - debt + other_assets + escrow - acquisition
        price = equity / claims
        out = {'date': f'{endpoint}-12-31', 'operating_and_conditional_tax_benefit_discount_rate': rate,
            'explicit_operating_PV_B': explicit, 'terminal_operating_PV_B': terminal,
            'parent_operating_value_B': explicit + terminal, 'financing_tax_benefit_PV_B': shield_pv,
            'economic_cash_B': cash, 'ordinary_debt_B': debt, 'net_other_assets_B': other_assets,
            'future_escrow_cash_PV_B': escrow, 'future_Classiq_cash_PV_B': acquisition,
            'equity_B': equity, 'planning_claims_B': claims, 'price_USD': price,
            'terminal_share_of_operating_value': terminal / (explicit + terminal)}
        if endpoint > 2026:
            years = (date(endpoint, 12, 31) - date.fromisoformat(ENTRY['date'])).days / 365.25
            out.update({'years_from_intraday_entry_date': years,
                'annual_price_change_from_58_11': (price / ENTRY['price_USD']) ** (1 / years) - 1,
                'cumulative_price_change_from_58_11': price / ENTRY['price_USD'] - 1})
        return out

    def compare(endpoint: int, rate: float) -> dict:
        combined = value(rows, funding, shields, endpoint, rate)
        h = value(host_rows, host_funding, host_shields, endpoint, rate)
        return {'combined': combined, 'unchanged_host': h,
            'incremental_program_equity_B': combined['equity_B'] - h['equity_B'],
            'incremental_program_price_USD': combined['price_USD'] - h['price_USD'],
            'incremental_endpoint_cash_B': combined['economic_cash_B'] - h['economic_cash_B']}

    values = {str(y): compare(y, .12) for y in range(2026, 2032)}
    controls = {str(y): {str(r): compare(y, r) for r in [.11, .12, .13]} for y in [2026, 2030]}
    for y in [2026, 2029, 2030, 2031]:
        assert abs(values[str(y)]['unchanged_host']['price_USD'] - host['values_at12pct'][str(y)]['price_USD']) < 1e-10
    for r in [.11, .13]:
        assert abs(controls['2030'][str(r)]['unchanged_host']['price_USD'] - host['end2030_rate_controls'][str(r)]['price_USD']) < 1e-10
    for h in host['treasury_rows']:
        actual = next(r for r in host_funding if r['year'] == h['year'])
        assert abs(actual['ending_economic_cash_B'] - h['ending_economic_cash_B']) < 1e-10
    terminal_growth = rows[-1]['parent_unlevered_cash_B'] / rows[-2]['parent_unlevered_cash_B'] - 1
    assert abs(terminal_growth - .03) < 1e-12
    for name, expected in INPUTS.items():
        assert digest(name) == expected, name
    output = {
        'computed_utc': datetime.now(timezone.utc).isoformat(), 'input_hashes': INPUTS,
        'reproducer_sha256': digest(Path(__file__).name), 'entry': ENTRY,
        'scope': 'Frozen funded CPU absorption host plus hardware-selected incremental external packaging, net of explicit embedded revenue/profit overlap and fully charged program capital, working capital and central SBC. No operating inputs selected by this valuation calculator.',
        'annual_operating_rows': rows, 'treasury_rows': funding, 'financing_tax_benefit_rows': shields,
        'values_at12pct': values, 'rate_controls_2026_and_2030': controls,
        'checks': {'all_source_hashes_preserved': True, 'host_existing_outputs_reproduced': True,
            'minimum_annual_economic_cash_B': min(r['ending_economic_cash_B'] for r in funding),
            'total_new_debt_2027_2030_B': math.fsum(r['new_borrowing_B'] for r in funding if r['year'] <= 2030),
            'terminal_cash_growth': terminal_growth,
            'incremental_physical_capital_2027_2030_B': math.fsum(r['incremental_physical_cash_capex_B'] for r in increments.values() if r['year'] <= 2030),
            'incremental_WC_cash_2027_2030_B': math.fsum(r['incremental_WC_cash_use_B'] for r in increments.values() if r['year'] <= 2030)},
        'interpretation_limits': [
            'End2026 is a planning reference using forecast opening2027 financial balances, not measured Nov4 fair value or a predicted market price.',
            'Annual endpoint values describe a conditional intrinsic trajectory, not promised convergence dates or required short-cover dates. The competition asks for a three-to-five-year fundamental thesis; these early intrinsic references do not promise a market repricing date.',
            '12% remains the primary operating-risk judgment;11/13% controls also discount contingent financing tax benefits at those rates, without changing debt coupons.',
            'No extra AMIC, customer/partner funding, external wafer-foundry option, buyback, dividend, share issuance or capital reuse credit is added.',
            'Incremental packaging capital is not also charged the host0.60 turnover rule. Depreciation is included in operating profit and added back once; future program reinvestment follows its frozen1.0 turnover convention.',
            'Economic treasury includes cash-equivalent SBC/minority reserves; it is not a literal bank-cash forecast or a monthly liquidity test.',
            'The explicit packaging overlap, growth, margins and capital efficiency remain owned forecasts. The company conference transcript evidence is not independently primary-audio verified in the operating policy.',
        ],
    }
    path = ROOT / 'external_packaging_valuation_2026_11_04.json'
    path.write_text(json.dumps(output, indent=2, allow_nan=False) + '\n')
    print(json.dumps({'path': str(path), 'sha256': digest(path.name),
        'primary_table': {y: {'combined': v['combined']['price_USD'], 'host': v['unchanged_host']['price_USD'],
            'program_delta': v['incremental_program_price_USD'], 'cash_delta': v['incremental_endpoint_cash_B']} for y, v in values.items()},
        'controls': {y: {r: v['combined']['price_USD'] for r, v in vv.items()} for y, vv in controls.items()},
        'checks': output['checks']}, indent=2))


if __name__ == '__main__':
    main()

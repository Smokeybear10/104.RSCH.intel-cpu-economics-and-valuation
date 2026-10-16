import hashlib
import json
import math
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
INPUTS = {
    'owned_intel_valuation_2026_11_04.json': '1fad8340551c55d5299762686c1c56238e30f4bd718c0dd1d2f9f553630f92ca',
    'funded_bull_execution_policy.json': 'ae6b3b69badafeb75fe6ab6c883d2316194ff1aeb0eb9c3901fe85700d862671',
    'bullish_absorption_operating_policy.json': '6857dbbc5e3d724a3dde2b0ef0ce5914d40a87a09ac4afd6aa0369c32113bf65',
}


def digest(name: str) -> str:
    return hashlib.sha256((ROOT / name).read_bytes()).hexdigest()


def main() -> None:
    for name, expected in INPUTS.items():
        assert digest(name) == expected
    base = json.loads((ROOT / 'owned_intel_valuation_2026_11_04.json').read_text())
    alternative = json.loads((ROOT / 'bullish_absorption_operating_policy.json').read_text())
    base_rows = {r['year']: r for r in base['operating_rows']}
    rows = []
    for source in alternative['annual_rows']:
        y = source['year']
        old = base_rows[y]
        corporate = [.7 - 4.5, .7 - 4.7, .7 - 4.9, .7 - 5.15][y - 2027] if y <= 2030 else (.7 - 5.15) * 1.03 ** (y - 2030)
        ebit = source['Products_operating_profit_B'] + source['Foundry_operating_profit_B'] + corporate
        da = source['total_normalized_DA_B']
        capex = source['physical_operating_gross_PPE_excluding_capitalized_interest_B']
        wc = source['cash_operating_WC_use_B']
        tax = max(ebit, 0) * old['ordinary_operating_tax_rate']
        cash = ebit - tax + da - capex - wc - old['all_in_lease_cash_B'] - old['minority_cash_reserve_B'] + old['old_capital_tax_receivable_collection_B'] + old['new_capital_credit_collection_B'] - old['new_credit_basis_loss_tax_charge_B']
        change = cash - old['parent_attributable_unlevered_cash_B']
        delta_check = (ebit - old['operating_EBIT_after_SBC_B']) * (1 - old['ordinary_operating_tax_rate']) + da - old['operating_DA_B'] - capex + old['physical_capex_B'] - wc + old['delta_WC_B']
        assert ebit > 0 and abs(change - delta_check) < 1e-10
        rows.append({'year': y, 'external_revenue_B': source['consolidated_external_revenue_for_capital_denominator_B'], 'EBIT_after_corporate_SBC_B': ebit, 'DA_B': da, 'physical_capex_B': capex, 'WC_B': wc, 'ordinary_tax_B': tax, 'parent_unlevered_cash_B': cash, 'cash_difference_vs_base_B': change})
    by_year = {row['year']: row for row in rows}
    funding = []
    cumulative = 0.0
    for old in base['treasury_rows']:
        y = old['year']
        cumulative += by_year[y]['cash_difference_vs_base_B']
        cash = old['ending_economic_cash_B'] + cumulative
        assert cash >= 20 and old['new_borrowing_B'] == 0
        assert by_year[y]['ordinary_tax_B'] > old['ordinary_interest_tax_benefit_B'] + old['capitalized_interest_depreciation_tax_benefit_B']
        funding.append({'year': y, 'owner_cash_B': old['owner_cash_after_financing_and_capital_incentives_B'] + by_year[y]['cash_difference_vs_base_B'], 'cash_difference_vs_base_B': cumulative, 'ending_economic_cash_B': cash, 'ending_ordinary_debt_B': old['ending_ordinary_debt_B'], 'new_borrowing_B': 0.0})
    for shield in base['financing_tax_benefit_rows']:
        assert by_year[shield['year']]['ordinary_tax_B'] > shield['conditional_financing_tax_benefit_B']
    by_funding = {row['year']: row for row in funding}
    assert abs(by_year[2041]['parent_unlevered_cash_B'] / by_year[2040]['parent_unlevered_cash_B'] - 1.03) < 1e-12

    def value(endpoint: int, rate: float, baseline: dict) -> dict:
        explicit_change = math.fsum(row['cash_difference_vs_base_B'] / (1 + rate) ** (row['year'] - endpoint) for row in rows if endpoint < row['year'] <= 2040)
        terminal_change = by_year[2041]['cash_difference_vs_base_B'] / (rate - .03) / (1 + rate) ** (2040 - endpoint)
        cash_change = 0.0 if endpoint == 2026 else by_funding[endpoint]['cash_difference_vs_base_B']
        equity_change = explicit_change + terminal_change + cash_change
        equity = baseline['equity_with_financing_tax_benefits_B'] + equity_change
        price = equity / baseline['planning_claims_B']
        item = {'date': f'{endpoint}-12-31', 'rate': rate, 'explicit_operating_PV_change_B': explicit_change, 'terminal_operating_PV_change_B': terminal_change, 'endpoint_cash_change_B': cash_change, 'equity_change_B': equity_change, 'equity_B': equity, 'price_USD': price, 'base_price_USD': baseline['price_with_financing_tax_benefits_USD']}
        if endpoint != 2026:
            years = (date(endpoint, 12, 31) - date.fromisoformat(base['entry']['date'])).days / 365.25
            item['annual_price_appreciation_from_entry'] = (price / base['entry']['price_USD']) ** (1 / years) - 1
        return item

    values = {str(y): value(y, .12, base['values_at12pct'][str(y)]) for y in [2026, 2029, 2030, 2031]}
    controls = {key: value(2030, float(key), v) for key, v in base['end2030_rate_controls'].items()}
    for name, expected in INPUTS.items():
        assert digest(name) == expected
    output = {'computed_utc': datetime.now(timezone.utc).isoformat(), 'scope': 'Funded bullish operating countercase, not a new base recommendation or probability. Forecast choices were frozen before this output; base valuation was already known.', 'input_hashes': INPUTS, 'reproducer_sha256': digest(Path(__file__).name), 'entry': base['entry'], 'operating_rows': rows, 'treasury_rows': funding, 'values_at12pct': values, 'end2030_rate_controls': controls, 'checks': {'unchanged_debt_and_financing_shield_valid_under_frozen_policies': True, 'minimum_yearend_economic_cash_B': min(r['ending_economic_cash_B'] for r in funding), 'terminal_cash_growth': by_year[2041]['parent_unlevered_cash_B'] / by_year[2040]['parent_unlevered_cash_B'] - 1, 'extra_physical_capex_2027_2030_B': math.fsum(r['physical_capex_B'] - base_rows[r['year']]['physical_capex_B'] for r in rows if r['year'] <= 2030), 'extra_WC_2027_2030_B': math.fsum(r['WC_B'] - base_rows[r['year']]['delta_WC_B'] for r in rows if r['year'] <= 2030)}, 'limitations': ['Additional manufacturing spending is charged; extra AMIC benefits are not assumed.', 'Corporate/SBC, lease, minority reserve, cash income and financial claims follow the frozen base conventions. Higher central costs or minority profit sharing would reduce the improvement.', 'Mature margins and capital productivity converge to the same conventions as the base. Faster timing and a higher accepted sales level persist.', 'This is a coherent forecast countercase, not proof that packaging qualification, CPU demand or yields will meet it.', 'End2026 is a planning reference, not current November3 fair value.']}
    path = ROOT / 'funded_bull_valuation_2026_11_04.json'
    path.write_text(json.dumps(output, indent=2, allow_nan=False) + '\n')
    print(json.dumps({'file': str(path), 'sha256': digest(path.name), 'values_at12pct': values, 'controls': controls, 'checks': output['checks']}, indent=2))


if __name__ == '__main__':
    main()

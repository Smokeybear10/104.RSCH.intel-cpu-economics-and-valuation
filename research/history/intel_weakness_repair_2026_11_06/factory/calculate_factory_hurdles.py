import copy
import hashlib
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path


OUT = Path(__file__).resolve().parent
RESEARCH = OUT.parents[1]
ACTIVE = RESEARCH / 'intel_market_share_thesis_2026_11_06/root/active_case.json'
ENGINE = RESEARCH / 'intel_two_hour_completion_2026_11_06/root/integrated_model.py'
POLICY = OUT / 'factory_policy.json'
spec = importlib.util.spec_from_file_location('factory_owned_case_engine', ENGINE)
model = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model)
active = json.loads(ACTIVE.read_text())
policy = json.loads(POLICY.read_text())
base_rows = {int(y): r for y, r in active['annual_rows'].items()}
opening_cash_delta = active['values']['2026']['cash_B'] - model.FUND[2027]['opening_economic_cash_B']


def scenario_rows(name: str) -> dict:
    rows = copy.deepcopy(base_rows)
    delay_ratio = 2.5 / base_rows[2032]['Products_revenue_B']
    for year, row in rows.items():
        if name == 'owned_base':
            profit = row['Foundry_profit_B']
        elif name == 'two_year_delay':
            profit = [-4, -4, -4, -.75, 1, 2.5][year - 2027] if year <= 2032 else delay_ratio * row['Products_revenue_B']
        elif name == 'breakeven_only':
            profit = [-4, -2.5, -1, 0][year - 2027] if year <= 2030 else 0
        else:
            profit = -4.12 if year == 2041 else -4
        delta = profit - row['Foundry_profit_B']
        row['Foundry_profit_B'] = profit
        row['EBIT_B'] += delta
        model.close_cash(row)
        assert abs(row['EBIT_B'] - base_rows[year]['EBIT_B'] - delta) < 1e-10
        for field in ['CPU_revenue_B', 'consolidated_revenue_B', 'CCPG_profit_B', 'DCAI_profit_B', 'net_packaging_profit_B', 'physical_capex_B', 'DA_B', 'WC_cash_use_B', 'minority_cash_B']:
            assert row[field] == base_rows[year][field], field
    return rows


cases = {}
for rate in policy['rates']:
    model.R = rate
    cases[str(rate)] = {}
    for name in policy['cases']:
        case = model.value(scenario_rows(name), opening_cash_delta=opening_cash_delta)
        if name == 'owned_base' and rate == active['operating_rate']:
            for year in [2026, 2030]:
                assert abs(case['values'][year]['price_USD'] - active['values'][str(year)]['price_USD']) < 1e-9
        cases[str(rate)][name] = {
            'Dec2026_value_USD': case['values'][2026]['price_USD'],
            'Dec2030_target_USD': case['values'][2030]['price_USD'],
            'annual_return_from_Nov5_quote': (case['values'][2030]['price_USD'] / model.ENTRY) ** (1 / model.YEARS) - 1,
            'Foundry_EBIT_2030_B': case['annual_rows'][2030]['Foundry_profit_B'],
            'group_EBIT_2030_B': case['annual_rows'][2030]['EBIT_B'],
            'parent_cash_2030_B': case['annual_rows'][2030]['parent_unlevered_cash_B'],
            'minimum_annual_cash_B': case['minimum_annual_cash_B'],
            'ending_cash_2030_B': case['treasury'][2030]['ending_cash_B'],
            'cash_2027_2030_before_financing_B': sum(case['annual_rows'][y]['parent_unlevered_cash_B'] for y in range(2027, 2031)),
            'annual_Foundry_EBIT_B': {y: case['annual_rows'][y]['Foundry_profit_B'] for y in range(2027, 2042)},
        }

quarterly = [{'quarter': 'Q1 2026', 'Foundry_EBIT_B': -4.526 + 2.089},
             {'quarter': 'Q2 2026', 'Foundry_EBIT_B': -2.089},
             {'quarter': 'Q3 2026', 'Foundry_EBIT_B': -1.853}]
reported_change = -1.853 - -2.321
charge_benefit = .793
ytd_change = -6.379 - -7.809
foundry_delta = base_rows[2030]['Foundry_profit_B'] - base_rows[2027]['Foundry_profit_B']
packaging_delta = base_rows[2030]['net_packaging_profit_B'] - base_rows[2027]['net_packaging_profit_B']
group_delta = base_rows[2030]['EBIT_B'] - base_rows[2027]['EBIT_B']
out = {
    'computed_utc': datetime.now(timezone.utc).isoformat(),
    'input_files': {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in [ACTIVE, ENGINE, POLICY]},
    'cases': cases,
    'opening_cash_delta_vs_original_engine_B': opening_cash_delta,
    'observed_loss_series': quarterly,
    'Q3_YoY_bridge_B': {
        'reported_EBIT_change': reported_change,
        'lower_period_charges': charge_benefit,
        'higher_opex': -.219,
        'other_net_change_residual': reported_change - charge_benefit + .219,
        'change_excluding_lower_period_charge_benefit': reported_change - charge_benefit,
        'note': 'Residual is calculated from disclosed changes, not labeled a separately disclosed product-profit change. Period charges are not all noncash or nonrecurring.',
    },
    'YTD_YoY_bridge_B': {
        'reported_EBIT_change': ytd_change,
        'lower_period_charges_rounded': 2.6,
        'lower_product_profit': -.936,
        'higher_opex': -.231,
        'rounding_residual': ytd_change - 2.6 + .936 + .231,
        'change_excluding_lower_period_charge_benefit_approx': ytd_change - 2.6,
    },
    'forecast_hurdles': {
        'Q3_2026_annualized_loss_B': 4 * -1.853,
        'owned_2027_loss_B': base_rows[2027]['Foundry_profit_B'],
        'improvement_required_vs_Q3_annualized_B': base_rows[2027]['Foundry_profit_B'] - 4 * -1.853,
        'loss_reduction_required_vs_Q3_annualized': 1 - 4 / (4 * 1.853),
        'Q1_to_Q3_quarterly_loss_reduction_B': quarterly[2]['Foundry_EBIT_B'] - quarterly[0]['Foundry_EBIT_B'],
        '2027_to_2030_Foundry_EBIT_improvement_B': foundry_delta,
        '2027_to_2030_net_packaging_EBIT_improvement_B': packaging_delta,
        'factory_packaging_share_of_group_EBIT_improvement': (foundry_delta + packaging_delta) / group_delta,
        'annual_Foundry_EBIT_forecasts_B': {y: base_rows[y]['Foundry_profit_B'] for y in range(2027, 2031)},
        'note': 'Q3 annualization is a level comparison, not a full-year forecast, normalized loss estimate or company guidance.',
    },
    'guardrails': [
        'Do not subtract the historical period-charge benefit from future forecasts; it diagnoses quality of reported improvement rather than forecasting a new cash penalty.',
        'Do not add the disclosed node cost reductions again: they are already reflected in actual economics.',
        'A lower consolidated value is the consequence of a standalone cost miss at fixed deliveries; do not combine with a volume miss by adding standalone scenario losses.',
        'Annual cash does not replace the separate quarter-end liquidity stress.',
        'No named, quantified packaging fee commitment was found that validates the two assumed 3B programs or total7B.',
    ],
}
(OUT / 'factory_results.json').write_text(json.dumps(out, indent=2) + '\n')
print(json.dumps({'cases': {rate: {name: {k: v for k, v in r.items() if k != 'annual_Foundry_EBIT_B'} for name, r in cases.items()} for rate, cases in cases.items()}, 'hurdles': out['forecast_hurdles'], 'quarter_bridge': out['Q3_YoY_bridge_B']}, indent=2))

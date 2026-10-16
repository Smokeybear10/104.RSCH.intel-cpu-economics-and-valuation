import copy
import hashlib
import json
import math
from datetime import date, datetime, timezone
from pathlib import Path

from scipy.optimize import brentq


OUT = Path(__file__).resolve().parent
RUN = OUT.parent
SOURCE = RUN / 'root/integrated_results.json'
ANCHOR_SOURCE = RUN / 'quarterly/anchor_valuation_overlay_results.json'
DATA = json.loads(SOURCE.read_text())
ANCHORS = json.loads(ANCHOR_SOURCE.read_text())
RAW_PATH = Path(DATA['input_files']['raw']['path'])
FUND = {r['year']: r for r in json.loads(RAW_PATH.read_text())['treasury_rows']}
RATE, G, SHARES, ENTRY = .11555, .03, 5.51, 52.25
HOLDING_YEARS = (date(2030, 12, 31) - date(2026, 11, 5)).days / 365.25
PLANNING_GAP_YEARS = (date(2026, 12, 31) - date(2026, 11, 5)).days / 365.25
FAVORABLE = 'joint_anchor_old_CPU2028plus_growth_pooled_old_growth'


def evaluate(case: dict, rate: float = RATE, growth: float = G,
             turnover: float = .8, mature_rate: bool = False,
             financing_rate: float | None = None,
             terminal_return_on_capital: float | None = None) -> dict:
    rows = {int(y): copy.deepcopy(r) for y, r in case['annual_rows'].items()}
    for year in range(2031, 2041):
        host_growth = rows[year]['host_capital_revenue_B'] - rows[year - 1]['host_capital_revenue_B']
        investment_change = host_growth * (1 / turnover - 1 / .8)
        rows[year]['net_operating_investment_B'] += investment_change
        rows[year]['physical_capex_B'] += investment_change
        rows[year]['parent_unlevered_cash_B'] -= investment_change
    last = rows[2040]
    terminal_nopat = last['EBIT_B'] * (1 + growth) * (1 - rows[2041]['tax_rate'])
    terminal_investment = growth * (
        last['host_capital_revenue_B'] / turnover + last['net_new_packaging_B'])
    if terminal_return_on_capital is not None:
        terminal_investment = growth * terminal_nopat / terminal_return_on_capital
    terminal_lease_and_nci = (last['lease_cash_B'] + last['minority_cash_B']) * (1 + growth)
    terminal_cash = terminal_nopat - terminal_investment - terminal_lease_and_nci

    def annual_rate(year: int, financial: bool = False) -> float:
        if financial and financing_rate is not None:
            return financing_rate
        return rate - .0015 * min(max(year - 2030, 0), 10) if mature_rate else rate

    def discount(endpoint: int, year: int, financial: bool = False) -> float:
        return math.prod(1 + annual_rate(y, financial) for y in range(endpoint + 1, year + 1))

    values = {}
    for endpoint in (2026, 2030):
        explicit = math.fsum(rows[y]['parent_unlevered_cash_B'] / discount(endpoint, y)
                             for y in range(endpoint + 1, 2041))
        terminal = terminal_cash / (annual_rate(2041) - growth) / discount(endpoint, 2040)
        shield = math.fsum(rows[y]['financing_shield_B'] / discount(endpoint, y, True)
                          for y in range(endpoint + 1, 2041))
        shield += rows[2041]['financing_shield_B'] / annual_rate(2041, True) / discount(endpoint, 2040, True)
        escrow = math.fsum(FUND[y]['escrow_cash_B'] / discount(endpoint, y, True)
                          for y in range(endpoint + 1, 2031))
        acquisition = math.fsum(FUND[y]['Classiq_cash_B'] / discount(endpoint, y, True)
                               for y in range(endpoint + 1, 2031))
        frozen = case['values'][str(endpoint)]
        equity = explicit + terminal + shield + frozen['cash_B'] - frozen['debt_B'] + frozen['net_other_assets_B'] + escrow - acquisition
        values[endpoint] = {
            'price_USD': equity / SHARES,
            'explicit_operating_PV_B': explicit,
            'terminal_operating_PV_B': terminal,
            'financing_shield_PV_B': shield,
            'remaining_escrow_PV_B': escrow,
            'remaining_acquisition_PV_B': acquisition,
            'terminal_share_of_operating_value': terminal / (explicit + terminal),
        }
    target = values[2030]['price_USD']
    return {
        'values': values,
        'planning_value_USD': values[2026]['price_USD'],
        'target2030_USD': target,
        'annual_price_return': (target / ENTRY) ** (1 / HOLDING_YEARS) - 1,
        'entry_ceiling_for10pct_price_return_USD': target / 1.1 ** HOLDING_YEARS,
        'terminal': {
            'growth': growth, 'NOPAT_B': terminal_nopat,
            'net_operating_investment_B': terminal_investment,
            'lease_and_minority_cash_B': terminal_lease_and_nci,
            'parent_unlevered_cash_B': terminal_cash,
            'reinvestment_fraction_of_NOPAT': terminal_investment / terminal_nopat,
            'implied_incremental_ROC': growth * terminal_nopat / terminal_investment,
        },
    }


def root_or_boundary(fn, low: float, high: float) -> dict:
    lower, upper = fn(low), fn(high)
    if lower * upper > 0:
        return {'root': None, 'search_bounds': [low, high], 'residual_at_bounds': [lower, upper]}
    root = brentq(fn, low, high, xtol=1e-13)
    return {'root': root, 'search_bounds': [low, high], 'residual_at_root_USD': fn(root)}


def main() -> None:
    cases = {k: DATA['cases'][k] for k in ['preferred', 'slower_delivery', 'retained_margin_components', 'accounting_completed']}
    cases['existing_favorable'] = ANCHORS['cases'][FAVORABLE]
    baseline_checks = []
    for name, case in cases.items():
        result = evaluate(case)
        for endpoint in (2026, 2030):
            for field in ['price_USD', 'explicit_operating_PV_B', 'terminal_operating_PV_B', 'financing_shield_PV_B']:
                error = result['values'][endpoint][field] - case['values'][str(endpoint)][field]
                assert abs(error) < 1e-8, (name, endpoint, field, error)
                baseline_checks.append(abs(error))

    rates = {'selected': RATE, 'plain_T12_NYU': .10631495183175221,
             'normalized_NYU_rounded': .10025, 'lower_rate_challenge': .10,
             'higher_rate_challenge': .13}
    rate_controls = []
    for name in ['preferred', 'slower_delivery', 'existing_favorable']:
        for label, rate in rates.items():
            rate_controls.append({'case': name, 'rate_policy': label, 'rate': rate,
                                  **evaluate(cases[name], rate)})
        rate_controls.append({'case': name, 'rate_policy': 'maturing_150bp',
                              'rate2027_2030': RATE, 'rate2040_on': RATE - .015,
                              **evaluate(cases[name], mature_rate=True)})

    rate_hurdles = []
    for name, case in cases.items():
        for hurdle in (0, .08, .10, .12):
            needed = ENTRY * (1 + hurdle) ** HOLDING_YEARS
            solution = root_or_boundary(lambda r: evaluate(case, r)['target2030_USD'] - needed, .031, .25)
            rate_hurdles.append({'case': name, 'annual_price_return_hurdle': hurdle,
                                 'required2030_price_USD': needed,
                                 'constant_asset_rate': solution,
                                 'implied_asset_beta_under_Nov1_selected_ERP': (solution['root'] - .0494) / .0441 if solution['root'] else None})
        solution = root_or_boundary(lambda r: evaluate(case, r)['planning_value_USD'] - ENTRY, .031, .25)
        rate_hurdles.append({'case': name, 'hurdle': 'Dec2026_planning_value_equals_Nov5_quote',
                             'constant_asset_rate': solution,
                             'scope': 'Date-mismatched planning comparison, not contemporaneous market-implied cost of capital.'})

    preferred = cases['preferred']
    target10 = ENTRY * 1.1 ** HOLDING_YEARS
    terminal_controls = [{'g': g, **evaluate(preferred, growth=g)} for g in (.02, .03, .04)]
    growth_hurdles = []
    for endpoint, needed in [(2026, ENTRY), (2030, target10)]:
        solution = root_or_boundary(lambda g: evaluate(preferred, growth=g)['values'][endpoint]['price_USD'] - needed, .00001, RATE - .0001)
        growth_hurdles.append({'endpoint': endpoint, 'required_price_USD': needed,
                              'terminal_growth_solution': solution,
                              'economics_at_solution': evaluate(preferred, growth=solution['root'])['terminal'] if solution['root'] else None})

    capital_controls = [{'host_incremental_sales_to_capital': t, **evaluate(preferred, turnover=t)} for t in (.6, .8, 1.)]
    capital_limit = evaluate(preferred, turnover=math.inf)
    capital_hurdles = []
    for endpoint, needed in [(2026, ENTRY), (2030, target10)]:
        solution = root_or_boundary(lambda t: evaluate(preferred, turnover=t)['values'][endpoint]['price_USD'] - needed, .1, 1000000.)
        capital_hurdles.append({'endpoint': endpoint, 'required_price_USD': needed,
                               'host_turnover_solution': solution,
                               'zero_host_growth_investment_limit_price_USD': capital_limit['values'][endpoint]['price_USD'],
                               'limit_scope': 'Infeasible optimistic ceiling for this single axis, holding all revenue, profit, packaging investment and pre2031 cash fixed; not a possible operating case.'})

    no_excess = evaluate(preferred, terminal_return_on_capital=RATE)
    component_risk = evaluate(preferred, financing_rate=.0494)
    timing = [{'illustrative_equity_rate': r,
               'Dec2026_value_discounted_back56days_USD': evaluate(preferred)['planning_value_USD'] / (1 + r) ** PLANNING_GAP_YEARS,
               'scope': 'Illustrative equity carry only, no dividend; not an exact reconstruction of intraquarter cash or forecast changes.'}
              for r in (.08, .10, .12)]
    result = {
        'computed_utc': datetime.now(timezone.utc).isoformat(),
        'inputs': [{'path': str(p), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in [SOURCE, ANCHOR_SOURCE, RAW_PATH]],
        'policy_files': ['risk_policy_before_calculation.json', 'risk_policy_extension_before_calculation.json'],
        'baseline_reconciliation': {'comparisons': len(baseline_checks), 'maximum_error_B_or_USD': max(baseline_checks)},
        'dates': {'entry': '2026-11-05', 'planning': '2026-12-31', 'exit': '2030-12-31',
                  'entry_USD': ENTRY, 'holding_years_ACT36525': HOLDING_YEARS, 'planning_gap_days': 56},
        'rate_controls': rate_controls, 'rate_hurdles': rate_hurdles,
        'funded_terminal_growth_controls': terminal_controls, 'terminal_growth_hurdles': growth_hurdles,
        'capital_efficiency_controls': capital_controls, 'capital_efficiency_hurdles': capital_hurdles,
        'no_excess_incremental_terminal_ROC_control': no_excess,
        'lower_risk_financing_components_control': component_risk,
        'illustrative_equity_date_bridge': timing,
        'warnings': [
            'No assigned probabilities. Selected preferred case is not established as the expected outcome.',
            'A reverse rate is the mathematical rate needed for a specified payoff, not proof that rate is economically correct.',
            'The2030rate sensitivity describes conditional future valuation; a current rate change does not guarantee a market rerating in2030.',
            'Terminal growth is funded; growth changes do not merely alter the Gordon denominator.',
            'Terminal incremental ROC excludes lease/minority cash and is not historical company ROIC.',
            'No asset-rate subtraction from stock-price CAGR, short recommendation or competition-win probability.',
        ],
    }
    (OUT / 'risk_robustness_results.json').write_text(json.dumps(result, indent=2) + '\n')
    concise = {
        'baseline_reconciliation': result['baseline_reconciliation'],
        'rates': [{k: r[k] for k in ['case', 'rate_policy', 'planning_value_USD', 'target2030_USD', 'annual_price_return']} for r in rate_controls],
        'preferred_and_favorable_rate_hurdles': [r for r in rate_hurdles if r['case'] in ['preferred', 'existing_favorable']],
        'terminal_controls': [{k: r[k] for k in ['g', 'planning_value_USD', 'target2030_USD', 'annual_price_return']} for r in terminal_controls],
        'growth_hurdles': growth_hurdles, 'capital_hurdles': capital_hurdles,
        'no_excess_terminal_prices': [no_excess['planning_value_USD'], no_excess['target2030_USD']],
        'lower_risk_finance_prices': [component_risk['planning_value_USD'], component_risk['target2030_USD']],
    }
    print(json.dumps(concise, indent=2))


if __name__ == '__main__':
    main()

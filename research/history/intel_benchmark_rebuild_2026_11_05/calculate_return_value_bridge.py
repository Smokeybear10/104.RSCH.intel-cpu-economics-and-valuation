from datetime import date, datetime, timezone
from hashlib import sha256
from pathlib import Path
import json
import math

ROOT = Path(__file__).resolve().parents[4]
RESEARCH = ROOT / 'work/three_hour/active_research'
OUT = Path(__file__).resolve().parent
PATHS = {
    'model': RESEARCH / 'pricing_and_competition_review_2026_11_04/intel_ASP20_mature_margin35_valuation.json',
    'host': RESEARCH / 'pricing_and_competition_review_2026_11_04/intel_server_ASP_mix_operating_policy.json',
    'rates': RESEARCH / 'intel_hour_verification_2026_11_04/corrected_rate_valuation.json',
    'weak': RESEARCH / 'intel_hour_verification_2026_11_04/weak_demand_results.json',
    'old_bridge': RESEARCH / 'intel_pitch_completion_2026_11_05/operating_value_bridge.json',
    'joint': RESEARCH / 'intel_directional_build_2026_11_05/joint_downside_results.json',
}
hashes = {name: sha256(path.read_bytes()).hexdigest() for name, path in PATHS.items()}
d = {name: json.loads(path.read_text()) for name, path in PATHS.items()}
base = {r['year']: r for r in d['model']['annual_operating_rows']}
host = {r['year']: r for r in d['host']['annual_rows']}
weak = {r['year']: r for r in d['weak']['rows']}
funding = {r['year']: r for r in d['model']['treasury_rows']}
shields = {r['year']: r['financing_tax_benefit_B'] for r in d['model']['financing_tax_benefit_rows']}
claims = d['model']['values_at12pct']['2026']['planning_claims_B']
other_assets = d['model']['values_at12pct']['2026']['net_other_assets_B']
rate = .11555
growth = .03
entry = 52.22
years = (date(2030, 12, 31) - date(2026, 11, 5)).days / 365.25
errors = []


def check(actual: float, expected: float) -> None:
    error = abs(actual - expected)
    assert error < 1e-9, (actual, expected, error)
    errors.append(error)


def cash_rows(mature_margin: float, lower_demand: bool = False) -> dict:
    rows = weak if lower_demand else base
    result = {}
    for year, row in rows.items():
        sales = host[year]['DCAI_revenue_B']
        if lower_demand:
            sales += row['server_revenue_delta_B']
        weight = min(max((year - 2030) / 10, 0), 1)
        ebit_delta = sales * (mature_margin - .35) * weight
        new_tax = max(row['EBIT_after_economic_SBC_B'] + ebit_delta, 0) * row['tax_rate']
        cash_delta = ebit_delta - new_tax + row['ordinary_operating_tax_B']
        result[year] = row['parent_unlevered_cash_B'] + cash_delta
        if year <= 2030:
            check(result[year], row['parent_unlevered_cash_B'])
    check(result[2041] / result[2040], 1.03)
    return result


def value(mature_margin: float, endpoint: int, lower_demand: bool = False, risk: str = 'corrected_central_flat') -> dict:
    cash = cash_rows(mature_margin, lower_demand)
    schedule = {int(year): discount_rate for year, discount_rate in d['rates']['rate_schedules'][risk].items()}
    discount = lambda year: math.prod(1 + schedule[step] for step in range(endpoint + 1, year + 1))
    explicit = math.fsum(amount / discount(year) for year, amount in cash.items() if endpoint < year <= 2040)
    terminal = cash[2041] / (schedule[2041] - growth) / discount(2040)
    shield_value = math.fsum(amount / discount(year) for year, amount in shields.items() if endpoint < year <= 2040)
    shield_value += shields[2041] / schedule[2041] / discount(2040)
    if endpoint == 2026:
        cash_balance = funding[2027]['opening_economic_cash_B']
        debt = funding[2027]['opening_ordinary_debt_B']
    else:
        cash_balance = weak[endpoint]['ending_economic_cash_B'] if lower_demand else funding[endpoint]['ending_economic_cash_B']
        debt = funding[endpoint]['ending_ordinary_debt_B']
    escrow = math.fsum(row['escrow_cash_B'] / discount(year) for year, row in funding.items() if endpoint < year <= 2030)
    acquisitions = math.fsum(row['Classiq_cash_B'] / discount(year) for year, row in funding.items() if endpoint < year <= 2030)
    financial = cash_balance - debt + other_assets + escrow - acquisitions + shield_value
    equity = explicit + terminal + financial
    return {
        'price_USD': equity / claims,
        'explicit_operating_PV_B': explicit,
        'terminal_operating_PV_B': terminal,
        'financing_tax_benefit_PV_B': shield_value,
        'net_financial_claims_and_tax_benefits_B': financial,
        'equity_B': equity,
        'terminal_share_of_operating_value': terminal / (explicit + terminal),
        'terminal_share_of_equity_value': terminal / equity,
        'terminal_value_per_share_USD': terminal / claims,
    }


by_endpoint = {}
for endpoint in (2026, 2030):
    old = next(r for r in d['old_bridge']['decomposition'] if r['endpoint'] == endpoint and r['risk'] == 'corrected_central_flat')
    values = {
        'base_demand_margin35': value(.35, endpoint),
        'base_demand_margin40': value(.4, endpoint),
        'lower_demand_margin35': value(.35, endpoint, True),
        'lower_demand_margin40': value(.4, endpoint, True),
        'lower_demand_margin30': value(.3, endpoint, True),
    }
    for name, prior_name in [('base_demand_margin35', 'central'), ('base_demand_margin40', 'margin_only')]:
        for field, expected in old['cases'][prior_name].items():
            check(values[name][field], expected)
    for field in ['price_USD', 'explicit_operating_PV_B', 'terminal_operating_PV_B']:
        check(values['lower_demand_margin35'][field], d['weak']['values_flat_11_555pct'][str(endpoint)][field])
    a, b = values['base_demand_margin35'], values['base_demand_margin40']
    margin_delta = b['price_USD'] - a['price_USD']
    by_endpoint[str(endpoint)] = {
        'values': values,
        'margin35_to40_contribution': {
            'per_share_USD': margin_delta,
            'equity_B': b['equity_B'] - a['equity_B'],
            'explicit_cash_PV_B': b['explicit_operating_PV_B'] - a['explicit_operating_PV_B'],
            'post2040_PV_B': b['terminal_operating_PV_B'] - a['terminal_operating_PV_B'],
            'share_of_selected_equity_value': margin_delta / b['price_USD'],
            'per_mature_margin_percentage_point_USD': margin_delta / 5,
            '2027_2030_cash_change_B': 0,
        },
    }

target = by_endpoint['2030']['values']['base_demand_margin40']['price_USD']
check(target, 77.6819879986314)
maturing = {}
for endpoint in (2026, 2030):
    maturing[endpoint] = value(.4, endpoint, risk='corrected_maturing_risk')
    old = next(r for r in d['old_bridge']['decomposition'] if r['endpoint'] == endpoint and r['risk'] == 'corrected_maturing_risk')
    for field, expected in old['cases']['margin_only'].items():
        check(maturing[endpoint][field], expected)

paired_scenarios = []
for label, near, future in [
    ('Joint downside', d['joint']['values']['2026']['corrected_central_flat'], d['joint']['values']['2030']['corrected_central_flat']),
    ('Lower CPU demand; retain 40% mature margin and 0.80 capital productivity', by_endpoint['2026']['values']['lower_demand_margin40'], by_endpoint['2030']['values']['lower_demand_margin40']),
    ('Competitive margin erosion: 35%, base sales and investment', by_endpoint['2026']['values']['base_demand_margin35'], by_endpoint['2030']['values']['base_demand_margin35']),
    ('Base LONG: 40%, base sales and investment', by_endpoint['2026']['values']['base_demand_margin40'], by_endpoint['2030']['values']['base_demand_margin40']),
    ('Lower-risk upside: same operations as base', maturing[2026], maturing[2030]),
]:
    paired_scenarios.append({
        'label': label,
        'December2026_planning_value_USD': near['price_USD'],
        'December2030_target_USD': future['price_USD'],
        'planning_value_change_from_reference': near['price_USD'] / entry - 1,
        'total_price_change_to2030': future['price_USD'] / entry - 1,
        'annual_price_change_to2030': (future['price_USD'] / entry) ** (1 / years) - 1,
    })

price_at35 = by_endpoint['2026']['values']['base_demand_margin35']['price_USD']
value_per_percentage_point = by_endpoint['2026']['margin35_to40_contribution']['per_mature_margin_percentage_point_USD']
conditional_reverse_margin = .35 + (entry - price_at35) / value_per_percentage_point * .01
check(value(conditional_reverse_margin, 2026)['price_USD'], entry)
entry_matrix = [
    {'annual_price_return_required': hurdle, 'maximum_entry_USD': target / (1 + hurdle) ** years,
     'change_from_reference_entry': (target / (1 + hurdle) ** years) / entry - 1}
    for hurdle in [.08, .10, .12, .15]
]
for row in entry_matrix:
    check((target / row['maximum_entry_USD']) ** (1 / years) - 1, row['annual_price_return_required'])

ordered_downside = []
for label, price in [
    ('Base sales; 40% mature margin; 0.80 capital productivity', target),
    ('Lower CPU demand with modeled cost/capital responses; keep 40% and 0.80', by_endpoint['2030']['values']['lower_demand_margin40']['price_USD']),
    ('Also reduce mature margin from 40% to 30%; keep 0.80', by_endpoint['2030']['values']['lower_demand_margin30']['price_USD']),
    ('Also reduce mature capital productivity to 0.60: existing joint downside', d['joint']['values']['2030']['corrected_central_flat']['price_USD']),
]:
    prior = ordered_downside[-1]['price_USD'] if ordered_downside else price
    ordered_downside.append({'label': label, 'price_USD': price, 'step_change_USD': price - prior, 'price_CAGR': (price / entry) ** (1 / years) - 1})
check(by_endpoint['2030']['values']['lower_demand_margin30']['price_USD'], d['joint']['2030_decomposition_flat']['weak_demand_plus_margin30_only'])
check(ordered_downside[-1]['step_change_USD'], d['joint']['2030_decomposition_flat']['incremental_mature_capital_loss_USD'])

result = {
    'computed_utc': datetime.now(timezone.utc).isoformat(),
    'scope': 'Read-only independent reconstruction and presentation diagnostics; selected model and recommendation unchanged.',
    'source_files': {name: {'path': str(path), 'sha256': hashes[name]} for name, path in PATHS.items()},
    'dates': {'entry_date': '2026-11-05', 'planning_value_date': '2026-12-31', 'target_date': '2030-12-31', 'holding_years': years, 'planning_date_mismatch_days': 56},
    'fixed_assumptions': {'entry_USD': entry, 'mature_capital_productivity': .8, 'flat_operating_discount_rate': rate, 'terminal_operating_growth': growth, 'planning_shares_B': claims, 'no_interim_dividends': True},
    'by_endpoint': by_endpoint,
    'paired_scenarios': paired_scenarios,
    'conditional_reverse_margin': {
        'mature_DCAI_margin_matching_reference': conditional_reverse_margin,
        'all_other_parameters': 'Base sales and investment,0.80 productivity,flat11.555% operating rate',
        'interpretation': 'One-variable conditional diagnostic, not a uniquely identified market forecast. Matches a December31,2026 planning value to a November5 quote, with56day mismatch. Not adopted as a forecast.',
    },
    'entry_price_matrix': entry_matrix,
    'entry_matrix_interpretation': 'Illustrative investor-chosen annual price-return requirements, not M37 rules, inferred market hurdles or justified cost-of-equity estimates. All use exactly the same conditional2030target. Lower price does not improve fundamentals; costs,taxes,dividends and scenario probabilities excluded.',
    'ordered_2030_downside_bridge': ordered_downside,
    'downside_bridge_interpretation': 'Order-dependent attribution: CPU weakness reduces the revenue base on which margin changes act. Lower-demand case includes specified cost,capital,working-capital and tax responses, so it is not a pure demand coefficient. All risk rates remain flat; scenarios are not floors or probability bounds.',
    'suggested_use': {
        'margin_slide': 'Preserving40% rather than35% adds4.33 per share to December2026 value and6.70 to December2030 target. It does not change cash through2030. This quantifies the belief instead of treating latest-quarter margins as proof.',
        'price_slide': 'The current entry roughly clears a chosen10% annual hurdle; it does not clear12% or15%. Show the choice rather than claim a valuation discount.',
        'risk_slide': 'The largest stress contribution is weaker CPU demand with cost/capital responses, not the mature-margin choice. Preserve a separate near-term stress value to avoid implying endpoint downside bounds drawdowns.',
    },
    'limits': [
        'A future target above the entry can reflect normal discount-rate roll-forward and accumulated cash; it is not by itself evidence of mispricing.',
        'Operating cash after2040 contributes44.8%of selectedDecember2026equity value and45.8%of selectedDecember2030equity value. Long-run margin and investment assumptions remain consequential.',
        'All40-versus35cash differences begin2031 and phase through2040. This is continuation-value sensitivity, not evidence of2027profit or a dated stock-price catalyst.',
        'A coherent LONGatfairvalue is a moderate-return investment choice, but this analysis does not establish that10% sufficiently compensates for Intel-specific risks or beats alternatives.',
        'Do not subtract11.555% operating-asset discount rate from10% shareholder price CAGR to infer alpha.',
        'Changing the chosen required return is a judgment and must not be represented as research evidence or a way to tune valuation into the recommendation.',
    ],
    'verification': {'independent_comparisons': len(errors), 'maximum_absolute_error': max(errors), 'all_source_files_unchanged': all(sha256(path.read_bytes()).hexdigest() == hashes[name] for name, path in PATHS.items())},
}
(OUT / 'return_value_bridge.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps({k: result[k] for k in ['dates', 'paired_scenarios', 'conditional_reverse_margin', 'entry_price_matrix', 'ordered_2030_downside_bridge', 'verification']}, indent=2))

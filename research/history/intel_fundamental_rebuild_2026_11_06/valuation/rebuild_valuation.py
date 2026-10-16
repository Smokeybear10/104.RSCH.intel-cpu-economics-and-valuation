import copy
import hashlib
import json
import math
from datetime import date, datetime, timezone
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[4]
POLICY_PATH = OUT / 'policy_before_calculation.json'
POLICY = json.loads(POLICY_PATH.read_text())
ACTIVE_PATH = ROOT / 'work/three_hour/active_research/intel_market_share_thesis_2026_11_06/root/active_case.json'
PRIOR_PATH = ROOT / 'work/three_hour/active_research/intel_valuation_resolution_2026_11_06/valuation/valuation_resolution_results.json'
ACTIVE = json.loads(ACTIVE_PATH.read_text())
PRIOR = json.loads(PRIOR_PATH.read_text())
BASE = {int(y): r for y, r in ACTIVE['annual_rows'].items()}
TREASURY = {int(y): r for y, r in ACTIVE['treasury'].items()}
G, SHARES = .03, 5.51
HORIZON = (date.fromisoformat(POLICY['exit_date']) - date.fromisoformat(POLICY['quote_date'])).days / 365.25


def close_cash(row: dict) -> None:
    row['ordinary_operating_tax_B'] = max(row['EBIT_B'], 0) * row['tax_rate']
    row['NOPAT_B'] = row['EBIT_B'] - row['ordinary_operating_tax_B']
    row['net_operating_investment_B'] = row['physical_capex_B'] - row['DA_B'] + row['WC_cash_use_B']
    row['parent_unlevered_cash_B'] = (row['NOPAT_B'] - row['net_operating_investment_B']
        - row['lease_cash_B'] - row['minority_cash_B'] + row['old_credit_collection_B']
        + row['new_credit_collection_B'] - row['credit_basis_loss_tax_B'])


def normalized_cash(row: dict) -> float:
    return row['parent_unlevered_cash_B'] - row['old_credit_collection_B'] - row['new_credit_collection_B'] + row['credit_basis_loss_tax_B']


def value(rows: dict, rate: float, endpoint: int) -> dict:
    explicit = math.fsum(rows[y]['parent_unlevered_cash_B'] / (1 + rate) ** (y - endpoint) for y in range(endpoint + 1, 2041))
    terminal = rows[2041]['parent_unlevered_cash_B'] / (rate - G) / (1 + rate) ** (2040 - endpoint)
    shield = math.fsum(rows[y]['financing_shield_B'] / (1 + rate) ** (y - endpoint) for y in range(endpoint + 1, 2041))
    shield += rows[2041]['financing_shield_B'] / rate / (1 + rate) ** (2040 - endpoint)
    cash = ACTIVE['values'][str(endpoint)]['cash_B']
    if endpoint == 2030:
        cash += math.fsum(rows[y]['parent_unlevered_cash_B'] - BASE[y]['parent_unlevered_cash_B'] for y in range(2027, 2031))
    debt = ACTIVE['values'][str(endpoint)]['debt_B']
    escrow = math.fsum(TREASURY[y]['escrow_cash_B'] / (1 + rate) ** (y - endpoint) for y in range(endpoint + 1, 2031))
    acquisition = math.fsum(TREASURY[y]['Classiq_cash_B'] / (1 + rate) ** (y - endpoint) for y in range(endpoint + 1, 2031))
    bridge = shield + cash - debt + 4.502 + escrow - acquisition
    equity = explicit + terminal + bridge
    return {'endpoint': endpoint, 'rate': rate, 'explicit_operating_PV_B': explicit,
        'terminal_operating_PV_B': terminal, 'total_operating_value_B': explicit + terminal,
        'financing_shield_PV_B': shield, 'cash_B': cash, 'debt_B': debt,
        'net_other_assets_B': 4.502, 'remaining_escrow_PV_B': escrow,
        'remaining_acquisition_PV_B': acquisition, 'nonoperating_and_financing_bridge_B': bridge,
        'equity_B': equity, 'price_USD': equity / SHARES}


def annual_return(price: float) -> float:
    return (price / POLICY['quote_USD']) ** (1 / HORIZON) - 1


def summarize(rows: dict, rate: float) -> dict:
    planning, target = value(rows, rate, 2026), value(rows, rate, 2030)
    cash, annual_cash = ACTIVE['values']['2026']['cash_B'], []
    for y in range(2027, 2031):
        cash += TREASURY[y]['ending_cash_B'] - TREASURY[y]['opening_cash_B']
        cash += rows[y]['parent_unlevered_cash_B'] - BASE[y]['parent_unlevered_cash_B']
        annual_cash.append({'year': y, 'ending_cash_B': cash})
    assert abs(cash - target['cash_B']) < 1e-9
    return {'rate': rate, 'Dec2026_planning_value_USD': planning['price_USD'],
        'Dec2030_target_USD': target['price_USD'], 'annual_price_return_from_Nov6_56_28': annual_return(target['price_USD']),
        'EBIT2030_B': rows[2030]['EBIT_B'],
        'normalized_parent_operating_cash2030_B': normalized_cash(rows[2030]),
        'normalized_parent_operating_cash2031_B': normalized_cash(rows[2031]),
        'CPU_margin2030': rows[2030]['CPU_margin'], 'CPU_margin2040': rows[2040]['CPU_margin'],
        'DCAI_margin2030': rows[2030]['DCAI_profit_B'] / rows[2030]['DCAI_revenue_B'],
        'Foundry_profit2030_B': rows[2030]['Foundry_profit_B'],
        'net_packaging_profit2030_B': rows[2030]['net_packaging_profit_B'],
        'physical_capex2027to2030_B': math.fsum(rows[y]['physical_capex_B'] for y in range(2027, 2031)),
        'annual_cash_only': annual_cash, 'minimum_annual_cash_B': min(r['ending_cash_B'] for r in annual_cash),
        'terminal_share_of_Dec2026_operating_value': planning['terminal_operating_PV_B'] / planning['total_operating_value_B'],
        'after2030_share_of_Dec2026_operating_value': target['total_operating_value_B'] / (1 + rate) ** 4 / planning['total_operating_value_B']}


def margin_rows(uplift: float) -> dict:
    rows = copy.deepcopy(BASE)
    for y, row in rows.items():
        phase = min((y - 2026) / 4, 1)
        change = uplift * phase * row['CPU_revenue_B']
        row['CPU_margin'] += uplift * phase
        row['DCAI_profit_B'] += change
        row['EBIT_B'] += change
        close_cash(row)
    return rows


def ablation(foundry: bool, packaging: bool) -> dict:
    rows = copy.deepcopy(BASE)
    for y, row in rows.items():
        if foundry:
            replacement = {2027: -4., 2028: -2.5, 2029: -1.}.get(y, 0.)
            row['EBIT_B'] += replacement - row['Foundry_profit_B']
            row['Foundry_profit_B'] = replacement
        if packaging:
            replacement = min(row['net_packaging_profit_B'], 0)
            row['EBIT_B'] += replacement - row['net_packaging_profit_B']
            row['net_packaging_profit_B'] = replacement
        close_cash(row)
    return rows


def margin_coefficient(rate: float) -> float:
    def benefit(y: int) -> float:
        return BASE[y]['CPU_revenue_B'] * min((y - 2026) / 4, 1) * (1 - BASE[y]['tax_rate'])
    cash = math.fsum(benefit(y) for y in range(2027, 2031))
    explicit = math.fsum(benefit(y) / (1 + rate) ** (y - 2030) for y in range(2031, 2041))
    terminal = benefit(2041) / (rate - G) / (1 + rate) ** 10
    return (cash + explicit + terminal) / SHARES


def main() -> None:
    baseline = {str(rate): {str(y): value(BASE, rate, y) for y in (2026, 2030)} for rate in POLICY['rates']}
    errors = []
    for rate in POLICY['rates']:
        for y in (2026, 2030):
            current, prior = baseline[str(rate)][str(y)], PRIOR['independent_APV'][str(rate)][str(y)]
            errors += [abs(current[k] - prior[k]) for k in current if k in prior]
    assert max(errors) < 1e-9
    row_errors = []
    for original in BASE.values():
        rebuilt = copy.deepcopy(original)
        close_cash(rebuilt)
        row_errors += [abs(rebuilt[k] - original[k]) for k in ('NOPAT_B', 'net_operating_investment_B', 'parent_unlevered_cash_B')]
    assert max(row_errors) < 1e-9
    cases = {}
    for name, rows in [('core', BASE), ('packaging_no_positive_profit_capital_retained', ablation(False, True)),
                       ('Foundry_existing_breakeven_stress', ablation(True, False)),
                       ('Foundry_breakeven_and_packaging_no_positive_profit', ablation(True, True))]:
        cases[name] = [summarize(rows, rate) for rate in POLICY['rates']]
        for y, row in rows.items():
            for field in ('physical_capex_B', 'DA_B', 'WC_cash_use_B', 'consolidated_revenue_B', 'CPU_revenue_B', 'lease_cash_B', 'minority_cash_B'):
                assert row[field] == BASE[y][field], (name, y, field)
    reverse, bound, margin_checks, cash_checks = [], [], [], []
    for rate in POLICY['rates']:
        core = baseline[str(rate)]['2030']
        coefficient = margin_coefficient(rate)
        max_rows = copy.deepcopy(BASE)
        max_rows[2041]['physical_capex_B'] -= max_rows[2041]['net_operating_investment_B']
        close_cash(max_rows[2041])
        assert abs(max_rows[2041]['net_operating_investment_B']) < 1e-10
        bound.append({'rate': rate, 'scope': 'Generous algebraic bound only;3%perpetualgrowth without netreinvestment from2041',
            'zero_terminal_net_investment_target_USD': value(max_rows, rate, 2030)['price_USD'],
            'annual_price_return_from_Nov6_56_28': annual_return(value(max_rows, rate, 2030)['price_USD']),
            'extra_target_value_USD': value(max_rows, rate, 2030)['price_USD'] - core['price_USD']})
        for hurdle in POLICY['return_hurdles']:
            target = POLICY['quote_USD'] * (1 + hurdle) ** HORIZON
            gap_equity = (target - core['price_USD']) * SHARES
            cash_delta = gap_equity * (rate - G)
            cash_rows = copy.deepcopy(BASE)
            for y in range(2031, 2042):
                cash_rows[y]['parent_unlevered_cash_B'] += cash_delta * (1 + G) ** (y - 2031)
            cash_checks.append(abs(value(cash_rows, rate, 2030)['price_USD'] - target))
            uplift = (target - core['price_USD']) / coefficient
            rows = margin_rows(uplift)
            margin_checks.append(abs(value(rows, rate, 2030)['price_USD'] - target))
            forward_cash = normalized_cash(BASE[2031])
            reverse.append({'rate': rate, 'annual_return_hurdle': hurdle,
                'required_Dec2030_price_USD': target, 'equity_gap_to_core_B': gap_equity,
                'equivalent_extra_parent_cash2031_B_growing3pct': cash_delta,
                'equivalent_total_normalized_parent_cash2031_B': forward_cash + cash_delta,
                'equivalent_2031_cash_improvement_fraction': cash_delta / forward_cash,
                'CPU_margin_uplift_by2030': uplift,
                'extra_accumulated_cash_by2030_B': value(rows, rate, 2030)['cash_B'] - core['cash_B'],
                'fraction_of_added2030value_from_cash_after2030': 1 - (value(rows, rate, 2030)['cash_B'] - core['cash_B']) / gap_equity,
                'CPU_margin_uplift_percentage_points_by2030': uplift * 100,
                'margin_threshold_case': summarize(rows, rate),
                'marginal_Dec2030_price_per_one_CPU_margin_point_USD': coefficient / 100})
    assert max(margin_checks + cash_checks) < 1e-9
    changes = []
    for index, rate in enumerate(POLICY['rates']):
        core = cases['core'][index]
        joint = cases['Foundry_breakeven_and_packaging_no_positive_profit'][index]
        changes.append({'rate': rate,
            'joint_reduction_in_Dec2026_equity_value_USD': core['Dec2026_planning_value_USD'] - joint['Dec2026_planning_value_USD'],
            'joint_reduction_fraction_of_Dec2026_equity_value': 1 - joint['Dec2026_planning_value_USD'] / core['Dec2026_planning_value_USD'],
            'joint_reduction_in_Dec2030_target_USD': core['Dec2030_target_USD'] - joint['Dec2030_target_USD'],
            'interpretation': 'Conditional exposure to two profit paths, not sum-of-parts or probabilityweightedexpectedloss.'})
    result = {'computed_utc': datetime.now(timezone.utc).isoformat(),
        'input_hashes': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in (ACTIVE_PATH, PRIOR_PATH, POLICY_PATH)},
        'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'quote_USD': POLICY['quote_USD'], 'quote_date': POLICY['quote_date'], 'exit_date': POLICY['exit_date'],
        'years_to_exit': HORIZON, 'shares_B': SHARES, 'baseline_APV': baseline,
        'profit_ablations': cases, 'profit_path_concentration': changes,
        'reverse_operating_thresholds': reverse, 'terminal_efficiency_upper_bound': bound,
        'checks': {'independent_APV_comparisons': len(errors), 'APV_max_error_B_or_USD': max(errors),
            'cash_identity_comparisons': len(row_errors), 'cash_identity_max_error_B': max(row_errors),
            'linear_margin_revaluation_max_error_USD': max(margin_checks),
            'cash_equivalent_revaluation_max_error_USD': max(cash_checks)},
        'interpretation': [
            'The business recovery and current investment attractiveness are separate claims. Reverse requirements are measurable burdens, not supported forecasts.',
            'A return below a chosen hurdle is not proof of overvaluation. No probabilities or risk-adjusted expectedreturns are inferred from unweighted cases.',
            'Packaging ablation retains investment and revenue but removes positive profit. It is zero-margin execution stress, not business removal.',
            'Foundry breakeven still assumes substantial recovery from current losses. The joint case does not eliminate factory-recovery dependence.',
            'Ablations retain CPU price/mix, post2030growth, terminalprofitability, client andcustomsilicon assumptions. Positivejointreturns do not establish protected downside.',
            'December2026 planningvalue is a differentdate from November6quote. No contemporaneous intrinsicvalue has been calculated.',
            'APV adds taxshields/netclaims once. Pre2030 cashbenefits enter2030cash once and are not also counted in2030operatingvalue.',
            'Reverse CPUmargin improvement holds investment unchanged. Evidence is needed for durableadvantage, fundingcosts and ownership economics.',
            'Weak long returns or a lowerplanningvalue do not establish profitable short. Coverpricepath, timing, financing andadverseoutcomes must support a short separately.'
        ]}
    (OUT / 'valuation_rebuild_results.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'checks': result['checks'], 'ablations': cases, 'reverse': reverse, 'terminal_bound': bound}, indent=2))


if __name__ == '__main__':
    main()

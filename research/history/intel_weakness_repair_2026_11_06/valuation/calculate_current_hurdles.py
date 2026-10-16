import copy
import hashlib
import json
import math
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path('/Users/thomasou/Documents/Codex/2026-11-02/lo')
OUT = Path(__file__).resolve().parent
ACTIVE_PATH = ROOT / 'work/three_hour/active_research/intel_market_share_thesis_2026_11_06/root/active_case.json'
ACTIVE = json.loads(ACTIVE_PATH.read_text())
BASE = {int(y): r for y, r in ACTIVE['annual_rows'].items()}
FUND = {int(y): r for y, r in ACTIVE['treasury'].items()}
RESEARCH = ROOT / 'work/three_hour/active_research'
HOST_PATH = RESEARCH / 'pricing_and_competition_review_2026_11_04/intel_server_ASP_mix_operating_policy.json'
PACK_PATH = RESEARCH / 'intel_competition_screen_2026_11_04/external_packaging_operating_policy_2026_11_04.json'
HOST = {r['year']: r for r in json.loads(HOST_PATH.read_text())['annual_rows']}
PACK = {r['year']: r for r in json.loads(PACK_PATH.read_text())['annual_rows']}
SHARES, G, ENTRY = 5.51, .03, 52.25
YEARS = (date(2030, 12, 31) - date(2026, 11, 5)).days / 365.25


def close_cash(row: dict) -> None:
    row['ordinary_operating_tax_B'] = max(row['EBIT_B'], 0) * row['tax_rate']
    row['NOPAT_B'] = row['EBIT_B'] - row['ordinary_operating_tax_B']
    row['net_operating_investment_B'] = row['physical_capex_B'] - row['DA_B'] + row['WC_cash_use_B']
    row['parent_unlevered_cash_B'] = (
        row['NOPAT_B'] - row['net_operating_investment_B']
        - row['lease_cash_B'] - row['minority_cash_B']
        + row['old_credit_collection_B'] + row['new_credit_collection_B']
        - row['credit_basis_loss_tax_B']
    )


def value(rows: dict, rate: float) -> dict:
    values = {}
    for endpoint in (2026, 2030):
        explicit = math.fsum(rows[y]['parent_unlevered_cash_B'] / (1 + rate) ** (y - endpoint)
                             for y in range(endpoint + 1, 2041))
        terminal = rows[2041]['parent_unlevered_cash_B'] / (rate - G) / (1 + rate) ** (2040 - endpoint)
        shield = math.fsum(rows[y]['financing_shield_B'] / (1 + rate) ** (y - endpoint)
                           for y in range(endpoint + 1, 2041))
        shield += rows[2041]['financing_shield_B'] / rate / (1 + rate) ** (2040 - endpoint)
        cash = ACTIVE['values'][str(endpoint)]['cash_B']
        if endpoint == 2030:
            cash += sum(rows[y]['parent_unlevered_cash_B'] - BASE[y]['parent_unlevered_cash_B'] for y in range(2027, 2031))
        debt = ACTIVE['values'][str(endpoint)]['debt_B']
        escrow = math.fsum(FUND[y]['escrow_cash_B'] / (1 + rate) ** (y - endpoint) for y in range(endpoint + 1, 2031))
        acquisition = math.fsum(FUND[y]['Classiq_cash_B'] / (1 + rate) ** (y - endpoint) for y in range(endpoint + 1, 2031))
        equity = explicit + terminal + shield + cash - debt + 4.502 + escrow - acquisition
        values[str(endpoint)] = {
            'price_USD': equity / SHARES, 'equity_B': equity,
            'explicit_operating_PV_B': explicit, 'terminal_operating_PV_B': terminal,
            'financing_shield_PV_B': shield, 'cash_B': cash, 'debt_B': debt,
            'remaining_escrow_PV_B': escrow, 'remaining_acquisition_PV_B': acquisition,
        }
    return values


def summarize(rows: dict, rate: float) -> dict:
    values = value(rows, rate)
    target = values['2030']['price_USD']
    terminal = rows[2041]
    return {
        'rate': rate, 'planning_value_USD': values['2026']['price_USD'],
        'target2030_USD': target, 'annual_price_return': (target / ENTRY) ** (1 / YEARS) - 1,
        'terminal_NOPAT_B': terminal['NOPAT_B'],
        'terminal_net_investment_B': terminal['net_operating_investment_B'],
        'terminal_reinvestment_fraction': terminal['net_operating_investment_B'] / terminal['NOPAT_B'],
        'terminal_implied_incremental_ROC': G * terminal['NOPAT_B'] / terminal['net_operating_investment_B'],
        'terminal_cash_B': terminal['parent_unlevered_cash_B'],
        'CPU_2030_B': rows[2030]['CPU_revenue_B'], 'CPU_2040_B': rows[2040]['CPU_revenue_B'],
        'CPU_CAGR2030to2040': (rows[2040]['CPU_revenue_B'] / rows[2030]['CPU_revenue_B']) ** .1 - 1,
        'net_investment2031to2040_B': sum(rows[y]['net_operating_investment_B'] for y in range(2031, 2041)),
        'entry_ceiling_for_annual_return': {str(h): target / (1 + h) ** YEARS for h in [.10, .12, .15]},
    }


def terminal_roc_rows(roc: float) -> dict:
    rows = copy.deepcopy(BASE)
    new_investment = G * rows[2041]['NOPAT_B'] / roc
    rows[2041]['physical_capex_B'] += new_investment - rows[2041]['net_operating_investment_B']
    close_cash(rows[2041])
    return rows


def growth_shift_rows(shift: float) -> dict:
    rows = copy.deepcopy(BASE)
    ratio = BASE[2030]['Foundry_profit_B'] / BASE[2030]['Products_revenue_B']
    for y in range(2031, 2042):
        row, prior = rows[y], rows[y - 1]
        growth = .03 if y == 2041 else BASE[y]['CPU_revenue_B'] / BASE[y - 1]['CPU_revenue_B'] - 1 + shift
        row['CPU_revenue_B'] = prior['CPU_revenue_B'] * (1 + growth)
        delta = row['CPU_revenue_B'] - BASE[y]['CPU_revenue_B']
        for key in ['DCAI_revenue_B', 'Products_revenue_B', 'consolidated_revenue_B', 'host_capital_revenue_B']:
            row[key] = BASE[y][key] + delta
        row['DCAI_profit_B'] = BASE[y]['DCAI_profit_B'] + delta * row['CPU_margin']
        row['Foundry_profit_B'] = BASE[y]['Foundry_profit_B'] + delta * ratio
        row['EBIT_B'] = BASE[y]['EBIT_B'] + delta * (row['CPU_margin'] + ratio)
        growth_delta = (row['host_capital_revenue_B'] - prior['host_capital_revenue_B']
                        - BASE[y]['host_capital_revenue_B'] + BASE[y - 1]['host_capital_revenue_B'])
        row['WC_cash_use_B'] = BASE[y]['WC_cash_use_B'] + .1 * growth_delta
        row['DA_B'] = HOST[y]['DA_fraction_of_Products_revenue'] * row['Products_revenue_B'] + PACK[y]['incremental_DA_B']
        investment = BASE[y]['net_operating_investment_B'] + growth_delta / .8
        row['physical_capex_B'] = row['DA_B'] + investment - row['WC_cash_use_B']
        close_cash(row)
    return rows


def solve(function, lower: float, upper: float, endpoint: str, rate: float, target: float) -> dict:
    low_value = value(function(lower), rate)[endpoint]['price_USD']
    high_value = value(function(upper), rate)[endpoint]['price_USD']
    if not low_value <= target <= high_value:
        return {'bracketed': False, 'lower_value': low_value, 'upper_value': high_value, 'target': target}
    for _ in range(80):
        mid = (lower + upper) / 2
        if value(function(mid), rate)[endpoint]['price_USD'] < target:
            lower = mid
        else:
            upper = mid
    parameter = (lower + upper) / 2
    rows = function(parameter)
    return {'bracketed': True, 'parameter': parameter, 'endpoint': endpoint, 'threshold_price_USD': target,
            'residual': value(rows, rate)[endpoint]['price_USD'] - target, **summarize(rows, rate)}


def main() -> None:
    policy = json.loads((OUT / 'policy_before_calculation.json').read_text())
    assert hashlib.sha256(ACTIVE_PATH.read_bytes()).hexdigest() == policy['source_sha256']
    baseline = value(BASE, .10625)
    errors = [abs(result[key] - ACTIVE['values'][year][key]) for year, result in baseline.items() for key in result]
    assert max(errors) < 1e-9, max(errors)
    shifted = growth_shift_rows(0)
    row_errors = [abs(shifted[y][key] - BASE[y][key]) for y in BASE for key in ['CPU_revenue_B', 'EBIT_B', 'net_operating_investment_B', 'parent_unlevered_cash_B']]
    assert max(row_errors) < 1e-9
    active_roc = ACTIVE['terminal']['implied_incremental_ROC']
    roc_control = value(terminal_roc_rows(active_roc), .10625)
    assert abs(roc_control['2026']['price_USD'] - baseline['2026']['price_USD']) < 1e-9
    grid = []
    for rate in policy['rates']:
        for roc in policy['terminal_ROC_grid']:
            grid.append({'terminal_ROC_assumption': roc, **summarize(terminal_roc_rows(roc), rate)})
    thresholds = []
    for rate in policy['rates']:
        for endpoint, target, label in [('2026', ENTRY, 'Planning value equals Nov5 quote; dates differ')]+[
            ('2030', ENTRY * (1 + h) ** YEARS, f'{h:.0%} annual return from Nov5') for h in policy['return_hurdles']]:
            thresholds.append({'name': label, 'growth_shift': solve(growth_shift_rows, -.025, .10, endpoint, rate, target),
                               'terminal_ROC_only': solve(terminal_roc_rows, .05, 10, endpoint, rate, target)})
    by_rate = [{**summarize(BASE, rate), 'twenty_pct_discount_to_Dec2026_value_USD': value(BASE, rate)['2026']['price_USD'] * .8,
                'twenty_pct_target_haircut_then_12pct_return_entry_USD': value(BASE, rate)['2030']['price_USD'] * .8 / 1.12 ** YEARS} for rate in policy['rates']]
    carry = [{'equity_carry_assumption': rate, 'arithmetic_proxy_only': baseline['2026']['price_USD'] / (1 + rate) ** (56 / 365.25)} for rate in [.08, .10, .12]]
    output = {'computed_utc': datetime.now(timezone.utc).isoformat(), 'policy_sha256': hashlib.sha256((OUT/'policy_before_calculation.json').read_bytes()).hexdigest(),
              'source_model_sha256': policy['source_sha256'], 'capital_policy_input_sha256': {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in [HOST_PATH, PACK_PATH]}, 'baseline_checks': {'valuation_comparisons':len(errors),'maximum_error':max(errors),'zero_growth_shift_max_error':max(row_errors)},
              'date_aligned_horizon_years': YEARS, 'baseline_by_rate':by_rate, 'terminal_ROC_sensitivity':grid, 'reverse_thresholds':thresholds,
              'equity_carry_sensitivity_not_fair_value':carry,
              'conclusions':['This analysis does not establish additional upside; it makes the required economic advantage explicit.',
                             'Terminal ROC is not an observed forecast. Lower terminal returns require more reinvestment for unchanged3%growth.',
                             'A reverse threshold is conditional on all other inputs; it does not identify a unique market expectation.',
                             'Date-correct2030 return ceilings are preferable to relabeling Dec2026 value as Nov5 fair value.',
                             'No evidence here justifies reducing the operating rate or raising growth to manufacture cushion.']}
    (OUT/'current_hurdles_results.json').write_text(json.dumps(output,indent=2)+'\n')
    print(json.dumps({'baseline_by_rate':by_rate,'terminal_grid':grid,'thresholds':thresholds,'checks':output['baseline_checks']},indent=2))


if __name__ == '__main__':
    main()

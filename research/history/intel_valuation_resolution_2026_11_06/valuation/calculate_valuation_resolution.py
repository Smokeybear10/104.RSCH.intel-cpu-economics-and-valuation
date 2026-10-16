import hashlib
import json
import math
from datetime import date, datetime, timezone
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[4]
POLICY_PATH = OUT / 'policy_before_calculation.json'
POLICY = json.loads(POLICY_PATH.read_text())
RESEARCH = ROOT / 'work/three_hour/active_research'
ACTIVE_PATH = RESEARCH / 'intel_market_share_thesis_2026_11_06/root/active_case.json'
ACTIVE = json.loads(ACTIVE_PATH.read_text())
ROWS = {int(y): r for y, r in ACTIVE['annual_rows'].items()}
TREASURY = {int(y): r for y, r in ACTIVE['treasury'].items()}
SHARES, GROWTH = 5.51, .03


def net_credit(row: dict) -> float:
    return row['old_credit_collection_B'] + row['new_credit_collection_B'] - row['credit_basis_loss_tax_B']


def normalized_cash(row: dict) -> float:
    return row['parent_unlevered_cash_B'] - net_credit(row)


def horizon(quote: dict) -> float:
    return (date.fromisoformat(POLICY['exit_date']) - date.fromisoformat(quote['date'])).days / 365.25


def annual_return(target: float, quote: dict) -> float:
    return (target / quote['price_USD']) ** (1 / horizon(quote)) - 1


def independent_value(endpoint: int, rate: float) -> dict:
    years = range(endpoint + 1, 2041)
    explicit = math.fsum(ROWS[y]['parent_unlevered_cash_B'] / (1 + rate) ** (y - endpoint) for y in years)
    terminal = ROWS[2041]['parent_unlevered_cash_B'] / (rate - GROWTH) / (1 + rate) ** (2040 - endpoint)
    credit = math.fsum(net_credit(ROWS[y]) / (1 + rate) ** (y - endpoint) for y in years)
    assert net_credit(ROWS[2041]) == 0
    shield = math.fsum(ROWS[y]['financing_shield_B'] / (1 + rate) ** (y - endpoint) for y in years)
    shield += ROWS[2041]['financing_shield_B'] / rate / (1 + rate) ** (2040 - endpoint)
    cash = ACTIVE['values'][str(endpoint)]['cash_B']
    debt = ACTIVE['values'][str(endpoint)]['debt_B']
    net_other = ACTIVE['values'][str(endpoint)]['net_other_assets_B']
    escrow = math.fsum(TREASURY[y]['escrow_cash_B'] / (1 + rate) ** (y - endpoint) for y in range(endpoint + 1, 2031))
    acquisition = math.fsum(TREASURY[y]['Classiq_cash_B'] / (1 + rate) ** (y - endpoint) for y in range(endpoint + 1, 2031))
    operating = explicit + terminal
    bridge = shield + cash - debt + net_other + escrow - acquisition
    equity = operating + bridge
    return {
        'explicit_operating_PV_B': explicit, 'terminal_operating_PV_B': terminal,
        'total_operating_value_B': operating, 'normalized_operating_value_B': operating - credit,
        'future_net_credit_PV_B': credit, 'financing_shield_PV_B': shield,
        'cash_B': cash, 'debt_B': debt, 'net_other_assets_B': net_other,
        'remaining_escrow_PV_B': escrow, 'remaining_acquisition_PV_B': acquisition,
        'nonoperating_and_financing_bridge_B': bridge, 'equity_B': equity, 'price_USD': equity / SHARES,
    }


def cash_conversion(year: int) -> dict:
    row = ROWS[year]
    cash = normalized_cash(row)
    return {
        'year': year, 'EBIT_B': row['EBIT_B'], 'operating_tax_B': row['ordinary_operating_tax_B'],
        'NOPAT_B': row['NOPAT_B'], 'physical_capex_B': row['physical_capex_B'],
        'DA_B': row['DA_B'], 'WC_cash_use_B': row['WC_cash_use_B'],
        'net_operating_investment_B': row['net_operating_investment_B'],
        'lease_cash_B': row['lease_cash_B'], 'minority_cash_B': row['minority_cash_B'],
        'normalized_parent_unlevered_cash_B': cash, 'net_finite_credits_B': net_credit(row),
        'parent_unlevered_cash_including_credits_B': row['parent_unlevered_cash_B'],
        'normalized_cash_to_EBIT': cash / row['EBIT_B'],
        'normalized_cash_to_NOPAT': cash / row['NOPAT_B'],
        'credits_fraction_of_parent_cash': net_credit(row) / row['parent_unlevered_cash_B'],
    }


def reverse_required_exit(quote: dict, rate: float, value: dict, hurdle: float) -> dict:
    target = quote['price_USD'] * (1 + hurdle) ** horizon(quote)
    operating = target * SHARES - value['nonoperating_and_financing_bridge_B']
    normalized = operating - value['future_net_credit_PV_B']
    return {
        'rate': rate, 'hurdle': hurdle, 'required_exit_price_USD': target,
        'required_exit_equity_B': target * SHARES, 'required_operating_value_B': operating,
        'required_normalized_operating_value_B': normalized,
        'diagnostic_operating_value_to_2030_group_EBIT': operating / ROWS[2030]['EBIT_B'],
        'diagnostic_operating_value_to_2030_group_NOPAT': operating / ROWS[2030]['NOPAT_B'],
        'required_trailing2030_normalized_cash_yield': normalized_cash(ROWS[2030]) / normalized,
        'required_forward2031_normalized_cash_yield': normalized_cash(ROWS[2031]) / normalized,
        'required_forward2031_normalized_cash_multiple': normalized / normalized_cash(ROWS[2031]),
        'required_operating_value_above_DCF': operating / value['total_operating_value_B'] - 1,
    }


def case_entries() -> list:
    prior = RESEARCH / 'intel_weakness_repair_2026_11_06'
    hurdles = json.loads((prior / 'valuation/current_hurdles_results.json').read_text())
    joint = json.loads((prior / 'valuation/delivery_joint_results.json').read_text())
    factory = json.loads((prior / 'factory/factory_results.json').read_text())
    cases = [{'case': 'owned core', **row} for row in hurdles['baseline_by_rate']]
    cases += [{'case': '2041 terminal ROC15% only', **row} for row in hurdles['terminal_ROC_sensitivity'] if row['terminal_ROC_assumption'] == .15]
    cases += joint['cases']
    for rate in POLICY['rates']:
        row = factory['cases'][str(rate)]['breakeven_only']
        cases.append({'case': 'Foundry breakeven only', 'rate': rate,
                      'planning_value_USD': row['Dec2026_value_USD'], 'target2030_USD': row['Dec2030_target_USD']})
    result = []
    for row in cases:
        target = row['target2030_USD']
        quote = POLICY['quote']['current']
        ceilings = {str(h): target / (1 + h) ** horizon(quote) for h in POLICY['price_return_hurdles']}
        margin_entry = row['planning_value_USD'] * .8
        result.append({
            'case': row['case'], 'rate': row['rate'],
            'terminal_ROC_assumption': row.get('terminal_ROC_assumption'),
            'Dec2026_planning_value_USD': row['planning_value_USD'], 'Dec2030_target_USD': target,
            'annual_price_return_from_current': annual_return(target, quote),
            'annual_price_return_from_prior_reference': annual_return(target, POLICY['quote']['prior_reference']),
            'current_date_entry_ceiling_by_hurdle': ceilings,
            'twenty_pct_discount_to_Dec2026_value_USD': margin_entry,
            'conditional_entry_min_of_20pct_planning_discount_and_12pct_return_USD': min(margin_entry, ceilings['0.12']),
        })
    return result


def main() -> None:
    for relative, expected in POLICY['input_sha256'].items():
        assert hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() == expected, relative
    values = {str(rate): {str(y): independent_value(y, rate) for y in (2026, 2030)} for rate in POLICY['rates']}
    base = values[str(ACTIVE['operating_rate'])]
    checks = []
    for year in ('2026', '2030'):
        checks += [abs(base[year][key] - expected) for key, expected in ACTIVE['values'][year].items() if key in base[year]]
    assert max(checks) < 1e-9
    conversions = [cash_conversion(y) for y in (2030, 2031, 2040)]
    conversion_errors = []
    for r in conversions:
        rebuilt = r['NOPAT_B'] - r['net_operating_investment_B'] - r['lease_cash_B'] - r['minority_cash_B']
        conversion_errors.append(abs(rebuilt - r['normalized_parent_unlevered_cash_B']))
    assert max(conversion_errors) < 1e-9
    diagnostic = []
    grid = []
    reverse = {name: [] for name in POLICY['quote']}
    rollforward = []
    for rate in POLICY['rates']:
        a, b = values[str(rate)]['2026'], values[str(rate)]['2030']
        diagnostic.append({
            'rate': rate, 'Dec2030_price_USD': b['price_USD'],
            'diagnostic_operating_value_to_2030_group_EBIT': b['total_operating_value_B'] / ROWS[2030]['EBIT_B'],
            'diagnostic_operating_value_to_2030_group_NOPAT': b['total_operating_value_B'] / ROWS[2030]['NOPAT_B'],
            '2030_group_NOPAT_to_parent_operating_value': ROWS[2030]['NOPAT_B'] / b['total_operating_value_B'],
            '2030_parent_cash_including_credits_to_operating_value': ROWS[2030]['parent_unlevered_cash_B'] / b['total_operating_value_B'],
            'trailing2030_normalized_cash_yield': normalized_cash(ROWS[2030]) / b['normalized_operating_value_B'],
            'forward2031_normalized_cash_yield': normalized_cash(ROWS[2031]) / b['normalized_operating_value_B'],
            'forward2031_normalized_cash_multiple': b['normalized_operating_value_B'] / normalized_cash(ROWS[2031]),
        })
        for metric_year in POLICY['exit_metric_years']:
            for assumed_yield in POLICY['normalized_parent_operating_cash_yield_grid']:
                normalized = normalized_cash(ROWS[metric_year]) / assumed_yield
                equity = normalized + b['future_net_credit_PV_B'] + b['nonoperating_and_financing_bridge_B']
                target = equity / SHARES
                grid.append({
                    'rate_for_finite_credits_and_financing_shields': rate,
                    'cash_metric_year': metric_year, 'metric_timing': 'trailing' if metric_year == 2030 else 'forward',
                    'assumed_normalized_parent_operating_cash_yield': assumed_yield,
                    'assumed_cash_multiple': 1 / assumed_yield, 'normalized_operating_value_B': normalized,
                    'Dec2030_equity_B': equity, 'Dec2030_price_USD': target,
                    'annual_price_return_from_current': annual_return(target, POLICY['quote']['current']),
                    'annual_price_return_from_prior_reference': annual_return(target, POLICY['quote']['prior_reference']),
                })
        for name, quote in POLICY['quote'].items():
            reverse[name] += [reverse_required_exit(quote, rate, b, h) for h in POLICY['price_return_hurdles']]
        carried_2026 = a['total_operating_value_B'] * (1 + rate) ** 4
        carried_cash = math.fsum(ROWS[y]['parent_unlevered_cash_B'] * (1 + rate) ** (2030 - y) for y in range(2027, 2031))
        op_error = carried_2026 - carried_cash - b['total_operating_value_B']
        assert abs(op_error) < 1e-9
        changes = {
            'operating_value_time_unwind_before_intervening_cash_B': carried_2026 - a['total_operating_value_B'],
            'less_carried_intervening_operating_cash_B': carried_cash,
            'net_operating_value_increase_B': b['total_operating_value_B'] - a['total_operating_value_B'],
            'treasury_cash_increase_B': b['cash_B'] - a['cash_B'],
            'ordinary_debt_reduction_B': a['debt_B'] - b['debt_B'],
            'financing_shield_value_change_B': b['financing_shield_PV_B'] - a['financing_shield_PV_B'],
            'escrow_receivable_and_acquisition_change_B': -a['remaining_escrow_PV_B'] + a['remaining_acquisition_PV_B'],
        }
        reconstructed_change = math.fsum(changes[key] for key in ['net_operating_value_increase_B', 'treasury_cash_increase_B', 'ordinary_debt_reduction_B', 'financing_shield_value_change_B', 'escrow_receivable_and_acquisition_change_B'])
        equity_error = reconstructed_change - (b['equity_B'] - a['equity_B'])
        assert abs(equity_error) < 1e-9
        rollforward.append({'rate': rate, **changes, 'equity_value_increase_B': reconstructed_change,
                            'price_value_increase_USD': reconstructed_change / SHARES,
                            'operating_rollforward_error_B': op_error, 'equity_rollforward_error_B': equity_error})
    output = {
        'computed_utc': datetime.now(timezone.utc).isoformat(),
        'policy_sha256': hashlib.sha256(POLICY_PATH.read_bytes()).hexdigest(),
        'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'input_sha256': POLICY['input_sha256'], 'model_shares_B': SHARES,
        'quotes_and_horizons': {name: {**q, 'exit_date': POLICY['exit_date'], 'days_to_exit': round(horizon(q) * 365.25), 'years_to_exit': horizon(q)} for name, q in POLICY['quote'].items()},
        'independent_APV': values, 'cash_conversion': conversions,
        'DCF_implied_operating_diagnostics_not_peer_multiples': diagnostic,
        'exit_cash_yield_sensitivity_not_selected_fair_value': grid,
        'reverse_exit_requirements': reverse,
        'verified_case_current_entry_and_return': case_entries(),
        'Dec2026_to_Dec2030_equity_value_rollforward': rollforward,
        'checks': {'active_baseline_comparisons': len(checks), 'active_baseline_maximum_error': max(checks), 'cash_conversion_maximum_error': max(conversion_errors)},
        'conclusions': [
            'The accounting bridge and future-price return arithmetic can be repaired and independently reproduced. This does not repair thin expected return at the current quote.',
            'The exit-yield grid is an alternative representation of the same operating forecast, not a peer-calibrated valuation or independent evidence that Intel deserves a chosen multiple.',
            '2030 group EBIT and NOPAT materially exceed normalized parent operating cash. EBIT divided by the current stock price is neither a same-date yield nor a matched ownership-scope metric.',
            'Existing core and stress targets fail a12% price-return hurdle at56.28. More optimistic operating assumptions or a richer exit valuation would be needed to pass, neither justified by this exercise.',
            'A conditional entry ceiling fixes decision discipline, not investment uncertainty. Listed inherited stress returns precede the separate conditional funding overlay; see independent_claims_funding_audit.json. Financing access, fees and daily liquidity remain unresolved.',
            'Dec2026 planning value remains a different date from the Nov6 quote. No new current-date intrinsic fair value, universal margin of safety, scenario probability, or competition win probability is claimed.',
        ],
    }
    destination = OUT / 'valuation_resolution_results.json'
    destination.write_text(json.dumps(output, indent=2) + '\n')
    print(json.dumps({'checks': output['checks'], 'diagnostics': diagnostic, 'cash_conversion': conversions,
                      'current_reverse': reverse['current'], 'output': str(destination)}, indent=2))


if __name__ == '__main__':
    main()

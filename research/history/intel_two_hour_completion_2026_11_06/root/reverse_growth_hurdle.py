import copy
import hashlib
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('integrated', ROOT / 'integrated_model.py')
model = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model)
BASE = model.build_case(delivery='preferred', revised_other=True, component_margin=True, normalized_growth=True)
POOLED = (2.474 + 3.039 - .2 * (.951 + 1.4)) / (6.262 + 7.318 - .951 - 1.4)


def evaluate(growth: float, rate: float, mature_margin: float) -> dict:
    rows = copy.deepcopy(BASE['annual_rows'])
    for year in range(2031, 2042):
        row, previous = rows[year], rows[year - 1]
        row['CPU_revenue_B'] = previous['CPU_revenue_B'] * (1.03 if year == 2041 else 1 + growth)
        row['DCAI_revenue_B'] = row['CPU_revenue_B'] + row['Other_DCAI_B']
        row['Products_revenue_B'] = row['DCAI_revenue_B'] + row['CCPG_revenue_B']
        row['consolidated_revenue_B'] = row['Products_revenue_B'] + row['net_All_Other_B'] + row['legacy_external_Foundry_B'] + row['gross_new_packaging_B']
        row['host_capital_revenue_B'] = row['consolidated_revenue_B'] - row['net_new_packaging_B']
        phase = min((year - 2030) / 10, 1)
        row['CPU_margin'] = rows[2030]['CPU_margin'] + phase * (mature_margin - rows[2030]['CPU_margin'])
        row['DCAI_profit_B'] = row['CPU_revenue_B'] * row['CPU_margin'] + row['Other_DCAI_B'] * row['Other_DCAI_margin']
        row['DCAI_margin'] = row['DCAI_profit_B'] / row['DCAI_revenue_B']
        row['Foundry_profit_B'] = rows[2030]['Foundry_profit_B'] / rows[2030]['Products_revenue_B'] * row['Products_revenue_B']
        row['EBIT_B'] = sum(row[key] for key in ['DCAI_profit_B', 'CCPG_profit_B', 'Foundry_profit_B', 'net_packaging_profit_B', 'Other_profit_less_corporate_B'])
        host_growth = row['host_capital_revenue_B'] - previous['host_capital_revenue_B']
        pack = model.PACK[year]
        row['DA_B'] = model.HOST[year]['DA_fraction_of_Products_revenue'] * row['Products_revenue_B'] + pack['incremental_DA_B']
        row['WC_cash_use_B'] = .1 * host_growth + pack['incremental_WC_cash_use_B']
        investment = host_growth / .8 + pack['incremental_net_operating_investment_B']
        row['physical_capex_B'] = row['DA_B'] + investment - row['WC_cash_use_B']
        model.close_cash(row)
    model.R = rate
    result = model.value(rows)
    model.R = .11555
    return result


def solve(rate: float, margin: float, endpoint: int, target: float) -> dict:
    lower, upper = 0, .25
    assert evaluate(lower, rate, margin)['values'][endpoint]['price_USD'] < target
    assert evaluate(upper, rate, margin)['values'][endpoint]['price_USD'] > target
    for _ in range(80):
        midpoint = (lower + upper) / 2
        value = evaluate(midpoint, rate, margin)['values'][endpoint]['price_USD']
        if value < target:
            lower = midpoint
        else:
            upper = midpoint
    growth = (lower + upper) / 2
    result = evaluate(growth, rate, margin)
    rows = result['annual_rows']
    return {'rate': rate, 'mature_CPU_margin': margin, 'threshold_endpoint': endpoint, 'threshold_price': target, 'CPU_growth2031to2040': growth,
            'planning_value': result['values'][2026]['price_USD'], 'target2030': result['values'][2030]['price_USD'],
            'CPU_revenue2030_B': rows[2030]['CPU_revenue_B'], 'CPU_revenue2040_B': rows[2040]['CPU_revenue_B'],
            'consolidated_revenue2040_B': rows[2040]['consolidated_revenue_B'], 'EBIT2040_B': rows[2040]['EBIT_B'],
            'net_investment2031to2040_B': sum(rows[y]['net_operating_investment_B'] for y in range(2031, 2041)),
            'terminal_cash2041_B': rows[2041]['parent_unlevered_cash_B'], 'residual': result['values'][endpoint]['price_USD'] - target,
            'near_term_unchanged': all(rows[y] == BASE['annual_rows'][y] for y in range(2027, 2031))}


def main() -> None:
    check = evaluate(1.02 ** 2 - 1, .11555, model.P['mature_CPU_margin'])
    errors = [abs(check['annual_rows'][y][k] - row[k]) for y, row in BASE['annual_rows'].items() for k in ['CPU_revenue_B', 'Products_revenue_B', 'EBIT_B', 'physical_capex_B', 'parent_unlevered_cash_B']]
    assert max(errors) < 1e-9
    cases = []
    for rate in [.11555, .10625]:
        for margin in [model.P['mature_CPU_margin'], POOLED]:
            for endpoint, target in [(2026, 52.25), (2030, 52.25 * 1.1 ** model.YEARS)]:
                cases.append(solve(rate, margin, endpoint, target))
    output = {'computed_utc': datetime.now(timezone.utc).isoformat(), 'policy_sha256': hashlib.sha256((ROOT / 'reverse_growth_policy.json').read_bytes()).hexdigest(), 'baseline_checks': len(errors), 'baseline_max_error': max(errors), 'cases': cases}
    (ROOT / 'reverse_growth_results.json').write_text(json.dumps(output, indent=2) + '\n')
    print(json.dumps(output, indent=2))


if __name__ == '__main__':
    main()

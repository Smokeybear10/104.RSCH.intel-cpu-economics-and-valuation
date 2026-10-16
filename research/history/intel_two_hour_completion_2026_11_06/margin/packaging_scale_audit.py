import copy
import hashlib
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path


OUT = Path(__file__).resolve().parent
ENGINE = OUT.parent / 'root/integrated_model.py'
POLICY = OUT / 'packaging_scale_stress_policy.json'
spec = importlib.util.spec_from_file_location('packaging_scale_model', ENGINE)
model = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model)
policy = json.loads(POLICY.read_text())
base = model.build_case(delivery='preferred', revised_other=True, component_margin=True, normalized_growth=True)
fraction = policy['retained_gross_fraction']


def calculate(avoid_cash_cost: bool, base_case: dict | None = None) -> dict:
    selected = base if base_case is None else base_case
    rows = copy.deepcopy(selected['annual_rows'])
    audit = []
    prior_new_sales = 0.0
    for year, row in rows.items():
        original = selected['annual_rows'][year]
        program = model.PACK[year]
        gross = original['gross_new_packaging_B'] * fraction
        net = gross - original['shadow_packaging_B']
        old_net = original['net_new_packaging_B']
        lost = old_net - net
        da = program['incremental_DA_B']
        cash_cost = old_net - original['net_packaging_profit_B'] - da
        assert 0 <= net < old_net
        assert cash_cost > 0
        avoided = cash_cost * lost / old_net if avoid_cash_cost else 0
        profit_delta = -lost + avoided
        new_wc = .15 * (net - prior_new_sales)
        old_wc = program['incremental_WC_cash_use_B']
        if year <= 2030:
            new_capex = program['incremental_physical_cash_capex_B']
        else:
            new_net_investment = net - prior_new_sales
            new_capex = da + new_net_investment - new_wc
        capex_delta = new_capex - program['incremental_physical_cash_capex_B']
        wc_delta = new_wc - old_wc
        row['gross_new_packaging_B'] = gross
        row['net_new_packaging_B'] = net
        row['consolidated_revenue_B'] -= lost
        row['net_packaging_profit_B'] += profit_delta
        row['EBIT_B'] += profit_delta
        row['physical_capex_B'] += capex_delta
        row['WC_cash_use_B'] += wc_delta
        model.close_cash(row)
        assert abs(row['consolidated_revenue_B'] - row['net_new_packaging_B'] - row['host_capital_revenue_B']) < 1e-10
        assert abs(row['EBIT_B'] - original['EBIT_B'] - profit_delta) < 1e-10
        assert abs(row['net_packaging_profit_B'] - (net - (cash_cost - avoided) - da)) < 1e-10
        if year <= 2030:
            assert row['physical_capex_B'] == original['physical_capex_B']
        else:
            assert abs(new_capex - da + new_wc - (net - prior_new_sales)) < 1e-10
        for field in ['CPU_revenue_B', 'client_revenue_B', 'Other_DCAI_B', 'DCAI_profit_B', 'CCPG_profit_B', 'Foundry_profit_B', 'shadow_packaging_B', 'host_capital_revenue_B', 'DA_B', 'lease_cash_B', 'minority_cash_B', 'old_credit_collection_B', 'new_credit_collection_B']:
            assert row[field] == original[field]
        audit.append({
            'year': year,
            'selected_gross_sales_B': original['gross_new_packaging_B'],
            'stressed_gross_sales_B': gross,
            'unchanged_shadow_sales_B': original['shadow_packaging_B'],
            'selected_net_sales_B': old_net,
            'stressed_net_sales_B': net,
            'lost_sales_B': lost,
            'selected_net_incremental_EBIT_B': original['net_packaging_profit_B'],
            'stressed_net_incremental_EBIT_B': row['net_packaging_profit_B'],
            'selected_incremental_cash_operating_cost_B': cash_cost,
            'avoided_cash_cost_B': avoided,
            'unchanged_incremental_DA_B': da,
            'group_EBIT_delta_B': profit_delta,
            'stressed_incremental_capex_B': new_capex,
            'incremental_capex_delta_B': capex_delta,
            'stressed_incremental_WC_cash_B': new_wc,
            'incremental_WC_cash_delta_B': wc_delta,
            'lost_sales_fraction_of_selected_incremental_sales': lost / old_net,
        })
        prior_new_sales = net
    terminal = audit[-1]
    previous = audit[-2]
    for field in ['stressed_gross_sales_B', 'stressed_net_sales_B', 'selected_incremental_cash_operating_cost_B', 'avoided_cash_cost_B', 'unchanged_incremental_DA_B', 'stressed_net_incremental_EBIT_B', 'stressed_incremental_capex_B', 'stressed_incremental_WC_cash_B']:
        if abs(previous[field]) > 1e-12:
            assert abs(terminal[field] / previous[field] - 1.03) < 1e-10, field
    opening_cash_delta = selected['values'][2026]['cash_B'] - model.FUND[2027]['opening_economic_cash_B']
    case = model.value(rows, opening_cash_delta)
    return {'case': case, 'packaging_rows': audit}


def summary(case: dict) -> dict:
    target = case['values'][2030]['price_USD']
    return {
        'planning_value_USD': case['values'][2026]['price_USD'],
        'target2030_USD': target,
        'target_change_vs_selected_USD': target - base['values'][2030]['price_USD'],
        'annual_price_return': (target / model.ENTRY) ** (1 / model.YEARS) - 1,
        'gross_packaging2030_B': case['annual_rows'][2030]['gross_new_packaging_B'],
        'net_incremental_packaging2030_B': case['annual_rows'][2030]['net_new_packaging_B'],
        'net_incremental_packaging_EBIT2030_B': case['annual_rows'][2030]['net_packaging_profit_B'],
        'group_EBIT2030_B': case['annual_rows'][2030]['EBIT_B'],
        'owner_cash2027to2030_B': sum(r['owner_cash_B'] for r in case['treasury'].values()),
        'minimum_annual_cash_B': case['minimum_annual_cash_B'],
        'requires_financing_extension': case['requires_financing_extension'],
    }


def main() -> None:
    cases = {
        'proportional_cash_cost_avoidance': calculate(True),
        'no_cash_cost_avoidance': calculate(False),
    }
    result = {
        'computed_utc': datetime.now(timezone.utc).isoformat(),
        'input_sha256': {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in [ENGINE, POLICY, *model.FILES.values()]},
        'policy': policy,
        'selected': summary(base),
        'summaries': {name: summary(data['case']) for name, data in cases.items()},
        'packaging_rows': {name: data['packaging_rows'] for name, data in cases.items()},
        'valuation': {name: data['case']['values'] for name, data in cases.items()},
        'checks': {
            'gross_minus_shadow_equals_nonnegative_net_incremental_sales': True,
            'host_capital_revenue_and_profit_unchanged': True,
            'all_2027_2030_physical_capex_and_all_DA_unchanged': True,
            'post2030_maintenance_retained_growth_capital_resized_once': True,
            'group_EBIT_changes_once_by_lost_sales_less_avoidable_cash_cost': True,
            'shadow_profit_not_removed_twice': True,
            'no_CPU_decremental_or_extra_foundry_absorption_penalty': True,
            'steady_terminal_packaging_cash_components_grow_three_percent': True,
        },
        'limits': [
            'No primary customer volumes or fees validate the selected or stressed sales. One missing customer family is an analyst scenario, not news of a lost contract.',
            'The optimistic endpoint scales modeled cash operating costs, not EBIT margin; unchanged D&A makes the new margin lower.',
            'The adverse endpoint keeps every operating cost despite lower throughput. Actual material cost avoidance or contract penalties could change the result.',
            'Full planned maintenance is retained after 2030 even for underused capacity. A future capital-rationalization decision could improve cash flow; none is assumed here.',
            'Current treasury interest assumptions remain fixed. No annual cash-floor breach is found; intrayear liquidity is not independently modeled.',
        ],
    }
    (OUT / 'packaging_scale_results.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'selected': result['selected'], 'summaries': result['summaries']}, indent=2))


if __name__ == '__main__':
    main()

import json
from datetime import datetime, timezone
from pathlib import Path

root = Path(__file__).resolve().parent
source = 'https://www.intc.com/filings-reports/all-sec-filings/content/0000050863-26-000191/intc-20260926.htm'
actual = {'DCAI_revenue_B': 7.318, 'DCAI_OI_B': 3.039, 'Other_DCAI_revenue_rounded_B': 1.4}
other_weight = 0.2474832777081776
cpu_weight = 1 - other_weight
target_margin = 0.4


def cpu_margin(current_other_margin):
    return (actual['DCAI_OI_B'] - actual['Other_DCAI_revenue_rounded_B'] * current_other_margin) / (actual['DCAI_revenue_B'] - actual['Other_DCAI_revenue_rounded_B'])


def scenario(current_other_margin, future_other_margin, price_factor=0.9, quantity_factor=1.0, fixed_fraction=0.0, fixed_cost_growth=0.0):
    cpu_margin_anchor = cpu_margin(current_other_margin)
    cpu_cost = cpu_weight * (1 - cpu_margin_anchor)
    cpu_sales = cpu_weight * price_factor * quantity_factor
    other_sales = other_weight
    variable_cost = cpu_cost * (1 - fixed_fraction) * quantity_factor
    fixed_cost = cpu_cost * fixed_fraction * (1 + fixed_cost_growth)
    revenue = cpu_sales + other_sales
    other_profit = other_sales * future_other_margin
    profit_before_extra_savings = cpu_sales - variable_cost - fixed_cost + other_profit
    allowed_cpu_cost = cpu_sales + other_profit - target_margin * revenue
    saving_needed = variable_cost + fixed_cost - allowed_cpu_cost
    variable_cut = saving_needed / variable_cost
    total_cut = saving_needed / (variable_cost + fixed_cost)
    return {
        'current_Other_margin': current_other_margin,
        'future_Other_margin': future_other_margin,
        'inferred_Q3_CPU_margin': cpu_margin_anchor,
        'mature_blend_before_price_volume_changes': cpu_weight * cpu_margin_anchor + other_weight * future_other_margin,
        'CPU_price_change': price_factor - 1,
        'CPU_quantity_change': quantity_factor - 1,
        'fixed_fraction_of_initial_CPU_expenses': fixed_fraction,
        'fixed_expense_growth': fixed_cost_growth,
        'CPU_revenue_after_change_per_initial_total_DCAI_revenue': cpu_sales,
        'CPU_expense_before_extra_savings_per_initial_total_DCAI_revenue': variable_cost + fixed_cost,
        'Other_revenue_after_change_per_initial_total_DCAI_revenue': other_sales,
        'DCAI_margin_before_extra_savings': profit_before_extra_savings / revenue,
        'required_total_CPU_expense_reduction': total_cut,
        'required_variable_CPU_expense_reduction_if_fixed_expenses_unchanged_after_stated_growth': variable_cut,
        'saving_amount_per_initial_total_DCAI_revenue': saving_needed,
        'post_saving_DCAI_margin_check': (cpu_sales - variable_cost * (1 - variable_cut) - fixed_cost + other_profit) / revenue,
    }


main = scenario(0.2, 0.2)
same_margin_grid = [scenario(m, m) for m in [0, 0.1, 0.2, 0.3, 0.4]]
independent_other_grid = [scenario(now, later) for now in [0.1, 0.2, 0.3] for later in [0.1, 0.2, 0.3]]
volume_fixed_grid = [scenario(0.2, 0.2, quantity_factor=q, fixed_fraction=f, fixed_cost_growth=g) for q in [0.9, 1.0, 1.2] for f in [0, 0.2, 0.4] for g in [0, 0.1]]
price_grid = [scenario(0.2, 0.2, price_factor=p) for p in [0.8, 0.9, 0.95, 1.0, 1.1, 1.2]]
allocation_grid = []
for eligible_fraction in [0.25, 0.5, 0.75, 1.0]:
    for package_fraction, package_inflation in [(0, 0), (0.1, 0.1), (0.2, 0.1)]:
        if eligible_fraction + package_fraction > 1:
            continue
        needed = (main['required_total_CPU_expense_reduction'] + package_fraction * package_inflation) / eligible_fraction
        allocation_grid.append({
            'eligible_cost_pool_share_of_initial_CPU_expenses': eligible_fraction,
            'separate_package_charge_share_of_initial_CPU_expenses': package_fraction,
            'package_charge_increase': package_inflation,
            'required_reduction_in_eligible_cost_pool': needed,
        })
required_cpu_margin_grid = [
    {'future_Other_margin': m, 'required_CPU_margin_for_40pct_mature_DCAI': (target_margin - other_weight * m) / cpu_weight}
    for m in [0, 0.1, 0.2, 0.3, 0.4]
]
for row in same_margin_grid + independent_other_grid + volume_fixed_grid + price_grid:
    assert abs(row['post_saving_DCAI_margin_check'] - target_margin) < 1e-12
assert abs(main['DCAI_margin_before_extra_savings'] - 0.3515247129940468) < 1e-12
assert abs(main['required_total_CPU_expense_reduction'] - 0.11159715509987911) < 1e-12

result = {
    'prepared_utc': datetime.now(timezone.utc).isoformat(),
    'purpose': 'Translate the mature 40% DCAI judgment into conditional CPU expense-retention hurdles. No valuation, target, forecast or probability is changed.',
    'status': 'Algebraic diagnostics anchored to actual segment totals and owned mature mix. The scenarios are illustrative parameter ranges, not statistical confidence bounds or empirically established cost shares.',
    'observed_anchor': actual,
    'source': {'url': source, 'locator': 'Q3 2026 Note 2 and MD&A DCAI section'},
    'owned_mature_mix': {'Other_revenue_weight': other_weight, 'CPU_revenue_weight': cpu_weight, 'source_file': '../model_audit/other_DCAI_revenue_and_mix_audit.json', 'year': 2040},
    'definition_warning': 'CPU expenses within DCAI are an inferred accounting residual after an assumed Other profit allocation. They include internal manufacturing charges, product development and allocations. They are not disclosed physical CPU manufacturing costs and exclude separately reported corporate SBC, restructuring and certain acquisition charges. No standalone CPU profit is disclosed.',
    'main_consistent_path': main,
    'reportable_main_sentence': 'If Other DCAI earns 20% and Q3 CPU economics persist into the mature revenue mix, DCAI margin is about 40.03%. A 10% CPU ASP decline at unchanged packages and expenses lowers it to 35.15%; restoring 40% requires a further 11.16% reduction in CPU expenses within DCAI. These are conditional accounting sensitivities, not forecasts of price or cost.',
    'rounding_reconciliation': {
        'Q3_CPU_margin_at_Other20': cpu_margin(0.2),
        'CPU_margin_if_reset_initial_mature_blend_to_exact40': (target_margin - other_weight * 0.2) / cpu_weight,
        'exact40_start_post_ASP10_decline_margin': (target_margin - cpu_weight * 0.1) / (1 - cpu_weight * 0.1),
        'exact40_start_required_CPU_expense_reduction': 0.1123121911535343,
        'warning': 'The exact40 start yields 35.11748% and 11.23122%; it must not be mixed with the Q3-carried 40.03236% and 35.15247% path. About 11% is adequate public precision; 11.2% rounds the selected Q3-carried case.'
    },
    'same_current_and_future_Other_margin_sensitivity': same_margin_grid,
    'required_CPU_margin_at_mature_mix': required_cpu_margin_grid,
    'independent_current_future_Other_margin_grid': independent_other_grid,
    'volume_and_fixed_expense_grid': volume_fixed_grid,
    'price_grid_fixed_quantity_and_Other_dollars': price_grid,
    'eligible_cost_pool_and_package_inflation_grid': allocation_grid,
    'equations': {
        'CPU_margin_Q3': '(3.039 − 1.4 × Other_margin_Q3) / (7.318 − 1.4)',
        'normalization': 'Initial total DCAI revenue = 1 at the mature sales mix; CPU revenue = a = 0.7525167 and Other revenue = b = 0.2474833. Initial CPU expense C0 = a × (1 − conditional Q3 CPU margin).',
        'revenue_after_change': 'R = a × q × p + b, where q is CPU package volume factor and p is CPU realized ASP factor. Other dollar revenue remains b.',
        'CPU_expense_before_extra_saving': 'C = C0 × [(1 − f) × q + f × (1 + gF)], where f is an assumed fixed expense fraction and gF its growth. Variable per-package cost initially holds constant.',
        'profit_and_margin': 'Profit = a × q × p − C + b × Other_margin_future. DCAI margin = Profit / R.',
        'required_expense_saving': 'S = 0.40 × R − Profit. Total expense cut = S/C. If only variable expenses can adjust, variable cut = S/[C0 × (1 − f) × q]. A negative result allows an expense increase while still meeting40%; it is not a negative physical cost.',
        'component_cost_model': 'More generally C = C0 × {q × [w × (1+gW) + k × (1+gK) + o × (1+gO)] + f × (1+gF)}, with w+k+o+f=1. These are expense shares and changes within DCAI, not physical Foundry cash-cost shares.',
        'component_hurdle_at_fixed_quantity': 'If only an eligible expense pool w declines and a separate package charge fraction k rises by i, required eligible-pool reduction = (required total expense reduction + k×i)/w.'
    },
    'fixed_variable_limitations': [
        'This is a one-period diagnostic at an illustrative mature scale. It does not freeze Q3 2026 R&D, personnel or depreciation in dollar terms through 2040.',
        'More volume helps only if the specified fixed expense pool really remains fixed and incremental packages can be manufactured, assembled, qualified and sold. Additional capital and working capital are outside this operating-margin illustration.',
        'Fabs can have scarce capacity on one node and underutilization on another. Products expense behavior also depends on internal transfer prices, not solely physical fab utilization.',
        'Holding Other dollars constant lets its revenue weight move mechanically with CPU price and quantity. Keeping revenue weights fixed would require a different Other-sales response and yields different margins.',
        'Current and future Other profitability need not be equal. The independent grid shows the extra uncertainty hidden by assuming a constant 20% margin.',
        'A hypothetical 0–40% Other margin range is not a factual bound. Negative Other margins or margins above40% remain algebraically possible absent disclosure. The range is used to expose dependency, not assign likelihood.'
    ],
    'mapping_actual_evidence_to_forward_parameters': [
        {'evidence': 'Intel reports Intel3 costs down approximately15% and Intel18A40% since Q1 2026.', 'source': 'https://d1io3yog0oux5.cloudfront.net/_47986fe477a6ac84fe34efbcbf38dd13/intel/db/887/9273/prepared_remarks/Q3%2726_Prepared_Remarks.pdf', 'what_it_supports': 'Manufacturing learning has occurred.', 'what_it_cannot_set': 'A further15%/40% reduction after the Q3 anchor, all CPU expense reductions, or the portion passed to DCAI versus retained by Foundry.'},
        {'evidence': 'Q3 filing attributes ASP growth primarily to richer products, and says premium mix raised server unit costs.', 'source': source, 'what_it_supports': 'Price and cost must be modeled together for changing SKU content.', 'what_it_cannot_set': 'The incremental cost percentage of the richer mix or net same-SKU pricing power.'},
        {'evidence': 'Ibiden illustrates1.9x production load for general-purpose server CPUs by2030 with1.3x market and approximately2.5x SAP demand.', 'source': 'https://www.ibiden.com/ir/items/en_kessannsetsumei2026Q2.pdf', 'what_it_supports': 'Package resources can grow faster than CPU unit shipments.', 'what_it_cannot_set': 'A90% increase in Intel package cost, Intel-specific allocation, substrate pricing, or package-yield performance.'},
        {'evidence': 'Ibiden August Q&A describes quarterly pricing discussions, input-cost pass-through and supply/demand conditions.', 'source': 'https://www.ibiden.com/ir/items/en_QA_FY2026Q1.pdf', 'what_it_supports': 'Some substrate price changes can reflect input costs and scarce capacity.', 'what_it_cannot_set': 'Intel customer prices, exact Intel contract escalators, or retained CPU profit after package cost increases.'},
        {'evidence': 'Q3 Note2 says internal prices are intended to approximate market pricing and Foundry carries most depreciation through overhead/inventory.', 'source': source, 'what_it_supports': 'A physical manufacturing saving need not appear in DCAI in the same amount or period.', 'what_it_cannot_set': 'Future transfer-price pass-through, CPU-specific depreciation, or fixed/variable cost fractions.'},
        {'evidence': 'Intel Q4 outlook calls purpose-built silicon mix a gross-margin headwind.', 'source': 'https://d1io3yog0oux5.cloudfront.net/_47986fe477a6ac84fe34efbcbf38dd13/intel/db/887/9273/prepared_remarks/Q3%2726_Prepared_Remarks.pdf', 'what_it_supports': 'A lower-return Other mix is a relevant risk.', 'what_it_cannot_set': 'A20% Other operating margin or its eventual level.'}
    ],
    'price_mix_and_workload_identity': {
        'SKU_level_revenue': 'CPU revenue = sum over SKU i of packages Qi times realized net price Pi. Average package ASP = revenue / sum Qi. A change in the SKU weights can raise ASP without any same-SKU price increase.',
        'SKU_level_segment_expense': 'CPU expenses within DCAI = sum Qi times (internal wafer charges Ti + package/back-end charges Ki + other variable product costs Vi) plus allocated CPU fixed product expenses F. The same SKU weights must be used on the price and expense sides.',
        'group_identity': 'On external sale and after eliminations, internal charges cancel. Group CPU contribution depends on customer price less actual wafer, packaging, component, product and manufacturing costs. Moving the internal charge only reallocates profit.',
        'capacity_identity': 'More cores or chiplets can increase silicon area, package size, layers, assembly steps and testing per package. Package unit growth cannot be assumed to equal wafer or substrate resource growth.',
        'workload_economics': 'Customer value is workload-specific cost per accepted operation, latency/SLA, reliability, energy and software licensing. A higher package ASP can coexist with a lower customer cost per operation if useful performance per package rises faster. This does not by itself identify the profit Intel retains.',
        'illustrative_ratio_only': {'package_price_factor': 1.2, 'useful_performance_factor': 1.3, 'price_per_performance_change': 1.2 / 1.3 - 1, 'status': 'Arithmetic example only, not an Intel performance or price forecast; benchmark configurations and production workloads must match.'},
        'identification_limit': 'Quarterly aggregate ASP and unit growth do not identify SKU weights, same-SKU net prices, physical cost curves or internal transfer revisions. Public benchmarks and list prices can establish alternatives or upgrade value, but cannot uniquely recover those missing variables.'
    },
    'double_counting_controls': [
        'Anchor costs after the Q3 learning already reported. All diagnostic reductions are additional future changes.',
        'Internal transfer-price reductions help DCAI but reduce Foundry revenue; they are not group savings unless physical costs also fall.',
        'For group underwriting, sum Products and Foundry once and reconcile eliminations, capital, R&D and corporate charges. No new node-saving line may be added on top of the existing segment forecasts.',
        'Use current SKU content to define matched price and expense changes. Adding higher core counts or package complexity to both ASP and volume without resource costs would overstate retained profit.',
        'The existing35% retained-profit stress holds sales and investment fixed. It is not a fully repriced10% ASP scenario; do not equate its target value with this algebraic margin exercise.',
        'Never use the hypothetical cost-pool shares in this receipt as measured Intel manufacturing or packaging shares.'
    ],
    'latest_builder_foundry_wording_audit': {
        'file': 'tmp/pdfs/intel_long/build_initial_screen.py',
        'observed_text': 'Q3 Foundry loss narrowed $0.47B YoY, helped by $0.79B lower period charges. Recurring factory improvement remains a forecast.',
        'quantitative_verdict': 'Accurate rounded figures; actual$468M and$793M.',
        'recommended_second_sentence': 'Further factory profit recovery remains a forecast.',
        'reason': 'Real cost learning has already been reported. The uncertainty concerns future profit conversion after expensive node mix, R&D and depreciation, not whether any operating improvement occurred.'
    }
}
(root / 'cpu_expense_retention_sensitivity.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps({'main': main, 'same_other_margin_rows': [{'Other_margin':r['current_Other_margin'],'CPU_margin':r['inferred_Q3_CPU_margin'],'mature_blend':r['mature_blend_before_price_volume_changes'],'post_price_margin':r['DCAI_margin_before_extra_savings'],'expense_cut':r['required_total_CPU_expense_reduction']} for r in same_margin_grid], 'rows_verified':len(same_margin_grid + independent_other_grid + volume_fixed_grid + price_grid)}, indent=2))

import hashlib
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path


OUT = Path(__file__).resolve().parent
ENGINE = OUT.parent / 'root/integrated_model.py'
spec = importlib.util.spec_from_file_location('integrated_intel_for_margin_audit', ENGINE)
model = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model)
own = json.loads((OUT / 'margin_bridge_results.json').read_text())
checks = []
base = model.build_case(delivery='preferred', revised_other=True, component_margin=True, normalized_growth=True)
for row in own['near_term_2027_2030']:
    y = row['year']
    integrated = base['annual_rows'][y]
    for left, right in [
        ('CPU_revenue_B', 'CPU_revenue_B'),
        ('Other_DCAI_revenue_B', 'Other_DCAI_B'),
        ('DCAI_allocated_operating_profit_B', 'DCAI_profit_B'),
        ('CCPG_allocated_operating_profit_B', 'CCPG_profit_B'),
        ('Foundry_allocated_operating_profit_B', 'Foundry_profit_B'),
    ]:
        error = integrated[right] - row[left]
        checks.append(error)
        assert abs(error) < 1e-10, (y, left, error)

for row in own['illustrative_post2030_component_transition']:
    integrated = base['annual_rows'][row['year']]
    for left, right in [
        ('CPU_revenue_B', 'CPU_revenue_B'),
        ('Other_DCAI_revenue_B', 'Other_DCAI_B'),
        ('CCPG_revenue_B', 'CCPG_revenue_B'),
        ('DCAI_operating_profit_B', 'DCAI_profit_B'),
        ('CCPG_operating_profit_B', 'CCPG_profit_B'),
        ('Foundry_operating_profit_B', 'Foundry_profit_B'),
    ]:
        error = integrated[right] - row[left]
        checks.append(error)
        assert abs(error) < 1e-10, (row['year'], left, error)


def summarize(case: dict) -> dict:
    target = case['values'][2030]['price_USD']
    return {
        'planning_value_USD': case['values'][2026]['price_USD'],
        'target2030_USD': target,
        'annual_price_return': (target / model.ENTRY) ** (1 / model.YEARS) - 1,
        'CPU_revenue2040_B': case['annual_rows'][2040]['CPU_revenue_B'],
        'DCAI_margin2040': case['annual_rows'][2040]['DCAI_margin'],
        'Foundry_profit2040_B': case['annual_rows'][2040]['Foundry_profit_B'],
    }


bracket = []
for name, margin in [
    ('YTD2026_selected', own['selected_CPU_margin']),
    ('Q2Q3_pooled', own['pooled_recent_CPU_margin']),
    ('Q3_only', (3.039 - .2 * 1.4) / (7.318 - 1.4)),
]:
    for normalized in [True, False]:
        case = model.build_case(delivery='preferred', revised_other=True, component_margin=True, normalized_growth=normalized, cpu_margin=margin)
        bracket.append({
            'margin_anchor': name,
            'mature_CPU_margin': margin,
            'CPU_growth_path': '2pct_units_2pct_ASP' if normalized else 'prior_fading_unit_growth',
            **summarize(case),
        })

allocation_sensitivities = []
for other_margin in [.1, .2, .3]:
    inferred_cpu = (7.055 - other_margin * 3.3) / (18.632 - 3.3)
    case = model.build_case(delivery='preferred', revised_other=True, component_margin=True, normalized_growth=True, cpu_margin=inferred_cpu, other_margin=other_margin)
    allocation_sensitivities.append({
        'Other_margin': other_margin,
        'CPU_margin_inferred_to_reconcile_same_YTDprofit': inferred_cpu,
        **summarize(case),
    })

foundry_cases = []
for terminal_ratio in [0, .03]:
    case = model.build_case(delivery='preferred', revised_other=True, component_margin=True, normalized_growth=True, foundry_terminal_ratio=terminal_ratio)
    foundry_cases.append({'Foundry_profit_to_Products_revenue_target': terminal_ratio, **summarize(case)})

forty_percent_hurdles = []
for normalized in [True, False]:
    case = model.build_case(delivery='preferred', revised_other=True, component_margin=True, normalized_growth=normalized)
    last = case['annual_rows'][2040]
    other_share = last['Other_DCAI_B'] / last['DCAI_revenue_B']
    for other_margin in [.1, .2, .3]:
        required_cpu = (.4 - other_share * other_margin) / (1 - other_share)
        hypothesis = model.build_case(delivery='preferred', revised_other=True, component_margin=True, normalized_growth=normalized, cpu_margin=required_cpu, other_margin=other_margin)
        forty_percent_hurdles.append({
            'CPU_growth_path': '2pct_units_2pct_ASP' if normalized else 'prior_fading_unit_growth',
            'Other_share2040': other_share,
            'Other_margin': other_margin,
            'CPU_margin_required_for40pct_DCAI2040': required_cpu,
            'extra_CPU_margin_vs_Q3_residual_at_same_Other_allocation': required_cpu - (3.039 - other_margin * 1.4) / (7.318 - 1.4),
            **summarize(hypothesis),
        })

q3_products_revenue = 15.415
q3_products_foundry_profit = 5.324 - 1.853
row2030 = own['near_term_2027_2030'][-1]
incremental_revenue = row2030['Products_revenue_B'] - q3_products_revenue * 4
incremental_profit = row2030['Products_plus_Foundry_profit_B'] - q3_products_foundry_profit * 4
out = {
    'computed_utc': datetime.now(timezone.utc).isoformat(),
    'engine_sha256': hashlib.sha256(ENGINE.read_bytes()).hexdigest(),
    'independent_operating_comparisons': len(checks),
    'maximum_difference_B': max(abs(x) for x in checks),
    'margin_growth_bracket': bracket,
    'allocation_sensitivity_not_new_profit_scenario': allocation_sensitivities,
    'foundry_sensitivity': foundry_cases,
    'forty_percent_DCAI_hypothesis_hurdles': forty_percent_hurdles,
    'remaining_profit_hurdle': {
        'Q3_2026_annualized_Products_revenue_B': 4 * q3_products_revenue,
        'Q3_2026_annualized_Products_plus_Foundry_profit_B': 4 * q3_products_foundry_profit,
        '2030_Products_revenue_B': row2030['Products_revenue_B'],
        '2030_Products_plus_Foundry_profit_B': row2030['Products_plus_Foundry_profit_B'],
        'incremental_profit_per_incremental_revenue': incremental_profit / incremental_revenue,
        'limits': 'Q3 annualization is an illustrative level comparator, not a2026 forecast; mix shifts, client changes and manufacturing costs matter. Ratio is not a measured future incremental margin.',
    },
    'adversarial_findings': [
        'No duplicated Foundry loss or old post2030 decremental was found in the component case. Independent near-term component arithmetic reproduces integrated values.',
        '2%units+2%ASP after2030 is a subjective normalization convention. No primary source identifies it, nor the priorfading8%-to1% unitpath. Display the bracket; do not call either measured.',
        'Using fullYTD rather than Q3 alone is a positive retention judgment plus earnings-cycle allowance, not an empirically identified through-cycle margin. Recent quarter preservation remains a legitimate favorablecase.',
        'Other20% is not observed. If changing the unknownhistoricalallocation, re-inferCPU margin to reconcile the sameDCAI profit. HoldingCPU fixed and loweringfutureOther margin is a distinct operationalunderperformance stress.',
        'Lower CPU sales also save future investment under the capital-turnover rule. This benefit is already included; the valuation reduction is not simply lost revenue timesa margin.',
        'The post2030 proportionaldepreciation schedule is a capital-allocation convention, not a physical retirementforecast. In the engineDA cancels with the replacementcapex base in netinvestment; it is not separately a cashbonus.',
        'Preferred still assumes a substantial manufacturingturnaround by2030. Loweringthe maturemargin andgrowth does not make every survivingoperating assumption conservative.',
        'Periodcharge reductions can create a recurring lowercost level, but the same year-over-year improvement cannot be added repeatedly. Currentmargins alreadycontain observedcost gains.',
    ],
    'policy_status': 'Diagnostic only. No policy changed in response to these equity values. This file must not be described as valuation-blind.',
}
(OUT / 'integrated_margin_audit_results.json').write_text(json.dumps(out, indent=2) + '\n')
print(json.dumps({k: out[k] for k in ['maximum_difference_B', 'margin_growth_bracket', 'allocation_sensitivity_not_new_profit_scenario', 'foundry_sensitivity', 'remaining_profit_hurdle']}, indent=2))

import copy
import hashlib
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path


OUT = Path(__file__).resolve().parent
ENGINE = OUT.parent / 'root/integrated_model.py'
POLICY = OUT / 'foundry_stress_policy.json'
spec = importlib.util.spec_from_file_location('foundry_cost_recovery_model', ENGINE)
model = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model)
policy = json.loads(POLICY.read_text())
base = model.build_case(delivery='preferred', revised_other=True, component_margin=True, normalized_growth=True)
base_rows = base['annual_rows']


def summary(case: dict) -> dict:
    target = case['values'][2030]['price_USD']
    return {
        'planning_value_USD': case['values'][2026]['price_USD'],
        'target2030_USD': target,
        'target_change_vs_selected_USD': target - base['values'][2030]['price_USD'],
        'annual_price_return': (target / model.ENTRY) ** (1 / model.YEARS) - 1,
        'EBIT2030_B': case['annual_rows'][2030]['EBIT_B'],
        'Foundry_profit2030_B': case['annual_rows'][2030]['Foundry_profit_B'],
        'Foundry_profit2040_B': case['annual_rows'][2040]['Foundry_profit_B'],
        'owner_cash2027to2030_B': sum(r['owner_cash_B'] for r in case['treasury'].values()),
        'minimum_annual_cash_B': case['minimum_annual_cash_B'],
        'requires_financing_extension': case['requires_financing_extension'],
    }


cases = {'selected': base}
for name, configuration in policy['scenarios'].items():
    rows = copy.deepcopy(base_rows)
    delay_ratio = 2.5 / base_rows[2032]['Products_revenue_B']
    for year, row in rows.items():
        if name == 'flat_2027_loss':
            profit = configuration['terminal2041_B'] if year == 2041 else configuration['annual_host_Foundry_profit_2027_2040_B']
        elif name == 'two_year_recovery_delay':
            profit = configuration['annual_host_Foundry_profit_2027_2032_B'][year - 2027] if year <= 2032 else delay_ratio * row['Products_revenue_B']
        else:
            profit = configuration['annual_host_Foundry_profit_2027_2030_B'][year - 2027] if year <= 2030 else configuration['after2030_B']
        delta = profit - row['Foundry_profit_B']
        row['Foundry_profit_B'] = profit
        row['EBIT_B'] += delta
        model.close_cash(row)
        assert abs(row['EBIT_B'] - base_rows[year]['EBIT_B'] - delta) < 1e-12
        for field in ['CPU_revenue_B', 'client_revenue_B', 'Other_DCAI_B', 'DCAI_profit_B', 'CCPG_profit_B', 'net_packaging_profit_B', 'physical_capex_B', 'DA_B', 'WC_cash_use_B', 'minority_cash_B', 'old_credit_collection_B', 'new_credit_collection_B']:
            assert row[field] == base_rows[year][field]
    cases[name] = model.value(rows)

profit_uplift = base_rows[2030]['EBIT_B'] - base_rows[2027]['EBIT_B']
foundry_uplift = base_rows[2030]['Foundry_profit_B'] - base_rows[2027]['Foundry_profit_B']
host_da = {y: r['DA_B'] - model.PACK[y]['incremental_DA_B'] for y, r in base_rows.items()}

revenue_proxies = []
actual_run_rate_bridges = []
internal_intensities = {'Q3_2026': 6.286 / 15.415, 'YTD_2026': 17.005 / 43.333}
for anchor, intensity in internal_intensities.items():
    for da_share in [.75, .9, 1.0]:
        rows = []
        for year in [2027, 2030]:
            r = base_rows[year]
            proxy_revenue = intensity * r['Products_revenue_B'] + r['legacy_external_Foundry_B'] + r['shadow_packaging_B']
            proxy_da = da_share * host_da[year]
            rows.append({
                'year': year,
                'internal_Foundry_revenue_to_Products_assumption': intensity,
                'host_Foundry_revenue_proxy_B': proxy_revenue,
                'host_Foundry_profit_B': r['Foundry_profit_B'],
                'host_Foundry_DA_proxy_B': proxy_da,
                'host_Foundry_total_cost_proxy_B': proxy_revenue - r['Foundry_profit_B'],
                'host_Foundry_cost_before_DA_proxy_B': proxy_revenue - r['Foundry_profit_B'] - proxy_da,
                'proxy_operating_margin': r['Foundry_profit_B'] / proxy_revenue,
            })
        revenue_gain = rows[1]['host_Foundry_revenue_proxy_B'] - rows[0]['host_Foundry_revenue_proxy_B']
        pre_da_gain = foundry_uplift + rows[1]['host_Foundry_DA_proxy_B'] - rows[0]['host_Foundry_DA_proxy_B']
        revenue_proxies.append({
            'historical_internal_intensity_anchor': anchor,
            'assumed_Foundry_share_of_host_DA': da_share,
            'rows': rows,
            'revenue_change_B': revenue_gain,
            'required_pre_DA_contribution_improvement_B': pre_da_gain,
            'incremental_pre_DA_contribution_over_proxy_revenue_change': pre_da_gain / revenue_gain,
            'permitted_growth_in_cost_before_DA_B': revenue_gain - pre_da_gain,
            'scope': 'Conditional accounting-dollar hurdle, not an independently identified wafer-volume or cash-cost forecast. Historical transfer intensity need not persist as product mix and outsourcing change. Host includes embedded packaging; incremental overlay excluded.',
        })
        actual_revenue = 4 * 6.697
        actual_profit = 4 * -1.853
        actual_da = da_share * 4 * 3.232
        actual_depreciation = da_share * 4 * (8.933 - 5.891)
        actual_cost_before_da = actual_revenue - actual_profit - actual_da
        actual_cost_before_depreciation = actual_revenue - actual_profit - actual_depreciation
        actual_run_rate_bridges.append({
            'historical_internal_intensity_anchor_for_future_revenue': anchor,
            'assumed_Foundry_share_of_total_DA': da_share,
            'Q3_2026_annualized_revenue_B': actual_revenue,
            'Q3_2026_annualized_operating_profit_B': actual_profit,
            'Q3_2026_annualized_total_DA_allocated_B': actual_da,
            'Q3_2026_annualized_cost_before_DA_proxy_B': actual_cost_before_da,
            '2030_revenue_proxy_B': rows[1]['host_Foundry_revenue_proxy_B'],
            '2030_cost_before_DA_proxy_B': rows[1]['host_Foundry_cost_before_DA_proxy_B'],
            'required_revenue_growth': rows[1]['host_Foundry_revenue_proxy_B'] / actual_revenue - 1,
            'permitted_cost_before_DA_change_B': rows[1]['host_Foundry_cost_before_DA_proxy_B'] - actual_cost_before_da,
            'Q3_2026_annualized_depreciation_only_allocated_B': actual_depreciation,
            'Q3_2026_annualized_cost_before_depreciation_only_proxy_B': actual_cost_before_depreciation,
            'permitted_cost_change_using_depreciation_only_actual_baseline_B': rows[1]['host_Foundry_cost_before_DA_proxy_B'] - actual_cost_before_depreciation,
            'scope': 'Q3 annualization is a level comparison, not a 2026 forecast. The original total-D&A comparison includes amortization excluded from reported segments; the depreciation-only actual baseline is a better scope check. Future allocated host D&A remains an analyst assumption. Inventory timing prevents either from being exact reported segment EBITDA or cash cost.',
        })

annual_hurdles = []
for year in range(2027, 2031):
    prior_profit = -8.5 if year == 2027 else base_rows[year - 1]['Foundry_profit_B']
    prior_da = 12.928 if year == 2027 else host_da[year - 1]
    annual_hurdles.append({
        'year': year,
        'host_Foundry_profit_B': base_rows[year]['Foundry_profit_B'],
        'host_total_DA_B': host_da[year],
        'change_in_Foundry_profit_B': base_rows[year]['Foundry_profit_B'] - prior_profit,
        'change_in_host_total_DA_B': host_da[year] - prior_da,
        'required_pre_DA_improvement_if_all_incremental_host_DA_in_Foundry_B': base_rows[year]['Foundry_profit_B'] - prior_profit + host_da[year] - prior_da,
    })

group_cost_levels = [{
    'period': 'Q3_2026_annualized',
    'external_revenue_B': 4 * 16.513,
    'consolidated_EBIT_B': 4 * 2.522,
    'total_DA_B': 4 * 3.232,
    'cost_less_total_DA_proxy_B': 4 * (16.513 - 2.522 - 3.232),
    'host_Foundry_profit_B': 4 * -1.853,
}]
for year in [2027, 2030, 2040]:
    row = base_rows[year]
    group_cost_levels.append({
        'period': str(year),
        'external_revenue_B': row['consolidated_revenue_B'],
        'consolidated_EBIT_B': row['EBIT_B'],
        'total_DA_B': row['DA_B'],
        'cost_less_total_DA_proxy_B': row['consolidated_revenue_B'] - row['EBIT_B'] - row['DA_B'],
        'host_Foundry_profit_B': row['Foundry_profit_B'],
    })

out = {
    'computed_utc': datetime.now(timezone.utc).isoformat(),
    'input_sha256': {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in [ENGINE, POLICY, *model.FILES.values()]},
    'scope': policy['scope'],
    'summaries': {name: summary(case) for name, case in cases.items()},
    'recovery_materiality': {
        'group_EBIT_increase2027to2030_B': profit_uplift,
        'host_Foundry_EBIT_increase2027to2030_B': foundry_uplift,
        'share_of_group_EBIT_increase': foundry_uplift / profit_uplift,
        'net_packaging_EBIT_increase2027to2030_B': base_rows[2030]['net_packaging_profit_B'] - base_rows[2027]['net_packaging_profit_B'],
        'host_Foundry_plus_net_packaging_share_of_group_EBIT_increase': (foundry_uplift + base_rows[2030]['net_packaging_profit_B'] - base_rows[2027]['net_packaging_profit_B']) / profit_uplift,
        'selected_host_Foundry_profit_to_Products_ratio2030': base_rows[2030]['Foundry_profit_B'] / base_rows[2030]['Products_revenue_B'],
    },
    'annual_pre_DA_hurdles': annual_hurdles,
    'consolidated_cost_hurdle_without_internal_transfer_proxy': {
        'rows': group_cost_levels,
        'Q3_annualized_to_2030_revenue_growth': group_cost_levels[2]['external_revenue_B'] / group_cost_levels[0]['external_revenue_B'] - 1,
        'Q3_annualized_to_2030_cost_less_DA_proxy_growth': group_cost_levels[2]['cost_less_total_DA_proxy_B'] / group_cost_levels[0]['cost_less_total_DA_proxy_B'] - 1,
        'Q3_annualized_to_2027_EBIT_change_B': group_cost_levels[1]['consolidated_EBIT_B'] - group_cost_levels[0]['consolidated_EBIT_B'],
        'Q3_annualized_to_2027_Foundry_profit_change_B': group_cost_levels[1]['host_Foundry_profit_B'] - group_cost_levels[0]['host_Foundry_profit_B'],
        'scope': 'Whole-group arithmetic avoids the assumed internal transfer-price denominator. It remains a hurdle derived from forecast profit, not a cost forecast. Q3 annualization is not a full-year forecast or a normalized comparable quarter. Cash-flow D&A, inventory timing, actual period charges and forecast economic-SBC policies prevent this residual from being literal cash cost.',
    },
    'historical_internal_revenue_intensities': internal_intensities,
    'conditional_revenue_cost_bridges': revenue_proxies,
    'conditional_Q3_annualized_to_2030_bridges': actual_run_rate_bridges,
    'historical_DA_scope_audit': {
        'YTD_depreciation_B': 8.933,
        'H1_depreciation_B': 5.891,
        'Q3_depreciation_B': 8.933 - 5.891,
        'YTD_amortization_B': .659,
        'H1_amortization_B': .469,
        'Q3_amortization_B': .659 - .469,
        'Q3_total_DA_B': 3.232,
        'source_Q3': 'https://www.intc.com/filings-reports/all-sec-filings/content/0000050863-26-000191/intc-20260926.htm',
        'source_Q2': 'https://www.intc.com/filings-reports/all-sec-filings/content/0000050863-26-000157/intc-20260627.htm',
        'locator': 'Consolidated cash-flow statements and Note 2 depreciation/allocation policy',
        'boundary': 'Substantial majority applies to depreciation, not all amortization. Acquisition-related amortization is corporate unallocated. A 100% total-D&A allocation is an upper diagnostic, not a faithful segment accounting estimate. D&A absorbed in inventory further prevents direct mapping to segment-period cost.',
    },
    'scenario_annual_Foundry_profits_B': {name: {str(y): r['Foundry_profit_B'] for y, r in case['annual_rows'].items()} for name, case in cases.items()},
    'scenario_values': {name: case['values'] for name, case in cases.items()},
    'checks': {
        'selected_CPU_client_and_Other_sales_and_profit_unchanged': True,
        'physical_capital_and_claims_unchanged': True,
        'group_EBIT_delta_equals_only_changed_Foundry_profit': True,
        'no_extra_revenue_decremental_or_absorption_overlay': True,
        'no_engine_or_frozen_artifact_modified': True,
    },
    'limits': [
        'Holding future operating profit lower with unchanged sales represents a cost miss, not a calibrated probability or a second volume miss.',
        'Ordinary tax follows existing engine. Existing financing income/cost assumptions are retained; a cash-floor breach requires further financing work.',
        'The full-YTD internal Foundry revenue is 17.005B, from 17.883B gross Foundry less .878B external. Products revenue is 43.333B. Q3 internal is 6.286B on 15.415B Products.',
        'The pre-D&A bridge allocates a stated share of host consolidated D&A to Foundry. It is not reported segment EBITDA or literal cash cost because inventory and other noncash items remain.',
        'No prior inventory-reserve release, asset impairment comparison, or historical node saving is added to future earnings.',
    ],
}
(OUT / 'foundry_recovery_results.json').write_text(json.dumps(out, indent=2) + '\n')
print(json.dumps({'summaries': out['summaries'], 'recovery_materiality': out['recovery_materiality']}, indent=2))

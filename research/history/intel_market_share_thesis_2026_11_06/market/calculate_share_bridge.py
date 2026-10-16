import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


def main() -> None:
    workspace = Path(__file__).resolve().parents[5]
    output = Path(__file__).resolve().parent
    prior = workspace / 'work/three_hour/active_research/intel_two_hour_completion_2026_11_06'
    model_path = prior / 'quarterly/anchor_valuation_overlay_results.json'
    anchor_path = prior / 'quarterly/favorable_anchor_case_results.json'
    original_path = workspace / 'work/three_hour/active_research/intel_competition_screen_2026_11_04/product_operating_forecast_2026_11_04.json'
    model = json.loads(model_path.read_text())
    anchors = json.loads(anchor_path.read_text())
    baseline = json.loads(original_path.read_text())['FY2026_estimated_anchor']['server_CPU_revenue_proxy_B']
    favorable_baseline = anchors['cases']['joint_favorable']['FY2026_revised_product_bases']['CPU_B']
    names = {
        'selected': 'unchanged_anchor__YTD_normalized_growth',
        'favorable': 'joint_anchor_old_CPU2028plus_growth_pooled_old_growth',
    }
    rows = {name: model['cases'][case]['annual_rows'] for name, case in names.items()}
    shares = {
        '2026_estimate': {'Intel': .50, 'AMD': .27, 'NVIDIA': .12, 'AWS': .04, 'Google': .03, 'Others': .04},
        '2027_forecast': {'Intel': .42, 'AMD': .28, 'NVIDIA': .12, 'AWS': .05, 'Google': .06, 'Others': .07},
    }
    assert all(abs(sum(s.values()) - 1) < 1e-12 for s in shares.values())
    near_term = []
    for market_growth in (.40, .45, .50):
        unit_growth = (1 + market_growth) * .42 / .50 - 1
        amd_unit_growth = (1 + market_growth) * .28 / .27 - 1
        for name, path in rows.items():
            revenue = path['2027']['CPU_revenue_B']
            own_baseline = baseline if name == 'selected' else favorable_baseline
            near_term.append({
                'case': name,
                'market_unit_growth': market_growth,
                'Intel_unit_growth_from_rounded_share_forecasts': unit_growth,
                'Intel_CPU2027_B': revenue,
                'common_FY2026_estimate_B': baseline,
                'required_ASP_growth_common_anchor': revenue / baseline / (1 + unit_growth) - 1,
                'case_FY2026_estimate_B': own_baseline,
                'required_ASP_growth_matched_anchor': revenue / own_baseline / (1 + unit_growth) - 1,
                'AMD_unit_growth_from_same_market': amd_unit_growth,
                'AMD_ASP_growth_at_70pct_CPU_revenue_growth': 1.70 / (1 + amd_unit_growth) - 1,
            })
    market_grid = []
    unit_price_grid = []
    tail_grid = []
    for market_2030 in (100., 120., 150., 180., 200., 220.):
        for name, path in rows.items():
            revenue = path['2030']['CPU_revenue_B']
            revenue_share = revenue / market_2030
            own_baseline = baseline if name == 'selected' else favorable_baseline
            market_grid.append({
                'case': name,
                'illustrative_CPU_market2030_B': market_2030,
                'Intel_CPU2030_B': revenue,
                'required_Intel_revenue_share': revenue_share,
                'Intel_revenue_CAGR2026E_2030_matched_anchor': (revenue / own_baseline) ** .25 - 1,
                'illustrative_market_CAGR_from_40B2026': (market_2030 / 40) ** .25 - 1,
                'illustrative_revenue_share_change_pp_from_40B_common_baseline': 100 * (revenue_share - baseline / 40),
            })
            for unit_share in (.25, .30, .35, .40, .42):
                unit_price_grid.append({
                    'case': name,
                    'illustrative_CPU_market2030_B': market_2030,
                    'Intel_unit_share2030_scenario': unit_share,
                    'required_Intel_ASP_over_market_average': revenue_share / unit_share,
                })
            for market_growth in (.04, .06, .08, .10):
                market_2040 = market_2030 * (1 + market_growth) ** 10
                share_2040 = path['2040']['CPU_revenue_B'] / market_2040
                tail_grid.append({
                    'case': name,
                    'CPU_market2030_B': market_2030,
                    'market_revenue_CAGR2031_2040_scenario': market_growth,
                    'CPU_market2040_B': market_2040,
                    'Intel_CPU2040_B': path['2040']['CPU_revenue_B'],
                    'required_Intel_revenue_share2040': share_2040,
                    'share_change_pp_2030_2040': 100 * (share_2040 - revenue_share),
                })
    reverse_share = [
        {'case': name, 'Intel_revenue_share_scenario': share,
         'required_CPU_market2030_B': path['2030']['CPU_revenue_B'] / share}
        for name, path in rows.items() for share in (.25, .30, .35, .40, .45, .50)
    ]
    result = {
        'computed_utc': datetime.now(timezone.utc).isoformat(),
        'input_sha256': {str(p): hashlib.sha256(p.read_bytes()).hexdigest()
                         for p in (model_path, anchor_path, original_path)},
        'case_names': names,
        'formulas': {
            'Intel_unit_growth': '(1 + industry unit growth) * Intel ending unit share / Intel starting unit share - 1',
            'required_ASP_growth': 'Intel revenue2027 / Intel revenue2026E / (1 + Intel unit growth) - 1',
            'revenue_share': 'Intel CPU revenue / comparable total CPU revenue pool',
            'relative_ASP': 'Intel revenue share / Intel unit share',
            'tail_market': 'market2030 * (1 + scenario market revenue CAGR)^10',
        },
        'source_chart_shares': shares,
        'FY2026_baselines': {'selected_estimate_B': baseline, 'favorable_estimate_B': favorable_baseline},
        'near_term_forecast_consistency': near_term,
        'market_revenue_share_grid': market_grid,
        'unit_share_and_relative_ASP_grid': unit_price_grid,
        'reverse_market_size_by_share': reverse_share,
        'post2030_share_consistency': tail_grid,
        'Intel_smooth_path_illustration': {
            'current_TAM_B': 40,
            'five_year_endpoint_B': 200,
            'constant_annual_growth': (200 / 40) ** .2 - 1,
            'four_year_market_B': 40 * (200 / 40) ** .8,
            'scope': 'Owned interpolation of rounded management endpoints; not Intel guidance for2030. The statement was October2026 over five years, roughly2031.',
        },
        'case_tail_CAGRs': {name: (path['2040']['CPU_revenue_B'] / path['2030']['CPU_revenue_B']) ** .1 - 1 for name, path in rows.items()},
        'boundaries': [
            'All market sizes, future share paths and future relative ASPs are conditional scenarios, not measured outcomes or probabilities.',
            'TrendForce chart uses rounded annual2026 estimates and2027 forecasts;17.6% is a calculation at40% market growth, not a strict real-world lower bound.',
            'Intel FY2026 CPU amounts are model estimates using reported DCAI minus rounded Other DCAI plus a modeledQ4. They are not filed full-yearCPU totals.',
            'Intel current$40B TAM is an approximate management snapshot, not a consistently measuredFY2026 market total; shares derived from it are illustrations only.',
            'A comparable dollar pool must treat merchant CPUs, captive designs, bundles and architecture consistently. Public vendorTAM methodology does not fully resolve this.',
            'Revenue share is not shipment share. CPU revenue is not DCAI/DataCenter segment revenue or whole-server spending.',
            'No profit, reinvestment, discount rate or valuation policy was changed by this bridge.',
        ],
    }
    (output / 'market_share_bridge_results.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'near_term': near_term[:2], 'market_grid': [r for r in market_grid if r['illustrative_CPU_market2030_B'] in (120,150,180)], 'tail_CAGRs': result['case_tail_CAGRs']}, indent=2))


if __name__ == '__main__':
    main()

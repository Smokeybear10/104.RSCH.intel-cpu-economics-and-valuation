import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


OUT = Path(__file__).resolve().parent
RESEARCH = OUT.parents[1]
ns = {'__file__': str(OUT / 'extended_scenarios.py')}
exec((OUT / 'extended_scenarios.py').read_text().split('\ncases = ')[0], ns)
ns['OTHER_ASSETS'] -= 1.215
rows = copy.deepcopy(ns['base_rows'])
host, packaging = ns['host'], ns['packaging']
value, close_cash = ns['value'], ns['close_cash']
base = value(rows)
margin35_rows = copy.deepcopy(rows)
transfer40_rows = copy.deepcopy(rows)
diagnostics = []
for year, row in rows.items():
    wedge = .05 * min(max((year - 2030) / 10, 0), 1) * row['DCAI_revenue_B']
    margin35_rows[year]['DCAI_product_margin'] -= .05 * min(max((year - 2030) / 10, 0), 1)
    margin35_rows[year]['EBIT_B'] -= wedge
    close_cash(margin35_rows[year])
    transfer40_rows[year]['illustrative_host_Foundry_profit_after_transfer_B'] = host[year]['Foundry_operating_profit_B'] - wedge
    transfer40_rows[year]['EBIT_B'] -= wedge
    close_cash(transfer40_rows[year])
    diagnostics.append({'year': year, 'DCAI_revenue_B': row['DCAI_revenue_B'], 'selected_DCAI_margin': row['DCAI_product_margin'], 'selected_DCAI_profit_B': row['DCAI_revenue_B'] * row['DCAI_product_margin'], 'selected_host_Foundry_profit_B': host[year]['Foundry_operating_profit_B'], 'real_consolidated_profit_added_by40versus35_B': wedge, 'illustrative_Foundry_profit_if_the_DCAI_uplift_were_only_transfer_reallocation_B': host[year]['Foundry_operating_profit_B'] - wedge})
margin35 = value(margin35_rows)
transfer40 = value(transfer40_rows)
for year in rows:
    assert abs(margin35_rows[year]['EBIT_B'] - transfer40_rows[year]['EBIT_B']) < 1e-12
    assert abs(margin35_rows[year]['parent_unlevered_cash_B'] - transfer40_rows[year]['parent_unlevered_cash_B']) < 1e-12
for endpoint in [2026, 2030]:
    assert abs(margin35['values'][endpoint]['price_USD'] - transfer40['values'][endpoint]['price_USD']) < 1e-12

corporate = {r['year']: r for r in json.loads((RESEARCH / 'intel_competition_screen_2026_11_04/corporate_other_policy.json').read_text())['policy_rows']}
group_bridge = []
for year in [2027, 2028, 2029, 2030, 2035, 2040]:
    row = rows[year]
    dcai = row['DCAI_revenue_B'] * row['DCAI_product_margin']
    ccpg = host[year]['CCPG_operating_profit_B']
    foundry = host[year]['Foundry_operating_profit_B']
    pack = packaging[year]['net_incremental_operating_profit_B']
    other = corporate[year]['other_segment_operating_profit_B'] if year <= 2030 else .7 * 1.03 ** (year - 2030)
    corp = corporate[year]['corporate_total_expense_B'] if year <= 2030 else 5.15 * 1.03 ** (year - 2030)
    error = dcai + ccpg + foundry + pack + other - corp - row['EBIT_B']
    assert abs(error) < 1e-10
    group_bridge.append({'year': year, 'DCAI_profit_B': dcai, 'CCPG_profit_B': ccpg, 'host_Foundry_profit_B': foundry, 'Other_profit_B': other, 'corporate_expense_including_economic_SBC_B': corp, 'net_incremental_external_packaging_profit_B': pack, 'intersegment_profit_elimination_assumption_B': 0, 'consolidated_EBIT_B': row['EBIT_B'], 'bridge_error_B': error, 'Products_plus_host_Foundry_profit_B': dcai + ccpg + foundry})

actual = {'Q3_2026': {'CCPG': 2.285, 'DCAI': 3.039, 'Foundry': -1.853, 'Other': .179, 'corporate': -1.058, 'eliminations': -.070, 'group': 2.522}, 'Q3_2025': {'CCPG': 2.694, 'DCAI': .964, 'Foundry': -2.321, 'Other': .100, 'corporate': -.782, 'eliminations': .028, 'group': .683}}
for row in actual.values():
    assert abs(sum(v for k, v in row.items() if k != 'group') - row['group']) < 1e-12
actual['YoY_change'] = {key: actual['Q3_2026'][key] - actual['Q3_2025'][key] for key in actual['Q3_2026']}
policy_path = OUT / 'transfer_price_independence_policy.json'
result = {
    'computed_utc': datetime.now(timezone.utc).isoformat(),
    'policy_sha256': hashlib.sha256(policy_path.read_bytes()).hexdigest(),
    'conclusion': 'No explicit duplicated manufacturing-saving line or arithmetic double posting found. Product and Foundry profits are economically linked through output, transfer pricing and inventory timing. Separate aggregate segment forecasts with a no-double-credit rule do not independently validate their joint operating economics.',
    'accounting_identity': 'Products profit = external product sales minus internal manufacturing charges minus other product costs. Foundry profit = those same internal charges plus external foundry sales minus actual fabrication, packaging and process-development costs. On sold-through inventory and consistent timing, the internal charge cancels in group EBIT. Internal-price changes alone create no group value.',
    'actual_Q3_profit_bridge_B': actual,
    'forecast_group_EBIT_bridge': group_bridge,
    'current2027_2028_bridge': {'group_EBIT_increase_B': rows[2028]['EBIT_B'] - rows[2027]['EBIT_B'], 'DCAI_profit_increase_B': group_bridge[1]['DCAI_profit_B'] - group_bridge[0]['DCAI_profit_B'], 'host_Foundry_profit_increase_B': 3.25, 'remaining_net_increase_B': rows[2028]['EBIT_B'] - rows[2027]['EBIT_B'] - (group_bridge[1]['DCAI_profit_B'] - group_bridge[0]['DCAI_profit_B']) - 3.25},
    'mature_margin_transfer_diagnostic': {'annual_profit_rows': diagnostics, 'base40_values_with_claim_reserve': base['values'], 'real35_values_with_claim_reserve': margin35['values'], 'reported40_but_Foundry_offset_values_with_claim_reserve': transfer40['values'], 'real40versus35_incremental_planning_value_USD': base['values'][2026]['price_USD'] - margin35['values'][2026]['price_USD'], 'real40versus35_incremental2030value_USD': base['values'][2030]['price_USD'] - margin35['values'][2030]['price_USD'], 'interpretation': 'Starting with the35%economic case, relabeling profit into DCAI until it reports40% leaves group cash and value unchanged when Foundry is reduced equally. This is an identity diagnostic, not a forecast that all the actual uplift is a transfer-price shift.'},
    'existing_policy_lineage': [
        {'file': 'intel_competition_screen_2026_11_04/paired_cpu20_capital080_operating_policy_2026_11_04.json', 'finding': 'Reducing2027unitgrowth30%to20% reduced productmargin0.5point for nonmanufacturing expense absorption AND Foundryprofit0.5/0.75/1/1B for manufacturing absorption. They are distinct specified cost categories, but are aggregate judgments without unit-cost calibration.'},
        {'file': 'pricing_and_competition_review_2026_11_04/intel_server_ASP_mix_operating_policy.json', 'finding': 'The later richer-ASP revision assigns50% incremental CONSOLIDATED EBIT and holds Foundry dollars unchanged.2027incremental2.622924B sales adds1.311462B groupEBIT once.2030incremental6.991574B sales adds3.495787B once; no incremental node-saving line is appended.'},
        {'file': 'intel_decision_pass_2026_11_04/operating_scenario_policy.json', 'finding': 'Maturemargin35-to40 adds the phased difference times DCAI sales once after2030, preserving Foundry dollars. This must mean real externally earned retained profit, not simply a lower internal wafer price.'},
        {'file': 'intel_competition_screen_2026_11_04/corporate_other_policy.json', 'finding': 'Forward intersegment operating eliminations normalized to zero, with no repeating inventory-reserve windfall. SBC is charged once in corporate costs.'}
    ],
    'missing_economic_evidence': [
        'Internal wafer, assembly and test transfer-price schedules and whether future manufacturing learning is passed to Products.',
        'Accepted good-die and complete-package output by node/product; per-unit cash cost, actual yield, utilization and richer-chip/package mix.',
        'A cost-dollar bridge separating variable manufacturing, fixed fab overhead, ongoing14A process R&D and new-node startup expenses.',
        'D&A actually recognized in segment costs versus absorbed into unfinished and finished inventory; Intel says Products attribution is impracticable.',
        'Internal inventory-profit eliminations during the large ramp. Zero future elimination is a normalization, not a demonstrated quarterly sell-through identity.',
        'A separately supported recurring externalFoundry revenue/cost path; its absence prevents fully reconstructing manufacturing economics from the external-sales forecast.',
        'Customer netCPUprices and margins of OtherDCAI to show that retained40%producteconomics survive richer mix and procurement competition.'
    ],
    'manufacturing_hurdle': {'host_Foundry_profit_improvement2026anchor_to2030_B': 11, 'host_total_DA_increase_B': 8.2595, 'annual_pre_DA_contribution_increase_if_all_incremental_DA_in_Foundry_B': 19.2595, 'interpretation': 'An increase in the annual operating-contribution level, not cumulativecash or measuredcostcuts. Revenue/volume can contribute. The attribution of all incrementalD&A toFoundry is diagnostic, not disclosed.'},
    'recommended_defense': 'I do not count a lower internal wafer price as new Intel profit. The product margin is after manufacturing charges; Foundry includes actual production and process-development costs. Internal charges cancel on consolidation. No extra node saving is added to the forecast. But the combined recovery remains an assumption: we need consolidated profit and cash improvement, with inventory and depreciation reconciled, to validate both segment paths together.',
    'sources': [
        {'url': 'https://www.intc.com/filings-reports/all-sec-filings/content/0000050863-26-000191/intc-20260926.htm', 'locator': 'Note2 printed9–11; localq3_10q.txt lines548–566,588–617,638–657', 'support': 'External Products revenue; market-like internal Foundry prices; manufacturing/process development/excess capacity costs; depreciation absorption; inventory eliminations; actual segment and group EBIT.'},
        {'file': 'economic_underwriting/foundry_internal_recovery_cost_bridge.json', 'support': 'Q3Foundry468M improvement equals793M periodcharge relief−219M extraopex−106M inferredproductprofit decline; groupgrossprofit increased1.878B, showing real consolidated progress but not a calibrated future savings pool.'}
    ],
    'checks': {'group_bridge_max_absolute_error_B': max(abs(r['bridge_error_B']) for r in group_bridge), 'transfer_reallocation_has_zero_value_vs_matching35economic_case': True, 'all_frozen_models_unchanged': True},
}
(OUT / 'transfer_price_independence_results.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps({key: result[key] for key in ['conclusion', 'actual_Q3_profit_bridge_B', 'forecast_group_EBIT_bridge', 'current2027_2028_bridge', 'checks']}, indent=2))
print('margin40value', base['values'][2030]['price_USD'], 'transferonly40value', transfer40['values'][2030]['price_USD'], '2040wedge', diagnostics[-2])

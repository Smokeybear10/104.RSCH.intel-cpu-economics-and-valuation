import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path('/Users/thomasou/Documents/Codex/2026-11-02/lo')
OUT = Path(__file__).resolve().parent
ACTIVE = ROOT / 'work/three_hour/active_research/intel_market_share_thesis_2026_11_06/root/active_case.json'
ANCHOR = ROOT / 'work/three_hour/active_research/intel_two_hour_completion_2026_11_06/quarterly/favorable_anchor_case_results.json'
POLICY = OUT / 'analysis_policy.json'
m = json.loads(ACTIVE.read_text())
a = json.loads(ANCHOR.read_text())['cases']['joint_favorable']
q = [r for r in a['CPU_quarterly'] if r['year'] == 2027]
r = m['annual_rows']
q3 = 7.318 - 1.4
q4 = a['Q4_2026']['CPU_B']
fy26 = a['FY2026_revised_product_bases']['CPU_B']
fy27 = r['2027']['CPU_revenue_B']
assert abs(sum(v['CPU_revenue_B'] for v in q) - fy27) < 1e-9
units = sum(v['unit_index_Q4_2026_100'] for v in q)
weighted_asp = sum(v['unit_index_Q4_2026_100'] * v['ASP_index_Q4_2026_100'] for v in q) / units / 100
flat_asp_sales = q4 * units / 100
annual_unit_factor = 1.4 * .42 / .50
annual_asp_factor = fy27 / fy26 / annual_unit_factor
implied_q4_over_annual_asp = annual_asp_factor / weighted_asp
h1 = sum(v['CPU_revenue_B'] for v in q[:2])
h2 = sum(v['CPU_revenue_B'] for v in q[2:])
h1_units = sum(v['unit_index_Q4_2026_100'] for v in q[:2])
h2_units = sum(v['unit_index_Q4_2026_100'] for v in q[2:])
h1_asp = h1 / h1_units
h2_asp = h2 / h2_units
carry2028_units = 4 * q[-1]['unit_index_Q4_2026_100'] / units
carry2028_asp = q[-1]['ASP_index_Q4_2026_100'] / 100 / weighted_asp
lagged = [q[0]['CPU_revenue_B']] + [v['CPU_revenue_B'] for v in q[:-1]]
lagged_annual = {2027: sum(lagged)}
for year in range(2028, 2041):
    lagged_annual[year] = lagged_annual[year-1] * r[str(year)]['CPU_revenue_B'] / r[str(year-1)]['CPU_revenue_B']
results = {
 'computed_utc': datetime.now(timezone.utc).isoformat(),
 'input_sha256': {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [ACTIVE,ANCHOR,POLICY]},
 'actual': {'Q3_2026_CPU_residual_B':q3,'Q3_DCAI_B':7.318,'Q3_OtherDCAI_rounded_B':1.4,'YTD_CPU_residual_B':18.632-3.3,'rounding_note':'CPU residuals inherit rounded Other DCAI disclosures; not separately reported CPU totals'},
 'owned_Q4': {'CPU_B':q4,'DCAI_B':a['Q4_2026']['DCAI_B'],'OtherDCAI_B':a['Q4_2026']['Other_DCAI_B'],'consolidated_B':a['Q4_2026']['consolidated_B'],'DCAI_QoQ':.17,'OtherDCAI_QoQ':.25,'CPU_QoQ':q4/q3-1,'status':'Owned allocation at favorable edge of qualitative guidance, not a CPU guide'},
 'runrate_bridge':{'FY2026E_CPU_B':fy26,'annualized_actual_Q3_B':4*q3,'annualized_owned_Q4_B':4*q4,'FY2027_CPU_B':fy27,'FY2027_growth':fy27/fy26-1,'owned_exit_runrate_vs_FY2026E':4*q4/fy26-1,'FY2027_above_owned_exit_runrate':fy27/(4*q4)-1,'FY2027_above_actual_Q3_runrate':fy27/(4*q3)-1,'carryover_addition_B':4*q4-fy26,'incremental_2027_ramp_B':fy27-4*q4,'carryover_fraction_of_revenue_growth':(4*q4-fy26)/(fy27-fy26)},
 'quarterly_2027':q,
 'H2_requirements': {'H1_revenue_B':h1,'H2_revenue_B':h2,'H2_revenue_over_H1':h2/h1-1,'H2_units_over_H1':h2_units/h1_units-1,'H2_weighted_ASP_over_H1':h2_asp/h1_asp-1},
 'ASP_carryover_conditional':{'annual_ASP_required_under_17_6_unit_growth':annual_asp_factor-1,'2027_weighted_ASP_above_Q4_2026':weighted_asp-1,'implied_Q4_2026_ASP_above_FY2026_average':implied_q4_over_annual_asp-1,'flat_Q4_ASP_2027_revenue_B':flat_asp_sales,'2027_in_year_ASP_ramp_revenue_B':fy27-flat_asp_sales,'flat_Q4_ASP_2027_annual_ASP_growth_conditional':implied_q4_over_annual_asp-1,'limit':'Multiplicative reconciliation under the independent 17.6% annual unit assumption and current quarterly indices. The implied exit ASP premium is not identified by filed YoY unit/ASP figures; cannot claim it is already secured.'},
 'FY2028_carryover':{'annual_unit_growth_if_all_quarters_at_Q4_2027_units':carry2028_units-1,'required_2028_average_units_above_Q4_2027':1.25/carry2028_units-1,'annual_ASP_growth_if_all_quarters_at_Q4_2027_ASP':carry2028_asp-1,'required_2028_average_ASP_above_Q4_2027':1.08/carry2028_asp-1,'limit':'Conditional on delivery of the forecast Q4 2027 exit. Does not verify 2028 demand or capacity.'},
 'H1_miss_hurdles':[{'H1_miss':miss,'H1_revenue_B':h1*(1-miss),'required_H2_revenue_B':fy27-h1*(1-miss),'required_H2_over_H1':(fy27-h1*(1-miss))/(h1*(1-miss))-1,'required_H2_above_original_H2':(fy27-h1*(1-miss))/h2-1} for miss in [0,.05,.10]],
 'delay_no_catchup':{'quarterly_2027_B':lagged,'annual_CPU_B':lagged_annual,'2027_sales_loss_B':fy27-sum(lagged),'persistent_level_loss':1-sum(lagged)/fy27,'hold_constant':'Existing annual CPU growth rates, other revenues, margin rules and capital policy: fixed physical capex 2027-30; existing host 0.8 sales/capital rule after 2030. Valuation engine handles profit and cash propagation.'},
 'reported_yoy': [ {'period':'Q1 2026','server_unit_growth':-.05,'ASP_growth':.27}, {'period':'Q2 2026','server_unit_growth':.09,'ASP_growth':.48}, {'period':'Q3 2026','server_unit_growth':.10,'ASP_growth':.54}, {'period':'YTD Q3 2026','server_unit_growth':.04,'ASP_growth':.44}],
}
assert abs((1+results['H2_requirements']['H2_units_over_H1'])*(1+results['H2_requirements']['H2_weighted_ASP_over_H1'])-h2/h1) < 1e-12
assert abs(implied_q4_over_annual_asp*weighted_asp-annual_asp_factor)<1e-12
(OUT/'cpu_ramp_results.json').write_text(json.dumps(results,indent=2)+'\n')
print(json.dumps({k:results[k] for k in ['runrate_bridge','H2_requirements','ASP_carryover_conditional','FY2028_carryover','H1_miss_hurdles','delay_no_catchup']},indent=2))

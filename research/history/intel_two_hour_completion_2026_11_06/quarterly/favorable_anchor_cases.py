import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

OUT = Path(__file__).resolve().parent
p = OUT / 'favorable_anchor_policy_before_calculation.json'
policy = json.loads(p.read_text())
s = json.loads((OUT / 'selected_quarterly_forecast.json').read_text())
base_q4 = {'CCPG_B':6.07275,'DCAI_B':8.4157,'CPU_B':6.5257,'client_B':4.87575,'Other_DCAI_B':1.89,'Other_CCPG_B':1.197,'consolidated_B':15.41695}
other_growth = [.60,.30,.20,.15]
base_other = []
other = 5.19
for g in other_growth:
    other *= 1+g
    base_other.append(other)
cases = {}
for name,rates in policy['cases'].items():
    ccpg = 8.097*(1+rates['CCPG_QoQ'])
    dcai = 7.318*(1+rates['DCAI_QoQ'])
    other_q4 = 1.4*(1+rates['Other_DCAI_QoQ'])
    cpu_anchor = dcai-other_q4
    client_anchor = ccpg-1.197
    consolidated = ccpg+dcai+.695+.2335
    delta = consolidated-base_q4['consolidated_B']
    ebit_delta = delta*.5
    tax_delta = ebit_delta*.15
    wc_delta = delta*.1
    cfo_delta = ebit_delta-tax_delta-wc_delta
    assert abs(delta-((cpu_anchor-base_q4['CPU_B'])+(client_anchor-base_q4['client_B'])+(other_q4-base_q4['Other_DCAI_B'])))<1e-10
    cpu_q = [dict(r, CPU_revenue_B=r['CPU_revenue_B']*cpu_anchor/6.5257) for r in s['CPU_quarterly']]
    client_q = [dict(r, client_revenue_B=r['client_revenue_B']*client_anchor/4.87575, CCPG_revenue_B=r['client_revenue_B']*client_anchor/4.87575+r['Other_CCPG_B']) for r in s['client_quarterly']]
    annual = []
    other = 3.3+other_q4
    for i,row in enumerate(s['annual_rows']):
        year = row['year']
        cpu = sum(q['CPU_revenue_B'] for q in cpu_q if q['year']==year)
        client = sum(q['client_revenue_B'] for q in client_q if q['year']==year)
        other *= 1+other_growth[i]
        dcai_annual = cpu+other
        ccpg_annual = client+row['Other_CCPG_B']
        annual.append({'year':year,'CPU_revenue_B':cpu,'client_revenue_B':client,'Other_DCAI_B':other,'Other_CCPG_B':row['Other_CCPG_B'],'DCAI_revenue_B':dcai_annual,'CCPG_revenue_B':ccpg_annual,'Products_revenue_B':dcai_annual+ccpg_annual,'CPU_delta_vs_selected_B':cpu-row['CPU_revenue_B'],'client_delta_vs_selected_B':client-row['client_revenue_B'],'Other_DCAI_delta_vs_selected_B':other-base_other[i],'consolidated_sales_delta_vs_selected_B':cpu-row['CPU_revenue_B']+client-row['client_revenue_B']+other-base_other[i]})
    cases[name] = {'Q4_2026':{'CCPG_B':ccpg,'DCAI_B':dcai,'CPU_B':cpu_anchor,'client_B':client_anchor,'Other_DCAI_B':other_q4,'Other_CCPG_B':1.197,'consolidated_B':consolidated,'inside_total_revenue_guidance':15<=consolidated<=16,'net_consolidated_revenue_delta_B':delta,'group_EBIT_delta_B':ebit_delta,'cash_tax_delta_B':tax_delta,'WC_cash_use_delta_B':wc_delta,'CFO_delta_B':cfo_delta,'opening2027_economic_cash_delta_B':cfo_delta},'FY2026_revised_product_bases':{'CPU_B':15.332+cpu_anchor,'client_B':21.3+client_anchor,'Other_DCAI_B':3.3+other_q4},'CPU_quarterly':cpu_q,'client_quarterly':client_q,'annual_rows':annual,'calibration_boundary':'Unchanged normalizedquarterindices, revisedQ4dollaranchors. Historicalunit/ASPdecompositionnotnewlyidentified.'}
result = {'computed_utc':datetime.now(timezone.utc).isoformat(),'policy_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'selected_input_sha256':hashlib.sha256((OUT/'selected_quarterly_forecast.json').read_bytes()).hexdigest(),'base_Q4_2026':base_q4,'cases':cases,'root_interface':{'annual_override_fields':['CPU_revenue_B','client_revenue_B','Other_DCAI_B'],'opening_cash_override':'Add case.Q4_2026.opening2027_economic_cash_delta_B to existing opening2027economiccash; no debt delta. Use the revised openingcash for2026valuation and2030treasury.','working_capital_initial_condition':'For2027 initialize prior-year revenue delta to case.Q4_2026.net_consolidated_revenue_delta_B, because YTD2026 is unchanged. Then incremental2027WC is10%*(2027revenue delta minus2026revenue delta). Q4WC is already reflected in openingcash; do not charge it again.','scope':'No target output; future group profit/margin/capex follows root selectedpolicies. ApplyWCchangeonce; do notaddQ4cashdeltatwice.'},'assessment':'Neitherselectedloweranchorsnorfavorableonesareindependentlyproven. AllfivefavorablecasesremainwithintotalQ4revenueguide. Publicevidencesupportstiminganddirectionbutnotuniquepoints.'}
(OUT/'favorable_anchor_case_results.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({name:{'Q4':case['Q4_2026'],'2027':case['annual_rows'][0]} for name,case in cases.items()},indent=2))

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

OUT = Path(__file__).resolve().parent
p = OUT / 'anchor_sensitivity_policy_before_calculation.json'
policy = json.loads(p.read_text())
selected = json.loads((OUT / 'selected_quarterly_forecast.json').read_text())
old = json.loads((OUT.parents[1] / 'pricing_and_competition_review_2026_11_04/intel_server_ASP_mix_operating_policy.json').read_text())
cpu = []
for dcai_g in policy['CPU']['Q4_DCAI_QoQ']:
    for other_g in policy['CPU']['Q4_Other_DCAI_QoQ']:
        q4_dcai = policy['CPU']['Q3_DCAI_B'] * (1 + dcai_g)
        q4_other = policy['CPU']['Q3_Other_DCAI_B'] * (1 + other_g)
        anchor = q4_dcai - q4_other
        multiplier = anchor / selected['anchors']['CPU_Q42026_revenue_B']
        annual = [{'year': r['year'], 'CPU_revenue_B': r['CPU_revenue_B'] * multiplier, 'delta_vs_selected_CPU_B': r['CPU_revenue_B'] * (multiplier - 1)} for r in selected['annual_rows']]
        cpu.append({'Q4_DCAI_growth': dcai_g, 'Q4_Other_DCAI_growth': other_g, 'Q4_DCAI_B': q4_dcai, 'Q4_Other_DCAI_B': q4_other, 'Q4_CPU_B': anchor, 'Q4_CPU_delta_vs_selected_B': anchor - selected['anchors']['CPU_Q42026_revenue_B'], 'annual': annual})
client = []
for ccpg_g in policy['client']['Q4_CCPG_QoQ']:
    q4_ccpg = policy['client']['Q3_CCPG_B'] * (1 + ccpg_g)
    anchor = q4_ccpg - policy['client']['Q4_Other_CCPG_B']
    multiplier = anchor / selected['anchors']['client_Q42026_revenue_B']
    annual = [{'year': r['year'], 'client_revenue_B': r['client_revenue_B'] * multiplier, 'CCPG_revenue_B': r['client_revenue_B'] * multiplier + r['Other_CCPG_B'], 'delta_vs_selected_client_B': r['client_revenue_B'] * (multiplier - 1)} for r in selected['annual_rows']]
    client.append({'Q4_CCPG_growth': ccpg_g, 'Q4_CCPG_B': q4_ccpg, 'Q4_client_B': anchor, 'Q4_client_delta_vs_selected_B': anchor - selected['anchors']['client_Q42026_revenue_B'], 'annual': annual})
old2027 = next(r for r in old['annual_rows'] if r['year'] == 2027)
new2027 = selected['annual_rows'][0]
needed_cpu_anchor = old2027['server_CPU_revenue_proxy_B'] / new2027['CPU_revenue_B'] * selected['anchors']['CPU_Q42026_revenue_B']
needed_client_anchor = old2027['client_revenue_B'] / new2027['client_revenue_B'] * selected['anchors']['client_Q42026_revenue_B']
result = {'computed_utc':datetime.now(timezone.utc).isoformat(),'policy_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'CPU_anchor_cases':cpu,'client_anchor_cases':client,'old_target_recovery_via_anchor_only':{'CPU_Q4_anchor_B':needed_cpu_anchor,'implied_Q4_DCAI_growth_holdingOther1_89':(needed_cpu_anchor+1.89)/7.318-1,'implied_Q4_Other_DCAI_growth_holdingDCAI15percent':(7.318*1.15-needed_cpu_anchor)/1.4-1,'client_Q4_anchor_B':needed_client_anchor,'implied_Q4_CCPG_decline_holdingOther1_197':(needed_client_anchor+1.197)/8.097-1,'boundary':'Reverse hurdle, not a newly selected forecast. A less severeQ4clientreset cannearlyrestoreold2027target evenwithselectedrecoveryrates.'},'valuation_boundary':policy['valuation_boundary']}
(OUT / 'anchor_sensitivity_results.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({'CPU2027_ranges_B':[min(c['annual'][0]['CPU_revenue_B'] for c in cpu),max(c['annual'][0]['CPU_revenue_B'] for c in cpu)],'client2027_cases': [{'Q4_CCPG_growth':c['Q4_CCPG_growth'],'CCPG2027_B':c['annual'][0]['CCPG_revenue_B']} for c in client], 'old_target_recovery_via_anchor_only':result['old_target_recovery_via_anchor_only']},indent=2))

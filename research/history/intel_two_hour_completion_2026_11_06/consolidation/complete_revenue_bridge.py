from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import math

ROOT = Path(__file__).resolve().parents[5]
BASE = ROOT / 'work/three_hour/active_research'
OUT = Path(__file__).resolve().parent
POLICY = json.loads((OUT / 'consolidation_policy_before_calculation.json').read_text())
INPUTS = {
    'host': BASE / 'pricing_and_competition_review_2026_11_04/intel_server_ASP_mix_operating_policy.json',
    'model': BASE / 'pricing_and_competition_review_2026_11_04/intel_ASP20_mature_margin35_valuation.json',
    'packaging': BASE / 'intel_competition_screen_2026_11_04/external_packaging_operating_policy_2026_11_04.json',
    'prior_audit': BASE / 'intel_edge_resolution_2026_11_06/delivery/consensus_residual_independent_audit.json',
}
HASHES = {k: hashlib.sha256(p.read_bytes()).hexdigest() for k,p in INPUTS.items()}
D = {k: json.loads(p.read_text()) for k,p in INPUTS.items()}
HOST = {r['year']: r for r in D['host']['annual_rows']}
MODEL = {r['year']: r for r in D['model']['annual_operating_rows']}
PACK = {r['year']: r for r in D['packaging']['annual_rows']}


def revenue_rows(legacy_annual: float = .934, internal_other_annual: float = .02) -> list[dict]:
    history = [
        {'year':2026,'quarter':1,'Products_external_B':12.779,'Foundry_total_B':5.421,'Foundry_external_B':.174,'AllOther_segment_B':.628,'total_revenue_eliminations_B':5.251,'consolidated_B':13.577},
        {'year':2026,'quarter':2,'Products_external_B':15.139,'Foundry_total_B':5.765,'Foundry_external_B':.293,'AllOther_segment_B':.701,'total_revenue_eliminations_B':5.477,'consolidated_B':16.128},
        {'year':2026,'quarter':3,'Products_external_B':15.415,'Foundry_total_B':6.697,'Foundry_external_B':.411,'AllOther_segment_B':.692,'total_revenue_eliminations_B':6.291,'consolidated_B':16.513},
    ]
    for r in history:
        r['Foundry_internal_B'] = r['Foundry_total_B']-r['Foundry_external_B']
        r['AllOther_internal_B'] = r['total_revenue_eliminations_B']-r['Foundry_internal_B']
        r['AllOther_external_B'] = r['AllOther_segment_B']-r['AllOther_internal_B']
        r['identity_error_B'] = r['Products_external_B']+r['Foundry_external_B']+r['AllOther_external_B']-r['consolidated_B']
        assert abs(r['identity_error_B'])<1e-12
    q4 = dict(POLICY['base_policy']['2026Q4'])
    q4.update(year=2026,quarter=4,classification='Analyst forecast, not reported result or management segment guide')
    q4['AllOther_external_B'] = q4['AllOther_segment_B']-q4['AllOther_internal_B']
    q4['Foundry_external_B'] = q4['legacy_external_Foundry_B']+q4['gross_new_packaging_B']
    q4['consolidated_B'] = q4['Products_external_B']+q4['AllOther_external_B']+q4['Foundry_external_B']
    q4['difference_from_Q4_guidance_midpoint_B'] = q4['consolidated_B']-15.5
    annual2026 = {'year':2026,'classification':'2026E:9Mreported plus ownedQ4estimate'}
    for field in ['Products_external_B','Foundry_external_B','AllOther_segment_B','AllOther_internal_B','AllOther_external_B','consolidated_B']:
        annual2026[field] = math.fsum(r[field] for r in history)+q4[field]
    annual2026['legacy_external_Foundry_B'] = annual2026['Foundry_external_B']
    annual2026['gross_new_packaging_B'] = 0.
    annual2026['identity_error_B'] = annual2026['Products_external_B']+annual2026['AllOther_external_B']+annual2026['Foundry_external_B']-annual2026['consolidated_B']
    assert abs(annual2026['identity_error_B'])<1e-12
    rows=[annual2026]
    for y in range(2027,2042):
        h,p,m=HOST[y],PACK[y],MODEL[y]
        grow = 1.03**max(0,y-2030)
        legacy=legacy_annual*grow
        other_gross=h['root_Other_revenue_for_capital_denominator_B']
        other_internal=internal_other_annual*grow
        other_net=other_gross-other_internal
        gross=p['gross_external_packaging_revenue_B']
        shadow=p['existing_embedded_packaging_revenue_allowance_B']
        net=p['incremental_external_packaging_revenue_B']
        host_external=h['Products_revenue_B']+other_net+legacy+shadow
        total=host_external+net
        missing=shadow+legacy-other_internal
        row={'year':y,'classification':'Owned analyst forecast',
             'Products_external_B':h['Products_revenue_B'],'AllOther_segment_B':other_gross,
             'AllOther_internal_B':other_internal,'AllOther_external_B':other_net,
             'legacy_external_Foundry_B':legacy,'gross_new_packaging_B':gross,
             'shadow_packaging_B':shadow,'net_incremental_packaging_B':net,
             'total_external_Foundry_B':legacy+gross,
             'host_consolidated_external_revenue_B':host_external,
             'consolidated_B':total,'previous_capital_revenue_proxy_B':m['external_revenue_B'],
             'missing_from_previous_proxy_B':missing,
             'reconciliation_identity_error_B':total-(h['Products_revenue_B']+other_net+legacy+gross),
             'previous_proxy_reconciliation_error_B':total-m['external_revenue_B']-missing,
             'double_counting_check_gross_minus_shadow_equals_net_B':gross-shadow-net,
             'new_revenue_level_does_not_add_EBIT_B':0.0,
             'retained_host_Foundry_operating_profit_B':h['Foundry_operating_profit_B'],
             'incremental_packaging_EBIT_B':p['net_incremental_operating_profit_B']}
        assert abs(row['reconciliation_identity_error_B'])<1e-10
        assert abs(row['previous_proxy_reconciliation_error_B'])<1e-10
        assert abs(row['double_counting_check_gross_minus_shadow_equals_net_B'])<1e-10
        if y>2030:
            prev=rows[-1]
            missing_delta=missing-prev['missing_from_previous_proxy_B']
            wc_delta=.1*missing_delta
            investment_delta=missing_delta/.8
            capex_delta=investment_delta-wc_delta
        else:
            missing_delta=wc_delta=investment_delta=capex_delta=0.
        row.update({'omitted_host_sales_growth_B':missing_delta,
                    'additional_host_WC_cash_use_B':wc_delta,
                    'additional_host_physical_cash_capex_B':capex_delta,
                    'additional_host_net_investment_B':investment_delta,
                    'DA_correction_B':0.,'cash_correction_before_tax_financing_B':-investment_delta,
                    'corrected_physical_cash_capex_B':m['physical_cash_capex_B']+capex_delta,
                    'corrected_WC_cash_use_B':m['WC_cash_use_B']+wc_delta,
                    'capital_allocation_identity_error_B':capex_delta+wc_delta-investment_delta})
        assert abs(row['capital_allocation_identity_error_B'])<1e-12
        if y==2027:
            row['S_and_P_2027_revenue_proxy_B']=69.27
            row['owned_forecast_minus_consensus_proxy_B']=total-69.27
            row['owned_forecast_above_consensus_proxy_pct']=total/69.27-1
        rows.append(row)
    return history,q4,rows


def reinvestment_PV(rows: list[dict], endpoint: int) -> dict:
    rate=.11555
    cash={r['year']:r.get('cash_correction_before_tax_financing_B',0.) for r in rows}
    explicit=math.fsum(cash[y]/(1+rate)**(y-endpoint) for y in range(endpoint+1,2041))
    terminal=cash[2041]/(rate-.03)/(1+rate)**(2040-endpoint)
    if endpoint==2030:
        assert abs(cash[2041]/cash[2040]-1.03)<1e-10
    return {'endpoint':endpoint,'discount_rate':rate,'shares_B':5.51,
            'explicit_operating_PV_delta_B':explicit,'terminal_operating_PV_delta_B':terminal,
            'operating_PV_delta_B':explicit+terminal,'per_share_delta_USD':(explicit+terminal)/5.51,
            'scope':'Reinvestment-only delta at unchanged EBIT, taxes, financing, claims and finite2027–30budgets. Not a new full value or standalone recurring revenue valuation.'}

history,q4,rows=revenue_rows()
controls=[]
for name,legacy,internal in [('selected',.934,.02),('Q1runrate',.696,.02),('Q2runrate',1.172,.02),('no_Other_internal',.934,0.),('one_percent_Other_internal',.934,.028)]:
    _,_,rr=revenue_rows(legacy,internal)
    controls.append({'name':name,'legacy2027_to2030_B':legacy,'Other_internal2027_to2030_B':internal,
                     'consolidated2027_B':rr[1]['consolidated_B'],
                     'reinvestment_PV':[reinvestment_PV(rr,e) for e in (2026,2030)]})
assert all(hashlib.sha256(p.read_bytes()).hexdigest()==HASHES[k] for k,p in INPUTS.items())
output={'computed_utc':datetime.now(timezone.utc).isoformat(),'policy_file':str(OUT/'consolidation_policy_before_calculation.json'),
 'source_input_hashes':HASHES,'source_models_unchanged':True,'historical_quarters':history,'Q4_2026_forecast':q4,'annual_rows':rows,
 'reinvestment_value_deltas':[reinvestment_PV(rows,e) for e in (2026,2030)],'source_anchored_controls_not_bounds':controls,
 'integration_rules':['Replace revenue labels with true consolidated series; do not add any EBIT for existingexternalFoundry asecondtime.',
  'For2031onward replacehostcapitaldenominator Products+grossOther with Products+netOther+legacyexternalFoundry+shadowpackaging; separately fund netincrementalpackaging under its existing1.0rule.',
  '2027–30capitalbudgets are already aggregate envelopes; do not back-charge existingassets simply because revenue rows become explicit.',
  'The reinvestment correction assumes normalizedD&A covers existingmaintenance. It does not independently establish physicalassetreplacement sufficiency.',
  'New quarterly Products forecasts can be substituted into the algebra without altering selected legacy/Other series. Do not double charge Products growth adjustments already modeledbyroot.',
  'Mobileye R&Dgrant cash timing is separate and not included here; pending primary-source diagnostic.'],
 'completion_status':'Revenue accounting series complete; factual rows distinguished from forecasts; no claimfuturecontractsorcapacityverified.'}
(OUT/'completed_revenue_bridge.json').write_text(json.dumps(output,indent=2)+'\n')
print(json.dumps({'selected_2026':rows[0],'selected_2027':rows[1],'selected_2030':rows[4],'selected_2031':rows[5],
 'deltas':output['reinvestment_value_deltas'],'all_checks':'pass'},indent=2))

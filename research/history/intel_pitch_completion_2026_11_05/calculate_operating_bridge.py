from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import math

ROOT = Path(__file__).resolve().parents[4]
BASE = ROOT / 'work/three_hour/active_research'
OUT = Path(__file__).resolve().parent
FILES = {
    'model': BASE / 'pricing_and_competition_review_2026_11_04/intel_ASP20_mature_margin35_valuation.json',
    'host': BASE / 'pricing_and_competition_review_2026_11_04/intel_server_ASP_mix_operating_policy.json',
    'rates': BASE / 'intel_hour_verification_2026_11_04/corrected_rate_valuation.json',
    'joint': BASE / 'intel_decision_pass_2026_11_04/joint_scenario_results.json',
}
hashes = {k: hashlib.sha256(p.read_bytes()).hexdigest() for k, p in FILES.items()}
assert hashes['model'] == 'f040f1f39a5daee1bbc9143129622440460e09bdcd2f9b83c4a374e13771e052'
d = {k: json.loads(p.read_text()) for k,p in FILES.items()}
base_rows = {r['year']:r for r in d['model']['annual_operating_rows']}
host_rows = {r['year']:r for r in d['host']['annual_rows']}
funding = {r['year']:r for r in d['model']['treasury_rows']}
benefits = {r['year']:r['financing_tax_benefit_B'] for r in d['model']['financing_tax_benefit_rows']}
claims = d['model']['values_at12pct']['2026']['planning_claims_B']
other_assets = d['model']['values_at12pct']['2026']['net_other_assets_B']
quote = d['rates']['reference_price_USD']
g = .03


def operating_rows(margin: float, productivity: float) -> list[dict]:
    result = []
    for y, old in base_rows.items():
        margin_weight = max(0., min((y-2030)/10, 1.))
        capital_weight = max(0., min((y-2030)/5, 1.))
        ebit_delta = host_rows[y]['DCAI_revenue_B'] * (margin-.35) * margin_weight
        turn = .8 if capital_weight == 0 else .8 + (productivity-.8)*capital_weight
        sales_change = 0. if y <= 2030 else host_rows[y]['consolidated_external_revenue_for_capital_denominator_B'] - host_rows[y-1]['consolidated_external_revenue_for_capital_denominator_B']
        capex_delta = sales_change * (1/turn - 1/.8)
        ebit = old['EBIT_after_economic_SBC_B'] + ebit_delta
        tax = max(0.,ebit)*old['tax_rate']
        tax_delta = tax - old['ordinary_operating_tax_B']
        cash = old['parent_unlevered_cash_B'] + ebit_delta - tax_delta - capex_delta
        assert benefits[y] <= tax + 1e-10
        if y <= 2030:
            assert abs(cash-old['parent_unlevered_cash_B']) < 1e-10
        result.append({'year':y,'margin_delta_B':ebit_delta,'tax_delta_B':tax_delta,'host_sales_change_B':sales_change,'host_turnover':turn,'capex_delta_B':capex_delta,'cash_B':cash,'cash_delta_B':cash-old['parent_unlevered_cash_B']})
    assert abs(result[-1]['cash_B']/result[-2]['cash_B'] - 1.03)<1e-10
    return result


def value(margin: float, productivity: float, endpoint: int, risk: str) -> dict:
    assert endpoint in (2026,2029,2030)
    rows = operating_rows(margin,productivity)
    schedule = {int(y): r for y,r in d['rates']['rate_schedules'][risk].items()}
    def df(y: int) -> float:
        return math.prod(1+schedule[t] for t in range(endpoint+1,y+1))
    explicit = math.fsum(r['cash_B']/df(r['year']) for r in rows if endpoint<r['year']<=2040)
    terminal = rows[-1]['cash_B']/(schedule[2041]-g)/df(2040)
    shields = math.fsum(v/df(y) for y,v in benefits.items() if endpoint<y<=2040)+benefits[2041]/schedule[2041]/df(2040)
    cash = funding[2027]['opening_economic_cash_B'] if endpoint==2026 else funding[endpoint]['ending_economic_cash_B']
    debt = funding[2027]['opening_ordinary_debt_B'] if endpoint==2026 else funding[endpoint]['ending_ordinary_debt_B']
    escrow = math.fsum(r['escrow_cash_B']/df(y) for y,r in funding.items() if endpoint<y<=2030)
    mna = math.fsum(r['Classiq_cash_B']/df(y) for y,r in funding.items() if endpoint<y<=2030)
    equity = explicit+terminal+shields+cash-debt+other_assets+escrow-mna
    return {'price_USD':equity/claims,'explicit_operating_PV_B':explicit,'terminal_operating_PV_B':terminal,'financing_tax_benefit_PV_B':shields,'equity_B':equity}

risks = ['corrected_central_flat','corrected_maturing_risk']
checked = []
for scenario in d['rates']['scenarios']:
    for endpoint in (2026,2029,2030):
        for risk in risks:
            got=value(scenario['mature_DCAI_margin'],scenario['mature_host_incremental_sales_to_capital'],endpoint,risk)
            expected=scenario['values'][str(endpoint)][risk]
            for field in got:
                err=abs(got[field]-expected[field])
                assert err<1e-9,(scenario['name'],endpoint,risk,field,err)
                checked.append(err)

cases = [('central',.35,.8),('margin_only',.4,.8),('capital_only',.35,1.),('both',.4,1.)]
results = []
for endpoint in (2026,2029,2030):
 for risk in risks:
    case_values={name:value(m,p,endpoint,risk) for name,m,p in cases}
    prices={name:r['price_USD'] for name,r in case_values.items()}
    margin_delta=prices['margin_only']-prices['central']
    capital_delta=prices['capital_only']-prices['central']
    joint_delta=prices['both']-prices['central']
    assert abs(margin_delta+capital_delta-joint_delta)<1e-10
    results.append({'endpoint':endpoint,'risk':risk,'cases':case_values,'margin_delta_USD':margin_delta,'capital_delta_USD':capital_delta,'joint_delta_USD':joint_delta,'margin_share_of_joint_delta':margin_delta/joint_delta,'additivity_error_USD':margin_delta+capital_delta-joint_delta})

thresholds=[]
grid=[]
for risk in risks:
    base=value(.35,.8,2026,risk)['price_USD']
    per_pp=(value(.36,.8,2026,risk)['price_USD']-base)
    implied_margin=.35+(quote-base)/per_pp*.01
    assert abs(value(implied_margin,.8,2026,risk)['price_USD']-quote)<1e-9
    low,high=.8,10000.
    if value(.35,high,2026,risk)['price_USD']<quote:
        implied_capital=None
    else:
        for _ in range(100):
            mid=(low+high)/2
            if value(.35,mid,2026,risk)['price_USD']<quote:low=mid
            else:high=mid
        implied_capital=(low+high)/2
    thresholds.append({'risk':risk,'target_quote_USD':quote,'price_at35pct_and080':base,'value_per_mature_margin_percentage_point_USD':per_pp,'margin_at080_matching_quote':implied_margin,'margin_threshold_within_existing30_40_range':.3<=implied_margin<=.4,'capital_productivity_at35pct_matching_quote':implied_capital,'capital_threshold_within_existing060_100_range':implied_capital is not None and .6<=implied_capital<=1.,'price_at35pct_capital10000_limit_check':value(.35,10000.,2026,risk)['price_USD'],'price_at35pct_zero_post2030_host_net_investment_limit':value(.35,float('inf'),2026,risk)['price_USD']})
    for margin in (.30,.35,.375,.40):
      for capital in (.6,.8,1.):
        grid.append({'risk':risk,'mature_DCAI_margin':margin,'mature_host_capital_productivity':capital,**value(margin,capital,2026,risk)})

out={'as_of_utc':datetime.now(timezone.utc).isoformat(),'scope':'Decomposition and conditional reverse diagnostics within the existing model; no new operating forecast or model mutation.','sources':{k:{'path':str(FILES[k]),'sha256':v} for k,v in hashes.items()},'reference_price_USD':quote,'date_scope':'Values at December31,2026 conditional planning date versus November4,2026close58.28;57day mismatch remains. This is not an exact current-date market-implied forecast or a holding-period return.','method':{'margin':'Change the mature35% DCAI endpoint only; incremental target margin phases linearly2031–2040 on unchanged DCAI sales; charge current operating tax; no duplicate Foundry benefit.','capital':'Change host incremental sales/net operating investment only; phases from.8in2030 to targetin2035. For eachyear capitaldelta=changeinhostsales*(1/newturnover−1/.8); no change to separatepackaging,WC,DA,earlierinvestment,revenues,leases,NCI,credits orfinancing.','risk':'Each comparison holds the selected existing annual risk schedule fixed. Maturing risk is11.555% through2030 then−0.15percentagepoint/year to10.055% in2040,holding thereafter.','APV':'Reconstructed fullcashPV and shieldPV using cumulative annualdiscountproducts. Operating terminalg3%; financingbenefittailg0;5.51Bclaims.','threshold':'One unknown at a time, all other assumptions held fixed. Multiple combinations can matchthequote; no unique marketexpectations identified.'},'decomposition':results,'reverse_thresholds':thresholds,'value_grid':grid,'verification':{'comparisons_to_existing_corrected_values':len(checked),'max_absolute_error':max(checked),'all2027_2030_cash_unchanged':True,'all_terminal_growth_checks_passed':True,'margin_plus_capital_delta_equals_joint_delta':True,'financing_tax_capacity_checks_passed':True,'all_source_hashes_unchanged':all(hashlib.sha256(p.read_bytes()).hexdigest()==hashes[k] for k,p in FILES.items())},'limitations':['The parameters are economic scenarios, not statisticallyestimatedcoefficients. Current productmargins can exceed the long-runbreak-even endpoint withoutestablishingthat they persist.','Capitaldenominator is the frozenhost convention,notfullyreconciledGAAPsales;no directclaimedmappingfromreportedquarterlyrevenue/capexto.8or1.0.','NormalizedD&A unchangedwhilecapitalchanges is anaggregateeconomicconvention,notreconstructedassetcohorts ortaxdepreciation.','Changes occurafter2030:they explain sensitivitytocontinuationcash,not a near-termcatalyst orforecastof2027earningsmiss.','No probabilityweights,winningscore,marginofcertainty,orautomaticriskreductionattachedtobetteroperations.']}
(OUT/'operating_value_bridge.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps({'decomposition':results,'thresholds':thresholds,'verification':out['verification']},indent=2))

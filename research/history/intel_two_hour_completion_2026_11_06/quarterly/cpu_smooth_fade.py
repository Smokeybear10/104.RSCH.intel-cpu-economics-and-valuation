import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

OUT = Path(__file__).resolve().parent
p = OUT / 'cpu_smooth_fade_policy_before_calculation.json'
policy = json.loads(p.read_text())
old = json.loads((OUT / 'quarterly_delivery_results.json').read_text())
quarters = [dict(r) for r in old['cases']['preferred']['quarterly_2027']]
annual = [dict(old['cases']['preferred']['annual_2027_2030'][0])]
scale = quarters[0]['CPU_revenue_B'] / quarters[0]['unit_index_Q4_2026_100'] / quarters[0]['ASP_index_Q4_2026_100']
for year in range(2028, 2031):
    previous = [r for r in quarters if r['year'] == year - 1]
    prior_units = sum(r['unit_index_Q4_2026_100'] for r in previous)
    prior_revenue = sum(r['CPU_revenue_B'] for r in previous)
    prior_asp = prior_revenue / scale / prior_units
    rates = policy['annual_sequential_rates'][str(year)]
    units = previous[-1]['unit_index_Q4_2026_100']
    asp = previous[-1]['ASP_index_Q4_2026_100']
    new = []
    for q in range(1, 5):
        units *= 1 + rates['units']
        asp *= 1 + rates['ASP']
        new.append({'year': year, 'quarter': q, 'unit_growth_QoQ': rates['units'], 'ASP_growth_QoQ': rates['ASP'], 'unit_index_Q4_2026_100': units, 'ASP_index_Q4_2026_100': asp, 'CPU_revenue_B': scale * units * asp})
    quarters.extend(new)
    current_units = sum(r['unit_index_Q4_2026_100'] for r in new)
    revenue = sum(r['CPU_revenue_B'] for r in new)
    current_asp = revenue / scale / current_units
    control = next(r for r in old['cases']['preferred']['annual_2027_2030'] if r['year'] == year)
    annual.append({'year': year, 'CPU_revenue_B': revenue, 'unit_growth': current_units / prior_units - 1, 'ASP_growth': current_asp / prior_asp - 1, 'delta_vs_annual_preferred_B': revenue - control['CPU_revenue_B']})
result = {'computed_utc': datetime.now(timezone.utc).isoformat(), 'policy_sha256': hashlib.sha256(p.read_bytes()).hexdigest(), 'quarterly': quarters, 'annual_2027_2030': annual, 'boundary': 'Sequential sensitivity selected fromoperatinglogic. Noequityvaluescalculated.'}
(OUT / 'cpu_smooth_fade_results.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(annual, indent=2))

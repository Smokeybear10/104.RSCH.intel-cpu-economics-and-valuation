import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

OUT = Path(__file__).resolve().parent
policy_path = OUT / 'quarterly_extension_policy_before_calculation.json'
policy = json.loads(policy_path.read_text())
cpu = json.loads((OUT / 'quarterly_delivery_results.json').read_text())
client = json.loads((OUT / 'client_quarterly_results.json').read_text())
old = json.loads((OUT.parents[1] / 'pricing_and_competition_review_2026_11_04/intel_server_ASP_mix_operating_policy.json').read_text())


def solve_increasing(function, target: float) -> float:
    lo, hi = -0.99, 5.
    assert function(lo) < target < function(hi)
    for _ in range(120):
        mid = (lo + hi) / 2
        if function(mid) < target:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def extend_cpu(name: str) -> dict:
    if name == 'old_target_favorable':
        quarters = cpu['old_target_with_preferred_H1']['favorable_target_hold_schedule']
        annual = [{'year': r['year'], 'CPU_revenue_B': r['server_CPU_revenue_proxy_B'], 'unit_growth': r['server_unit_growth'], 'ASP_growth': r['server_ASP_growth']} for r in old['annual_rows']]
    else:
        quarters = cpu['cases'][name]['quarterly_2027']
        annual = cpu['cases'][name]['annual_2027_2030']
    quarters = [dict(row) for row in quarters]
    reconciliation = []
    scale = quarters[0]['CPU_revenue_B'] / quarters[0]['unit_index_Q4_2026_100'] / quarters[0]['ASP_index_Q4_2026_100']
    for year in range(2028, 2031):
        target = next(r for r in annual if r['year'] == year)
        previous = [r for r in quarters if r['year'] == year - 1]
        previous_units = sum(r['unit_index_Q4_2026_100'] for r in previous)
        previous_revenue = sum(r['CPU_revenue_B'] for r in previous)
        previous_asp = previous_revenue / scale / previous_units
        target_units = previous_units * (1 + target['unit_growth'])
        target_asp = previous_asp * (1 + target['ASP_growth'])
        last = previous[-1]
        unit_rate = solve_increasing(lambda g: sum(last['unit_index_Q4_2026_100'] * (1 + g) ** q for q in range(1, 5)), target_units)
        units = [last['unit_index_Q4_2026_100'] * (1 + unit_rate) ** q for q in range(1, 5)]
        asp_rate = solve_increasing(lambda g: sum(u * last['ASP_index_Q4_2026_100'] * (1 + g) ** q for q, u in enumerate(units, 1)) / sum(units), target_asp)
        new = []
        for q, unit in enumerate(units, 1):
            asp = last['ASP_index_Q4_2026_100'] * (1 + asp_rate) ** q
            new.append({'year': year, 'quarter': q, 'unit_index_Q4_2026_100': unit, 'ASP_index_Q4_2026_100': asp, 'unit_growth_QoQ': unit_rate, 'ASP_growth_QoQ': asp_rate, 'CPU_revenue_B': scale * unit * asp, 'classification': 'Timing allocation reconciled to owned annual assumptions, not independently identified capacity'})
        quarters.extend(new)
        actual_rev = sum(r['CPU_revenue_B'] for r in new)
        assert abs(actual_rev - target['CPU_revenue_B']) < 1e-8
        assert abs(sum(units) / previous_units - 1 - target['unit_growth']) < 1e-10
        actual_asp = actual_rev / scale / sum(units)
        assert abs(actual_asp / previous_asp - 1 - target['ASP_growth']) < 1e-10
        reconciliation.append({'year': year, 'annual_CPU_B': actual_rev, 'annual_unit_growth': target['unit_growth'], 'annual_ASP_growth': target['ASP_growth'], 'implied_constant_QoQ_units': unit_rate, 'implied_constant_QoQ_ASP': asp_rate, 'flat_priorQ4_unit_carryover': 4 * last['unit_index_Q4_2026_100'] / previous_units - 1, 'flat_priorQ4_ASP_carryover': last['ASP_index_Q4_2026_100'] / previous_asp - 1})
    return {'quarterly': quarters, 'annual_reconciliation': reconciliation}


def extend_client(name: str) -> dict:
    if name == 'old_target_favorable':
        quarters = client['old_target_hurdle']['favorable_schedule_holding_old_annual_target']
        annual = [{'year': r['year'], 'client_revenue_B': r['client_revenue_B'], 'Other_CCPG_B': r['Other_CCPG_revenue_B'], 'client_unit_growth': r['client_unit_growth'], 'client_ASP_growth': r['client_ASP_growth']} for r in old['annual_rows']]
    else:
        quarters = client['cases'][name]['quarterly_2027']
        annual = client['cases'][name]['annual_2027_2030']
    quarters = [dict(row) for row in quarters]
    reconciliation = []
    scale = quarters[0]['client_revenue_B'] / quarters[0]['unit_index_Q4_2026_100'] / quarters[0]['ASP_index_Q4_2026_100']
    for year in range(2028, 2031):
        target = next(r for r in annual if r['year'] == year)
        previous = [r for r in quarters if r['year'] == year - 1]
        previous_units = sum(r['unit_index_Q4_2026_100'] for r in previous)
        previous_revenue = sum(r['client_revenue_B'] for r in previous)
        previous_asp = previous_revenue / scale / previous_units
        target_units = previous_units * (1 + target['client_unit_growth'])
        target_asp = previous_asp * (1 + target['client_ASP_growth'])
        last = previous[-1]
        units = [target_units * weight for weight in policy['client_2028_2030']['unit_weights']]
        asp_rate = solve_increasing(lambda g: sum(u * last['ASP_index_Q4_2026_100'] * (1 + g) ** q for q, u in enumerate(units, 1)) / sum(units), target_asp)
        new = []
        last_unit = last['unit_index_Q4_2026_100']
        for q, unit in enumerate(units, 1):
            asp = last['ASP_index_Q4_2026_100'] * (1 + asp_rate) ** q
            other = target['Other_CCPG_B'] * policy['client_2028_2030']['Other_CCPG_quarter_weights'][q - 1]
            revenue = scale * unit * asp
            new.append({'year': year, 'quarter': q, 'unit_index_Q4_2026_100': unit, 'ASP_index_Q4_2026_100': asp, 'unit_growth_QoQ': unit / last_unit - 1, 'ASP_growth_QoQ': asp_rate, 'client_revenue_B': revenue, 'Other_CCPG_B': other, 'CCPG_revenue_B': revenue + other, 'classification': 'Owned seasonal allocation, not measured OEM orders'})
            last_unit = unit
        quarters.extend(new)
        actual_rev = sum(r['client_revenue_B'] for r in new)
        assert abs(actual_rev - target['client_revenue_B']) < 1e-8
        assert abs(sum(units) / previous_units - 1 - target['client_unit_growth']) < 1e-10
        actual_asp = actual_rev / scale / sum(units)
        assert abs(actual_asp / previous_asp - 1 - target['client_ASP_growth']) < 1e-10
        reconciliation.append({'year': year, 'annual_client_B': actual_rev, 'annual_CCPG_B': actual_rev + target['Other_CCPG_B'], 'annual_unit_growth': target['client_unit_growth'], 'annual_ASP_growth': target['client_ASP_growth'], 'Q1_unit_reset_from_priorQ4': new[0]['unit_growth_QoQ'], 'flat_priorQ4_unit_carryover': 4 * last['unit_index_Q4_2026_100'] / previous_units - 1, 'flat_priorQ4_ASP_carryover': last['ASP_index_Q4_2026_100'] / previous_asp - 1, 'implied_constant_QoQ_ASP': asp_rate})
    return {'quarterly': quarters, 'annual_reconciliation': reconciliation}


cases = {name: {'CPU': extend_cpu(name), 'client': extend_client(name)} for name in ['preferred', 'slower', 'old_target_favorable']}
share = []
for name in cases:
    q = cases[name]['CPU']['quarterly']
    factor = sum(r['unit_index_Q4_2026_100'] for r in q if r['year'] == 2030) / sum(r['unit_index_Q4_2026_100'] for r in q if r['year'] == 2027)
    share.append({'case': name, 'CPU_unit_factor_2030_over2027': factor, 'market_CPU_unit_CAGR_required_for_flat_share': factor ** (1 / 3) - 1, 'conditional_share_indices_2027_100': [{'assumed_market_CAGR': rate, '2030_share_index': 100 * factor / (1 + rate) ** 3} for rate in policy['later_market_diagnostic']['assumed_industry_CPU_unit_CAGR_2028_2030']]})
result = {'computed_utc': datetime.now(timezone.utc).isoformat(), 'policy_sha256': hashlib.sha256(policy_path.read_bytes()).hexdigest(), 'cases': cases, 'market_share_diagnostics': share, 'boundary': '2027ownedpolicy;2028–30annualdriverreconciliationwithdeclaredtimingrules.Thequarterlymathdoesnotaddindependentforecastcertainty.'}
(OUT / 'quarterly_2027_2030_results.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps({'preferred': {business: cases['preferred'][business]['annual_reconciliation'] for business in ['CPU', 'client']}, 'share_diagnostic': share}, indent=2))

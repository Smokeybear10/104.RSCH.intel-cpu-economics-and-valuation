import copy
import hashlib
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path

OUT = Path(__file__).resolve().parent
engine_path = OUT.parent / 'root/integrated_model.py'
engine_hash = hashlib.sha256(engine_path.read_bytes()).hexdigest()
spec = importlib.util.spec_from_file_location('intel_root_engine', engine_path)
engine = importlib.util.module_from_spec(spec)
spec.loader.exec_module(engine)
policy_path = OUT / 'anchor_valuation_policy_before_calculation.json'
policy = json.loads(policy_path.read_text())
anchors_path = OUT / 'favorable_anchor_case_results.json'
anchors = json.loads(anchors_path.read_text())['cases']
controls = {}
old_annual = []
other = 5.19
for year, growth in zip(range(2027, 2031), [.6, .3, .2, .15]):
    old = engine.HOST[year]
    other *= 1 + growth
    old_annual.append({'year': year, 'CPU_revenue_B': old['server_CPU_revenue_proxy_B'], 'client_revenue_B': old['client_revenue_B'], 'Other_DCAI_B': other})
controls['exact_old_delivery_pooled_old_growth'] = {'annual_rows': old_annual, 'Q4_2026': {'net_consolidated_revenue_delta_B': 0., 'opening2027_economic_cash_delta_B': 0.}}
control = copy.deepcopy(anchors['joint_favorable'])
prior_cpu = control['annual_rows'][0]['CPU_revenue_B']
for row, ug, ag in zip(control['annual_rows'][1:], [.25, .18, .12], [.08, .04, .02]):
    prior_cpu *= (1 + ug) * (1 + ag)
    row['CPU_revenue_B'] = prior_cpu
controls['joint_anchor_old_CPU2028plus_growth_pooled_old_growth'] = control
summary = []
cases = {}
checks = []


def run_case(name: str, economic: dict, anchor: dict | None) -> None:
    value = engine.build_case(delivery='preferred', revised_other=True, component_margin=True, normalized_growth=economic['normalized_growth'], cpu_margin=economic['CPU_margin'], anchor_case=anchor)
    rows = value['annual_rows']
    if anchor:
        for r in anchor['annual_rows']:
            for field in ['CPU_revenue_B', 'client_revenue_B', 'Other_DCAI_B']:
                assert abs(rows[r['year']][field] - r[field]) < 1e-9
        delta_cash = anchor['Q4_2026']['opening2027_economic_cash_delta_B']
        assert abs(value['treasury'][2027]['opening_cash_B'] - engine.FUND[2027]['opening_economic_cash_B'] - delta_cash) < 1e-9
        assert abs(value['values'][2026]['cash_B'] - engine.FUND[2027]['opening_economic_cash_B'] - delta_cash) < 1e-9
        revenue_delta = sum(rows[2027][f] - engine.HOST[2027][h] for f, h in [('CPU_revenue_B', 'server_CPU_revenue_proxy_B'), ('client_revenue_B', 'client_revenue_B'), ('Other_DCAI_B', 'Other_DCAI_revenue_B')])
        expected_wc = engine.RAW[2027]['WC_cash_use_B'] + .1 * (revenue_delta - anchor['Q4_2026']['net_consolidated_revenue_delta_B'])
        assert abs(rows[2027]['WC_cash_use_B'] - expected_wc) < 1e-9
    cpu_factor = 1.02**2 if economic['normalized_growth'] else (1 + engine.HOST[2031]['server_unit_growth']) * (1 + engine.HOST[2031]['server_ASP_growth'])
    client_factor = (1 + engine.HOST[2031]['client_unit_growth']) * (1 + engine.HOST[2031]['client_ASP_growth'])
    assert abs(rows[2031]['CPU_revenue_B'] - rows[2030]['CPU_revenue_B'] * cpu_factor) < 1e-8
    assert abs(rows[2031]['client_revenue_B'] - rows[2030]['client_revenue_B'] * client_factor) < 1e-8
    assert abs(rows[2031]['Other_DCAI_B'] - rows[2030]['Other_DCAI_B'] * (1 + engine.HOST[2031]['Other_DCAI_growth'])) < 1e-8
    target = value['values'][2030]['price_USD']
    row = {'case': name, 'planning_value_USD': value['values'][2026]['price_USD'], 'target2030_USD': target, 'annual_price_return_from52_25': (target / engine.ENTRY) ** (1 / engine.YEARS) - 1, 'consolidated_revenue2027_B': rows[2027]['consolidated_revenue_B'], 'CPU_revenue2030_B': rows[2030]['CPU_revenue_B'], 'consolidated_revenue2030_B': rows[2030]['consolidated_revenue_B'], 'EBIT2030_B': rows[2030]['EBIT_B'], 'opening2027_cash_B': value['treasury'][2027]['opening_cash_B'], 'minimum_annual_cash_B': value['minimum_annual_cash_B'], 'owner_cash2027to2030_B': sum(r['owner_cash_B'] for r in value['treasury'].values()), 'DCAI_margin2040': rows[2040]['DCAI_margin'], 'after2030_operating_value_share_at2026': value['values'][2030]['total_operating_value_B'] / (1 + engine.R) ** 4 / value['values'][2026]['total_operating_value_B'], 'entry_ceiling_for10pct_annual_return_USD': target / 1.1 ** engine.YEARS}
    summary.append(row)
    cases[name] = {'values': value['values'], 'treasury': value['treasury'], 'annual_rows': rows}
    checks.append({'case': name, 'status': 'Passed annual override, openingcash,2027WC and2031carryforward checks'})


for economic_name, economic in policy['economic_sets'].items():
    run_case(f'unchanged_anchor__{economic_name}', economic, None)
    for anchor_name, anchor in anchors.items():
        run_case(f'{anchor_name}__{economic_name}', economic, anchor)
for name, control in controls.items():
    run_case(name, policy['economic_sets']['pooled_old_growth'], control)
assert hashlib.sha256(engine_path.read_bytes()).hexdigest() == engine_hash
result = {'computed_utc': datetime.now(timezone.utc).isoformat(), 'root_engine': {'path': str(engine_path), 'sha256': engine_hash}, 'input_hashes': {'policy': hashlib.sha256(policy_path.read_bytes()).hexdigest(), 'anchors': hashlib.sha256(anchors_path.read_bytes()).hexdigest(), 'root_input_files': {name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in engine.FILES.items()}}, 'summary': summary, 'cases': cases, 'checks': checks, 'limits': ['Unweighted planning scenarios, not probabilities or confidence intervals.', 'Q4anchor improvements and retainedgrowth/margins are not independent outcomes with knownjointprobability.', 'Fixedcashincome is inherited fromrootengine; extraopeningcashdoesnotcreateanadditionalinterestwindfall.', 'No newrootenginepolicy orpricinginput selected bythese outputs.']}
(OUT / 'anchor_valuation_overlay_results.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(summary, indent=2))

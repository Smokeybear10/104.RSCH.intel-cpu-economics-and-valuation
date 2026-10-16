import copy
import hashlib
import json
import math
from pathlib import Path
import rebuild_valuation as model

OUT = Path(__file__).resolve().parent
CONTROL_PATH = OUT.parent / 'factory/packaging_margin_controls.json'
PACK_PATH = model.ROOT / 'work/three_hour/active_research/intel_competition_screen_2026_11_04/external_packaging_operating_policy_2026_11_04.json'
controls = json.loads(CONTROL_PATH.read_text())
pack = {r['year']: r for r in json.loads(PACK_PATH.read_text())['annual_rows']}
levels = {'unchanged_owned_case': None, 'rounded_Amkor_company_Q3_margin11_3pct_control': .113,
    'rounded_ASE_ATM_Q3_margin20pct_control': .20, 'flat25pct_from2030_no_mature27pct': .25,
    'Intel_attributed_aspiration30pct_control': .30}
errors, rows_out = [], []
for rate_key, cases in controls['results'].items():
    rate = float(rate_key)
    for name, expected in cases.items():
        level = levels[name]
        rows = copy.deepcopy(model.BASE)
        change = {}
        for y, row in rows.items():
            old = pack[y]['gross_program_operating_margin_after_direct_DA']
            delta_margin = 0 if y < 2030 or level is None else level - old
            gross_delta = delta_margin * row['gross_new_packaging_B']
            embed_delta = delta_margin * row['shadow_packaging_B']
            incremental_delta = delta_margin * row['net_new_packaging_B']
            row['Foundry_profit_B'] += embed_delta
            row['net_packaging_profit_B'] += incremental_delta
            row['EBIT_B'] += gross_delta
            model.close_cash(row)
            change[y] = gross_delta * (1 - row['tax_rate'])
            errors.append(abs(change[y] - row['parent_unlevered_cash_B'] + model.BASE[y]['parent_unlevered_cash_B']))
            a = next(x for x in expected['audit'] if x['year'] == y)
            errors += [abs(gross_delta - a['gross_program_EBIT_delta_B']), abs(embed_delta - a['embedded_host_EBIT_delta_B']), abs(incremental_delta - a['incremental_EBIT_delta_B'])]
        for endpoint, key in [(2026, 'Dec2026_planning_value_USD'), (2030, 'Dec2030_target_USD')]:
            rebuilt = model.value(rows, rate, endpoint)['price_USD']
            errors.append(abs(rebuilt - expected[key]))
            direct = math.fsum(change[y] / (1 + rate) ** (y - endpoint) for y in range(endpoint + 1, 2041))
            direct += change[2041] / (rate - .03) / (1 + rate) ** (2040 - endpoint)
            if endpoint == 2030:
                direct += math.fsum(change[y] for y in range(2027, 2031))
            errors.append(abs(model.value(model.BASE, rate, endpoint)['price_USD'] + direct / 5.51 - rebuilt))
            rows_out.append({'case': name, 'rate': rate, 'endpoint': endpoint, 'verified_price_USD': rebuilt})
        errors += [abs(expected['EBIT2030_B'] - rows[2030]['EBIT_B']),
                   abs(expected['host_Foundry_EBIT2030_B'] - rows[2030]['Foundry_profit_B']),
                   abs(expected['net_packaging_EBIT2030_B'] - rows[2030]['net_packaging_profit_B'])]
assert max(errors) < 1e-9
out = {'status': 'passed', 'numeric_comparisons': len(errors), 'maximum_error': max(errors),
    'method': 'Independent frozen-row APV rebuild plus direct discounted aftertax EBITdelta identity; no factory engine imported.',
    'control_sha256': hashlib.sha256(CONTROL_PATH.read_bytes()).hexdigest(), 'results': rows_out,
    'limits': 'Arithmetic audit only. ASE/Amkor margin scope differs from Intel; controls do not validate Intel fees, program scale or forecast margins. No selected forecast changed.'}
(OUT / 'independent_factory_control_audit.json').write_text(json.dumps(out, indent=2) + '\n')
print(json.dumps({k:v for k,v in out.items() if k != 'results'}, indent=2))

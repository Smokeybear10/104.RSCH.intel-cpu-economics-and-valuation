import copy
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path


OUT = Path(__file__).resolve().parent
namespace = {'__file__': str(OUT / 'extended_scenarios.py')}
exec((OUT / 'extended_scenarios.py').read_text().split('\ncases = ')[0], namespace)
base_rows = namespace['base_rows']
host = namespace['host']
value = namespace['value']
close_cash = namespace['close_cash']
base = value(copy.deepcopy(base_rows))
policy_path = OUT / 'other_DCAI_scenario_policy.json'
policy = json.loads(policy_path.read_text())
other_2026 = 5.19
adjustment = (3 / 3.36) ** (1 / 3)
output = {}

for name in policy['cases']:
    output[name] = {}
    for retention in (.1, .2, .3):
        rows = copy.deepcopy(base_rows)
        prior_delta = 0
        prior_new_other = other_2026
        audit_rows = []
        for year, row in rows.items():
            old_other = host[year]['Other_DCAI_revenue_B']
            if name == 'whole_other_tripling_2030':
                if year == 2027:
                    new_other = old_other
                elif year <= 2030:
                    new_other = prior_new_other * old_other / host[year - 1]['Other_DCAI_revenue_B'] * adjustment
                else:
                    new_other = prior_new_other * old_other / host[year - 1]['Other_DCAI_revenue_B']
            else:
                new_other = old_other if year <= 2030 else host[2030]['Other_DCAI_revenue_B'] * 1.03 ** (year - 2030)
            delta = new_other - old_other
            ebit_delta = delta * retention
            old_dcai_profit = row['DCAI_product_margin'] * row['DCAI_revenue_B']
            row['DCAI_revenue_B'] += delta
            row['DCAI_product_margin'] = (old_dcai_profit + ebit_delta) / row['DCAI_revenue_B']
            row['capital_denominator_revenue_B'] += delta
            row['EBIT_B'] += ebit_delta
            wc_delta = .1 * (delta - prior_delta)
            row['WC_cash_use_B'] += wc_delta
            if year <= 2030:
                row['net_operating_investment_B'] += wc_delta
            else:
                investment_delta = (delta - prior_delta) / .8
                row['net_operating_investment_B'] += investment_delta
                row['physical_capex_B'] += investment_delta - wc_delta
            assert abs(row['physical_capex_B'] - row['DA_B'] + row['WC_cash_use_B'] - row['net_operating_investment_B']) < 1e-12
            if year in (2031, 2032):
                assert row['physical_capex_B'] > {2031: 5, 2032: 2}[year]
            close_cash(row)
            audit_rows.append({'year': year, 'base_Other_DCAI_B': old_other, 'scenario_Other_DCAI_B': new_other, 'revenue_delta_B': delta, 'group_EBIT_delta_B': ebit_delta, 'net_investment_delta_B': row['net_operating_investment_B'] - base_rows[year]['net_operating_investment_B'], 'parent_unlevered_cash_delta_B': row['parent_unlevered_cash_B'] - base_rows[year]['parent_unlevered_cash_B']})
            prior_delta, prior_new_other = delta, new_other
        assert abs(rows[2041]['parent_unlevered_cash_B'] / rows[2040]['parent_unlevered_cash_B'] - 1.03) < 1e-12
        result = value(rows)
        target = result['values'][2030]['price_USD']
        delta_pv = sum((rows[y]['parent_unlevered_cash_B'] - base_rows[y]['parent_unlevered_cash_B']) / (1.11555 ** (y - 2026)) for y in range(2027, 2041))
        delta_pv += (rows[2041]['parent_unlevered_cash_B'] - base_rows[2041]['parent_unlevered_cash_B']) / (.11555 - .03) / 1.11555 ** 14
        check = result['values'][2026]['equity_B'] - base['values'][2026]['equity_B'] - delta_pv
        assert abs(check) < 1e-10
        output[name][str(retention)] = {'values': result['values'], 'treasury': result['treasury'], 'rows': audit_rows, 'cash_rows': rows, 'summary': {'planning_value_USD': result['values'][2026]['price_USD'], 'target_USD': target, 'target_delta_USD': target - base['values'][2030]['price_USD'], 'annual_price_return': (target / 52.22) ** (1 / namespace['YEARS']) - 1, 'minimum_cash_B': min(r['ending_economic_cash_B'] for r in result['treasury'].values()), '2030_ending_cash_delta_B': result['treasury'][2030]['ending_economic_cash_B'] - base['treasury'][2030]['ending_economic_cash_B'], 'independent_equity_delta_check_B': check}}

result = {'computed_utc': datetime.now(timezone.utc).isoformat(), 'policy_sha256': hashlib.sha256(policy_path.read_bytes()).hexdigest(), 'policy': policy, 'common_2028_2030_growth_factor_adjustment': adjustment, 'mixture_identity': {'residual_3pct_four_year_factor': 1.03 ** 4, 'purpose_built_fraction_required_for3_36_factor_if_its_own_factor3': (3.36 - 1.03 ** 4) / (3 - 1.03 ** 4), 'interpretation': 'A fraction above100% demonstrates that narrower3x cannot alone establish broader3.36x under these illustrative timing and residual-growth assumptions. Those assumptions are not disclosures.'}, 'results': output}
(OUT / 'other_DCAI_scenario_results.json').write_text(json.dumps(result, indent=2) + '\n')
for name, margins in output.items():
    for margin, details in margins.items():
        print(name, margin, json.dumps(details['summary']))

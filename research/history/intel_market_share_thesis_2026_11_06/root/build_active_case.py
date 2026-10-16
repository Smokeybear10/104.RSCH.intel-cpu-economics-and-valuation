import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


OUT = Path(__file__).resolve().parent
PRIOR = OUT.parents[1] / 'intel_two_hour_completion_2026_11_06'
paths = {
    'operations': PRIOR / 'quarterly/anchor_valuation_overlay_results.json',
    'valuation': PRIOR / 'risk_policy/rounded_ERP_comparison_results.json',
    'decision': OUT / 'decision_policy.json',
}
inputs = {key: json.loads(path.read_text()) for key, path in paths.items()}
case = copy.deepcopy(inputs['operations']['cases'][inputs['decision']['operating_case']])
risk = inputs['valuation']['cases']['existing_favorable_operating']
for year in ('2026', '2030'):
    case['values'][year].update(risk['values'][year])
    value = case['values'][year]
    value['total_operating_value_B'] = value['explicit_operating_PV_B'] + value['terminal_operating_PV_B']
    value['equity_B'] = value['price_USD'] * 5.51
    check = (value['total_operating_value_B'] + value['financing_shield_PV_B']
             + value['cash_B'] - value['debt_B'] + value['net_other_assets_B']
             + value['remaining_escrow_PV_B'] - value['remaining_acquisition_PV_B'])
    assert abs(check - value['equity_B']) < 1e-9
case['annual_price_return'] = risk['annual_price_return']
case['operating_rate'] = inputs['decision']['operating_asset_rate']
case['reference_price_USD'] = inputs['decision']['reference_price_USD']
case['terminal'] = risk['terminal']
case['after2030_operating_value_share'] = (
    case['values']['2030']['total_operating_value_B'] / (1 + case['operating_rate']) ** 4
    / case['values']['2026']['total_operating_value_B']
)
case['planning_value_premium'] = case['values']['2026']['price_USD'] / case['reference_price_USD'] - 1
case['target_total_price_return'] = case['values']['2030']['price_USD'] / case['reference_price_USD'] - 1
case['metadata'] = {
    'built_utc': datetime.now(timezone.utc).isoformat(),
    'input_files': {key: {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()} for key, path in paths.items()},
    'case_name': 'Owned long thesis; previously the favorable operating scenario',
    'scope': 'Selection of an existing forecast and risk method. No operating forecast raised or new valuation formula introduced.',
    'date_boundary': 'December 2026 planning value and November 5 entry differ by 56 days.',
}
(OUT / 'active_case.json').write_text(json.dumps(case, indent=2) + '\n')
print(json.dumps({key: case[key] for key in ('annual_price_return', 'after2030_operating_value_share', 'planning_value_premium', 'target_total_price_return')}, indent=2))

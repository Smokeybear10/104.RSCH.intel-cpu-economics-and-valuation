import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import calculate_current_hurdles as model
import calculate_delivery_joint as cases

OUT = Path(__file__).resolve().parent
SOURCE_PATH = model.ROOT / 'work/three_hour/active_research/intel_market_share_thesis_2026_11_06/root/owned_quarterly_cash_results.json'
SOURCE = json.loads(SOURCE_PATH.read_text())
POLICY_PATH = model.RESEARCH / 'intel_two_hour_completion_2026_11_06/root/quarterly_cash_policy_before_calculation.json'
POLICY = json.loads(POLICY_PATH.read_text())
CPU = json.loads(cases.DELAY_PATH.read_text())['delay_no_catchup']


def build(annual: dict, timing: str, delayed: bool) -> dict:
    old_rows = SOURCE[timing]['quarterly_rows']
    cash = model.ACTIVE['values']['2026']['cash_B']
    result, errors = [], []
    for y in range(2027, 2031):
        rows = copy.deepcopy([r for r in old_rows if r['year'] == y])
        for i, row in enumerate(rows):
            old_cpu = row['CPU_revenue_B']
            if delayed:
                row['CPU_revenue_B'] = CPU['quarterly_2027_B'][i] if y == 2027 else annual[y]['CPU_revenue_B'] * [ .23, .24, .26, .27][i]
            delta_cpu = row['CPU_revenue_B'] - old_cpu
            if delayed:
                row.pop('CPU_unit_index', None)
                row.pop('CPU_ASP_index', None)
            delta_foundry = (annual[y]['Foundry_profit_B'] - model.BASE[y]['Foundry_profit_B']) / 4
            for key in ['DCAI_revenue_B', 'Products_revenue_B', 'consolidated_revenue_B']:
                row[key] += delta_cpu
            row['DCAI_profit_B'] += .5 * delta_cpu
            row['Foundry_profit_B'] += delta_foundry
            row['EBIT_B'] += .5 * delta_cpu + delta_foundry
        positive = sum(max(r['EBIT_B'], 0) for r in rows)
        for i, row in enumerate(rows):
            a = annual[y]
            row['ordinary_operating_tax_B'] = a['ordinary_operating_tax_B'] * max(row['EBIT_B'], 0) / positive if positive else 0
            row['WC_cash_use_B'] = a['WC_cash_use_B'] * POLICY['investment']['WC_cash_use_weights'][i]
            row['net_operating_investment_B'] = row['physical_capex_B'] - row['DA_B'] + row['WC_cash_use_B']
            row['parent_unlevered_cash_B'] = (row['EBIT_B'] - row['ordinary_operating_tax_B'] - row['net_operating_investment_B']
                - row['lease_cash_B'] - row['minority_cash_B'] + row['old_credit_collection_B']
                + row['new_credit_collection_B'] - row['credit_basis_loss_tax_B'])
            row['owner_cash_B'] = (row['parent_unlevered_cash_B'] - row['ordinary_interest_B'] - row['capitalized_interest_B']
                                  + row['cash_income_B'] * (1 - a['tax_rate']) + row['financing_shield_B'])
            row['opening_cash_B'] = cash
            cash += row['owner_cash_B'] + row['escrow_cash_B'] - row['Classiq_cash_B'] - row['principal_B']
            row['ending_cash_B'] = cash
        for key in ['CPU_revenue_B', 'consolidated_revenue_B', 'DCAI_profit_B', 'Foundry_profit_B', 'EBIT_B', 'ordinary_operating_tax_B', 'WC_cash_use_B', 'physical_capex_B', 'parent_unlevered_cash_B']:
            errors.append(abs(sum(r[key] for r in rows) - annual[y][key]))
        expected_cash = model.ACTIVE['treasury'][str(y)]['ending_cash_B'] + sum(annual[z]['parent_unlevered_cash_B'] - model.BASE[z]['parent_unlevered_cash_B'] for z in range(2027, y + 1))
        errors.append(abs(rows[-1]['ending_cash_B'] - expected_cash))
        result.extend(rows)
    assert max(errors) < 1e-9, max(errors)
    minimum = min(result, key=lambda r: r['ending_cash_B'])
    return {'minimum_quarter_cash_B': minimum['ending_cash_B'], 'minimum_period': f"Q{minimum['quarter']} {minimum['year']}",
            'headroom_above_assumed20B_buffer_B': minimum['ending_cash_B'] - 20,
            'buffer_shortfall_B': max(20 - minimum['ending_cash_B'], 0),
            'quarters_below20B': [f"Q{r['quarter']} {r['year']}" for r in result if r['ending_cash_B'] < 20],
            'annual_reconciliation_max_error_B': max(errors), 'quarterly_rows': result}


def main() -> None:
    assert SOURCE['input_files']['active_case']['sha256'] == hashlib.sha256(model.ACTIVE_PATH.read_bytes()).hexdigest()
    controls = {}
    for timing in ['base', 'concentrated_timing_stress']:
        rebuilt = build(model.BASE, timing, False)
        errors = [abs(a['ending_cash_B'] - b['ending_cash_B']) for a, b in zip(rebuilt['quarterly_rows'], SOURCE[timing]['quarterly_rows'])]
        assert max(errors) < 1e-9
        controls[timing] = {'max_cash_error_B': max(errors), 'minimum_quarter_cash_B': rebuilt['minimum_quarter_cash_B']}
    annual_delay = {int(y): v for y, v in CPU['annual_CPU_B'].items()}
    results = {}
    for name, annual, delayed in [('one_quarter_CPU_ramp_delay', cases.delivery_rows(annual_delay), True),
                                 ('Foundry_breakeven_also_applies_to_terminalROC_joint_cases', cases.factory_rows(), False)]:
        results[name] = {timing:build(annual,timing,delayed) for timing in ['base','concentrated_timing_stress']}
    out={'computed_utc':datetime.now(timezone.utc).isoformat(), 'controls':controls,
         'inputs': {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [SOURCE_PATH,POLICY_PATH,cases.DELAY_PATH,OUT/'quarterly_overlay_policy_before_calculation.json']},
         'cases':results,
         'interpretation':'Both operating stresses breach the chosen20Bquarter-endbuffer under concentratedtiming. Valuations retain existingfinancing schedules;they do not fund the buffer breach or value additionalfunding actions. This is not a debtcovenant or insolvencythreshold.',
         'limits':['Timing andcashbufferareanalystassumptions, notreportedcommitments.','No dailycashlow or unrestrictedcashaccess claim.','TerminalROCstressbegins2041; it hasnoeffecton2027-30liquidity.']}
    (OUT/'quarterly_overlay_results.json').write_text(json.dumps(out,indent=2)+'\n')
    print(json.dumps({'controls':controls,'cases':{n:{t:{k:v for k,v in x.items() if k!='quarterly_rows'} for t,x in d.items()} for n,d in results.items()}},indent=2))


if __name__ == '__main__':
    main()

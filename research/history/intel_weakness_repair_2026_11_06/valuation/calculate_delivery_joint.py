import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import calculate_current_hurdles as model

OUT = Path(__file__).resolve().parent
BASE = model.BASE
RESEARCH = model.ROOT / 'work/three_hour/active_research'
DELAY_PATH = OUT.parent / 'cpu/cpu_ramp_results.json'
FACTORY_PATH = OUT.parent / 'factory/factory_results.json'
HOST = {r['year']: r for r in json.loads((RESEARCH / 'pricing_and_competition_review_2026_11_04/intel_server_ASP_mix_operating_policy.json').read_text())['annual_rows']}
PACK = {r['year']: r for r in json.loads((RESEARCH / 'intel_competition_screen_2026_11_04/external_packaging_operating_policy_2026_11_04.json').read_text())['annual_rows']}


def delivery_rows(annual: dict) -> dict:
    rows = copy.deepcopy(BASE)
    previous_delta = 0
    for y in range(2027, 2042):
        row = rows[y]
        row['CPU_revenue_B'] = annual[y] if y <= 2040 else rows[y - 1]['CPU_revenue_B'] * 1.03
        delta = row['CPU_revenue_B'] - BASE[y]['CPU_revenue_B']
        for key in ['DCAI_revenue_B', 'Products_revenue_B', 'consolidated_revenue_B', 'host_capital_revenue_B']:
            row[key] = BASE[y][key] + delta
        if y <= 2030:
            row['DCAI_profit_B'] = BASE[y]['DCAI_profit_B'] + .5 * delta
            row['CPU_margin'] = (row['DCAI_profit_B'] - row['Other_DCAI_B'] * row['Other_DCAI_margin']) / row['CPU_revenue_B']
            row['EBIT_B'] = BASE[y]['EBIT_B'] + .5 * delta
            row['WC_cash_use_B'] = BASE[y]['WC_cash_use_B'] + .1 * (delta - previous_delta)
            previous_delta = delta
        else:
            phase = min((y - 2030) / 10, 1)
            row['CPU_margin'] = rows[2030]['CPU_margin'] + phase * (BASE[2040]['CPU_margin'] - rows[2030]['CPU_margin'])
            row['DCAI_profit_B'] = row['CPU_revenue_B'] * row['CPU_margin'] + row['Other_DCAI_B'] * row['Other_DCAI_margin']
            ratio = rows[2030]['Foundry_profit_B'] / rows[2030]['Products_revenue_B']
            row['Foundry_profit_B'] = ratio * row['Products_revenue_B']
            row['EBIT_B'] = sum(row[key] for key in ['DCAI_profit_B', 'CCPG_profit_B', 'Foundry_profit_B', 'net_packaging_profit_B', 'Other_profit_less_corporate_B'])
            growth = row['host_capital_revenue_B'] - rows[y - 1]['host_capital_revenue_B']
            row['DA_B'] = HOST[y]['DA_fraction_of_Products_revenue'] * row['Products_revenue_B'] + PACK[y]['incremental_DA_B']
            row['WC_cash_use_B'] = .1 * growth + PACK[y]['incremental_WC_cash_use_B']
            investment = growth / .8 + PACK[y]['incremental_net_operating_investment_B']
            row['physical_capex_B'] = row['DA_B'] + investment - row['WC_cash_use_B']
        row['DCAI_margin'] = row['DCAI_profit_B'] / row['DCAI_revenue_B']
        model.close_cash(row)
    return rows


def factory_rows() -> dict:
    rows = copy.deepcopy(BASE)
    for y, row in rows.items():
        profit = {2027: -4, 2028: -2.5, 2029: -1}.get(y, 0)
        row['EBIT_B'] += profit - row['Foundry_profit_B']
        row['Foundry_profit_B'] = profit
        model.close_cash(row)
    return rows


def combined_rows(roc: float) -> dict:
    rows = factory_rows()
    investment = .03 * rows[2041]['NOPAT_B'] / roc
    rows[2041]['physical_capex_B'] += investment - rows[2041]['net_operating_investment_B']
    model.close_cash(rows[2041])
    return rows


def output_case(rows: dict, rate: float) -> dict:
    cash = model.ACTIVE['values']['2026']['cash_B']
    treasury = []
    for y in range(2027, 2031):
        f = model.FUND[y]
        owner = f['owner_cash_B'] + rows[y]['parent_unlevered_cash_B'] - BASE[y]['parent_unlevered_cash_B']
        cash += owner + f['escrow_cash_B'] - f['Classiq_cash_B'] - f['principal_B']
        treasury.append({'year': y, 'ending_cash_B': cash, 'parent_cash_B': rows[y]['parent_unlevered_cash_B']})
    assert abs(cash - model.value(rows, rate)['2030']['cash_B']) < 1e-9
    return {**model.summarize(rows, rate), 'company_sales_2028_B': rows[2028]['consolidated_revenue_B'],
            'EBIT_2030_B': rows[2030]['EBIT_B'], 'parent_cash_2030_B': rows[2030]['parent_unlevered_cash_B'],
            'annual_treasury': treasury, 'minimum_annual_cash_B': min(r['ending_cash_B'] for r in treasury),
            'near_term_capex_B': sum(rows[y]['physical_capex_B'] for y in range(2027, 2031))}


def main() -> None:
    policy_path = OUT / 'additional_stress_policy_before_calculation.json'
    policy = json.loads(policy_path.read_text())
    delay = json.loads(DELAY_PATH.read_text())
    annual = {int(y): x for y, x in delay['delay_no_catchup']['annual_CPU_B'].items()}
    control = delivery_rows({y: r['CPU_revenue_B'] for y, r in BASE.items()})
    errors = [abs(control[y][key] - BASE[y][key]) for y in BASE for key in ['CPU_revenue_B', 'CPU_margin', 'Foundry_profit_B', 'EBIT_B', 'physical_capex_B', 'parent_unlevered_cash_B']]
    assert max(errors) < 1e-9, max(errors)
    factory = json.loads(FACTORY_PATH.read_text())['cases']
    factory_errors = []
    for rate in policy['rates']:
        rebuilt = model.value(factory_rows(), rate)
        expected = factory[str(rate)]['breakeven_only']
        factory_errors.extend([abs(rebuilt['2026']['price_USD'] - expected['Dec2026_value_USD']), abs(rebuilt['2030']['price_USD'] - expected['Dec2030_target_USD'])])
    assert max(factory_errors) < 1e-9
    results = []
    for rate in policy['rates']:
        results.append({'case':'2027 ramp delayed one quarter; no sales catch-up; capital policy unchanged', **output_case(delivery_rows(annual), rate)})
        for roc in [.15, rate]:
            results.append({'case':'Foundry breakeven only + lower terminal ROC', 'terminal_ROC_assumption':roc, **output_case(combined_rows(roc), rate)})
    output={'computed_utc':datetime.now(timezone.utc).isoformat(), 'input_sha256':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [model.ACTIVE_PATH,DELAY_PATH,FACTORY_PATH,policy_path]},
            'checks':{'unchanged_delivery_max_error':max(errors),'independent_factory_reproduction_max_error':max(factory_errors)},
            'cases':results,'limits':['Capital policy is preserved, not physical capex in all years. Physical capex2027-30 remains124.5B; post2030growthinvestment adjusts with growth under existing0.8rule.',
            'Factory and terminalROC jointly revalued on changedterminalNOPAT. These are not summed singlefactor losses.',
            'Minimum annual cash does not establish minimum quarterly or daily cash. The recalculated quarterly_overlay_results.json shows that joint operating and concentrated timing stresses can breach the assumed $20B buffer. Corrective financing or spending actions and their valuation costs remain unmodeled.',
            'No scenario probability estimated; noactivedatasetmodified.']}
    (OUT/'delivery_joint_results.json').write_text(json.dumps(output,indent=2)+'\n')
    print(json.dumps(output,indent=2))


if __name__ == '__main__':
    main()

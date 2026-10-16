import copy
import hashlib
import importlib.util
import json
import math
import sys
from datetime import date
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path('/Users/thomasou/Documents/Codex/2026-11-02/lo')
OUT = Path(__file__).resolve().parent
RESEARCH = ROOT / 'work/three_hour/active_research'
ACTIVE_PATH = RESEARCH / 'intel_market_share_thesis_2026_11_06/root/active_case.json'
ACTIVE = json.loads(ACTIVE_PATH.read_text())
BASE = {int(y): r for y, r in ACTIVE['annual_rows'].items()}
TREASURY = {int(y): r for y, r in ACTIVE['treasury'].items()}
HORIZON = (date(2030, 12, 31) - date(2026, 11, 6)).days / 365.25
RATE, SHARES = .11555, 5.51


def close_cash(row: dict) -> None:
    row['ordinary_operating_tax_B'] = max(row['EBIT_B'], 0) * row['tax_rate']
    row['NOPAT_B'] = row['EBIT_B'] - row['ordinary_operating_tax_B']
    row['net_operating_investment_B'] = row['physical_capex_B'] - row['DA_B'] + row['WC_cash_use_B']
    row['parent_unlevered_cash_B'] = (row['NOPAT_B'] - row['net_operating_investment_B']
        - row['lease_cash_B'] - row['minority_cash_B'] + row['old_credit_collection_B']
        + row['new_credit_collection_B'] - row['credit_basis_loss_tax_B'])


def apv(rows: dict, rate: float, endpoint: int) -> dict:
    explicit = math.fsum(rows[y]['parent_unlevered_cash_B'] / (1 + rate) ** (y - endpoint)
                         for y in range(endpoint + 1, 2041))
    terminal = rows[2041]['parent_unlevered_cash_B'] / (rate - .03) / (1 + rate) ** (2040 - endpoint)
    shield = math.fsum(rows[y]['financing_shield_B'] / (1 + rate) ** (y - endpoint)
                       for y in range(endpoint + 1, 2041))
    shield += rows[2041]['financing_shield_B'] / rate / (1 + rate) ** (2040 - endpoint)
    cash = ACTIVE['values'][str(endpoint)]['cash_B']
    if endpoint == 2030:
        cash += math.fsum(rows[y]['parent_unlevered_cash_B'] - BASE[y]['parent_unlevered_cash_B'] for y in range(2027, 2031))
    claims = cash - ACTIVE['values'][str(endpoint)]['debt_B'] + 4.502
    claims += math.fsum((TREASURY[y]['escrow_cash_B'] - TREASURY[y]['Classiq_cash_B'])
                       / (1 + rate) ** (y - endpoint) for y in range(endpoint + 1, 2031))
    equity = explicit + terminal + shield + claims
    return {'explicit_B': explicit, 'terminal_B': terminal, 'shield_B': shield, 'net_assets_B': claims,
            'equity_B': equity, 'price_USD': equity / SHARES}


def summary(rows: dict, funded_cost: float = 0) -> dict:
    value = apv(rows, RATE, 2030)
    target = value['price_USD'] - funded_cost
    return {'target_USD': target, 'return_at40': (target / 40) ** (1 / HORIZON) - 1,
            'entry_ceiling12_USD': target / 1.12 ** HORIZON,
            'CPU2027_B': rows[2027]['CPU_revenue_B'], 'CPU2030_B': rows[2030]['CPU_revenue_B'],
            'capex2027_2030_B': math.fsum(rows[y]['physical_capex_B'] for y in range(2027, 2031)),
            'cash2030_B': ACTIVE['values']['2030']['cash_B'] + math.fsum(rows[y]['parent_unlevered_cash_B'] - BASE[y]['parent_unlevered_cash_B'] for y in range(2027, 2031)),
            'net_investment2031_2040_B': math.fsum(rows[y]['net_operating_investment_B'] for y in range(2031, 2041))}


def joint(rows: dict) -> dict:
    rows = copy.deepcopy(rows)
    for y, row in rows.items():
        profit = {2027: -4, 2028: -2.5, 2029: -1}.get(y, 0)
        row['EBIT_B'] += profit - row['Foundry_profit_B']
        row['Foundry_profit_B'] = profit
        close_cash(row)
    row = rows[2041]
    row['physical_capex_B'] += .03 * row['NOPAT_B'] / .15 - row['net_operating_investment_B']
    close_cash(row)
    return rows


prior_path = RESEARCH / 'intel_weakness_repair_2026_11_06/valuation/calculate_delivery_joint.py'
sys.path.insert(0, str(prior_path.parent))
spec = importlib.util.spec_from_file_location('prior_delivery', prior_path)
delivery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(delivery)


def degraded_joint(fraction: float) -> dict:
    annual = {y: row['CPU_revenue_B'] * (1 - fraction) for y, row in BASE.items()}
    return joint(delivery.delivery_rows(annual))


errors = []
for y in (2026, 2030):
    value = apv(BASE, .10625, y)
    errors.append(abs(value['price_USD'] - ACTIVE['values'][str(y)]['price_USD']))
assert max(errors) < 1e-10
cash_errors = []
for r in BASE.values():
    row = copy.deepcopy(r)
    close_cash(row)
    cash_errors.append(abs(row['parent_unlevered_cash_B'] - r['parent_unlevered_cash_B']))
assert max(cash_errors) < 1e-10

funding = json.loads((RESEARCH / 'intel_valuation_resolution_2026_11_06/claims/claims_and_funding_results.json').read_text())
selected_funding = next(v for v in funding['cases']['Foundry_breakeven_also_applies_to_terminalROC_joint_cases']
                        if v['timing'] == 'concentrated_timing_stress'
                        and v['annual_simple_rate'] == .08 and v['immediate_cash_tax_benefit_fraction'] == 0)
cost = -selected_funding['Dec2030_per_share_delta_USD']
selected = summary(joint(BASE), cost)
assert abs(selected['target_USD'] - 64.7378499644682) < 1e-10
required_target = 40 * 1.12 ** HORIZON

lo, hi = 0, .1
for _ in range(70):
    mid = (lo + hi) / 2
    if summary(degraded_joint(mid))['target_USD'] > required_target:
        lo = mid
    else:
        hi = mid
threshold = (lo + hi) / 2

delay = json.loads((RESEARCH / 'intel_weakness_repair_2026_11_06/cpu/cpu_ramp_results.json').read_text())['delay_no_catchup']['persistent_level_loss']
combined = summary(degraded_joint(delay))

capital = joint(BASE)
for y in range(2031, 2041):
    delta_revenue = BASE[y]['host_capital_revenue_B'] - BASE[y - 1]['host_capital_revenue_B']
    capital[y]['physical_capex_B'] += delta_revenue * (1 / .6 - 1 / .8)
    close_cash(capital[y])

results = {
    'input_sha256': {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in (ACTIVE_PATH, prior_path)},
    'checks': {'APV_max_error_USD': max(errors), 'cash_identity_max_error_B': max(cash_errors)},
    'scope': 'Independent APV sum and selected-stress recreation. Existing reviewed CPU delivery propagation is reused without invoking main or writing upstream files.',
    'horizon_years': HORIZON,
    'base': {str(r): {str(y): apv(BASE, r, y) for y in (2026, 2030)} for r in (.10625, .11555)},
    'core_return_Nov6': (apv(BASE, .10625, 2030)['price_USD'] / 56.28) ** (1 / HORIZON) - 1,
    'higher_rate_return_Nov6': (apv(BASE, .11555, 2030)['price_USD'] / 56.28) ** (1 / HORIZON) - 1,
    'selected_funded_joint': selected,
    'required_target_at40_for12': required_target,
    'selected_joint_target_cushion_USD': selected['target_USD'] - required_target,
    'selected_joint_fractional_target_cushion': 1 - required_target / selected['target_USD'],
    'business_news_test': {
        'description': 'Apply a persistent CPU revenue level loss to the existing selected joint stress. Preserve all growth rates, near-term capex, existing profit response and post2030 investment policy; then jointly recompute Foundry breakeven and 15% terminal return. No price-move probability is claimed.',
        'fractional_CPU_loss_exhausting_12pct_hurdle_before_funding_cost': threshold,
        'threshold': summary(degraded_joint(threshold)),
        'already_modeled_one_quarter_delay_CPU_level_loss': delay,
        'selected_joint_plus_existing_CPU_delay_before_funding_cost': combined,
        'limitation': 'New combined stresses omit incremental revolver costs and altered cash income. Their targets are operating/claims comparisons before additional financing cost, not fully funded liquidity forecasts. Baseline cash income convention is retained. Failure before extra financing cost is enough to reject a claim that the original $40 hurdle survives this business-news test.'
    },
    'capital_timing_test': {
        'description': 'Keep the selected joint 2041 15% terminal-return assumption, but reduce host incremental revenue/net-investment from 0.8 to 0.6 for 2031–2040 only. All revenue, profit, DA, WC, near-term capital and terminal cash remain unchanged.',
        'case_before_funding_cost': summary(capital),
        'extra_investment2031_2040_B': math.fsum(capital[y]['net_operating_investment_B'] - joint(BASE)[y]['net_operating_investment_B'] for y in range(2031, 2041)),
        'limitation': 'Capital efficiency is a sensitivity, not new evidence that 0.6 is the correct forecast. This tests a period the selected terminal-only stress does not change.'
    },
    'later_entry_dates_same_target_no_new_news': {
        d: {'remaining_years': (date(2030,12,31)-date.fromisoformat(d)).days / 365.25,
            'selected_joint_12pct_entry_ceiling_USD': selected['target_USD'] / 1.12 ** ((date(2030,12,31)-date.fromisoformat(d)).days / 365.25)}
        for d in ('2026-11-06','2027-06-30','2027-12-31')
    },
    'finding_boundary': 'No unexplained cash double count, arithmetic failure, or material missing financing claim established. Tests challenge selection robustness and durable economics, not reproducibility.'
}
(OUT / 'decision_recheck_results.json').write_text(json.dumps(results, indent=2) + '\n')
print(json.dumps(results, indent=2))

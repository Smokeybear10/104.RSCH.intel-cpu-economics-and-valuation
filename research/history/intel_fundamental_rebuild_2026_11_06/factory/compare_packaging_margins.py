import copy
import hashlib
import importlib.util
import json
from datetime import date, datetime, timezone
from pathlib import Path


OUT = Path(__file__).resolve().parent
RESEARCH = OUT.parents[1]
ENGINE = RESEARCH / 'intel_two_hour_completion_2026_11_06/root/integrated_model.py'
ACTIVE = RESEARCH / 'intel_market_share_thesis_2026_11_06/root/active_case.json'
POLICY = RESEARCH / 'intel_competition_screen_2026_11_04/external_packaging_operating_policy_2026_11_04.json'
spec = importlib.util.spec_from_file_location('packaging_margin_control', ENGINE)
engine = importlib.util.module_from_spec(spec)
spec.loader.exec_module(engine)
active = json.loads(ACTIVE.read_text())
policy = json.loads(POLICY.read_text())
pack = {r['year']: r for r in policy['annual_rows']}
base_rows = {int(y): r for y, r in active['annual_rows'].items()}
cash_delta = active['values']['2026']['cash_B'] - engine.FUND[2027]['opening_economic_cash_B']
horizon = (date(2030, 12, 31) - date(2026, 11, 6)).days / 365.25


def calculate(level: float | None, rate: float) -> dict:
    rows = copy.deepcopy(base_rows)
    audit = []
    for year, row in rows.items():
        old_margin = pack[year]['gross_program_operating_margin_after_direct_DA']
        new_margin = old_margin if level is None or year < 2030 else level
        margin_change = new_margin - old_margin
        gross_delta = row['gross_new_packaging_B'] * margin_change
        embedded_delta = row['shadow_packaging_B'] * margin_change
        incremental_delta = row['net_new_packaging_B'] * margin_change
        assert abs(gross_delta - embedded_delta - incremental_delta) < 1e-12
        row['Foundry_profit_B'] += embedded_delta
        row['net_packaging_profit_B'] += incremental_delta
        row['EBIT_B'] += gross_delta
        engine.close_cash(row)
        for field in ['physical_capex_B', 'DA_B', 'WC_cash_use_B', 'consolidated_revenue_B',
                      'CPU_revenue_B', 'DCAI_profit_B', 'CCPG_profit_B', 'lease_cash_B',
                      'minority_cash_B', 'old_credit_collection_B', 'new_credit_collection_B']:
            assert row[field] == base_rows[year][field], (year, field)
        assert abs(row['EBIT_B'] - sum(row[f] for f in ['DCAI_profit_B', 'CCPG_profit_B',
                   'Foundry_profit_B', 'net_packaging_profit_B', 'Other_profit_less_corporate_B'])) < 1e-10
        audit.append({'year': year, 'selected_gross_margin': old_margin, 'control_gross_margin': new_margin,
                      'gross_program_EBIT_delta_B': gross_delta,
                      'embedded_host_EBIT_delta_B': embedded_delta,
                      'incremental_EBIT_delta_B': incremental_delta})
    engine.R = rate
    case = engine.value(rows, cash_delta)
    target = case['values'][2030]['price_USD']
    return {
        'Dec2026_planning_value_USD': case['values'][2026]['price_USD'],
        'Dec2030_target_USD': target,
        'annual_price_return_from_Nov6_56_28': (target / 56.28) ** (1 / horizon) - 1,
        'EBIT2030_B': rows[2030]['EBIT_B'],
        'gross_packaging2030_B': rows[2030]['gross_new_packaging_B'],
        'host_Foundry_EBIT2030_B': rows[2030]['Foundry_profit_B'],
        'net_packaging_EBIT2030_B': rows[2030]['net_packaging_profit_B'],
        'audit': audit,
    }


results = {}
for rate in [.10625, .11555]:
    results[str(rate)] = {name: calculate(level, rate) for name, level in [
        ('unchanged_owned_case', None),
        ('rounded_Amkor_company_Q3_margin11_3pct_control', .113),
        ('rounded_ASE_ATM_Q3_margin20pct_control', .2),
        ('flat25pct_from2030_no_mature27pct', .25),
        ('Intel_attributed_aspiration30pct_control', .3),
    ]}
for endpoint in [2026, 2030]:
    key = 'Dec2026_planning_value_USD' if endpoint == 2026 else 'Dec2030_target_USD'
    assert abs(results['0.10625']['unchanged_owned_case'][key] - active['values'][str(endpoint)]['price_USD']) < 1e-10
out = {
    'computed_utc': datetime.now(timezone.utc).isoformat(),
    'purpose': 'Margin-only economic sensitivity; peer outcomes contextualize an owned forecast, not estimate Intel expected margins.',
    'unchanged_central_model': True,
    'inputs': {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in [ENGINE, ACTIVE, POLICY]},
    'method': 'Keep 2027-29 and all revenue/capital unchanged; from2030 replace the total program margin. Charge embedded-program EBIT change to host Foundry and remaining program change to net packaging. Recalculate tax, treasury and value once. Do not assume internal Foundry silently offsets the embedded margin miss.',
    'sources': {
        'ASE': 'https://www.sec.gov/Archives/edgar/data/1122411/000095010326016324/dp255760_6k.htm',
        'Amkor': 'https://www.sec.gov/Archives/edgar/data/1047127/000104712726000052/amkr-20260930.htm',
        'Intel_aspiration_primary_event_only': 'https://www.intc.com/news-events/ir-calendar/detail/20260826-deutsche-banks-2026-technology-conference',
    },
    'limits': [
        'ASE ATM is a blended assembly/test/material business; Amkor is a broader packaging/test company. Neither isolates Intel-equivalent EMIB-T services.',
        'Materials, process IP, testing, geography, utilization, D&A and R&D scope differ. These are economic controls, not a statistical peer band or bounds.',
        'Intel30pct aspiration comes from a third-party transcript of an issuer-confirmed event, not independently audio-verified.',
        'The return sensitivity has no forecast probabilities and does not validate7B future fees or accepted output.',
        'Fixed capital at unchanged output isolates retained cost/pricing economics. Sustained high margins could require extra investment; none is claimed free.',
        'December2026 planning value is not an exact November6 fair-value estimate.',
    ],
    'results': results,
}
(OUT / 'packaging_margin_controls.json').write_text(json.dumps(out, indent=2) + '\n')
print(json.dumps({rate: {k: {f: v for f, v in row.items() if f != 'audit'} for k, row in cases.items()}
                  for rate, cases in results.items()}, indent=2))

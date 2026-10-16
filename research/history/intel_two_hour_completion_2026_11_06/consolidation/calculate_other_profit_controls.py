from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import math

OUT = Path(__file__).resolve().parent
POLICY_PATH = OUT / 'other_profit_controls_policy_before_calculation.json'
MODEL_PATH = OUT.parent / 'root/integrated_results.json'
POLICY = json.loads(POLICY_PATH.read_text())
MODEL_HASH = hashlib.sha256(MODEL_PATH.read_bytes()).hexdigest()
assert MODEL_HASH == POLICY['root_results_sha256']
MODEL = json.loads(MODEL_PATH.read_text())
BASE = MODEL['cases']['preferred']
R, G, SHARES = .11555, .03, 5.51

quarters = [
    {'quarter': 1, 'Intel_AllOther_profit_M': 102, 'Mobileye_GAAP_operating_M': -3896,
     'Mobileye_amortization_M': 113, 'Mobileye_SBC_M': 84, 'Mobileye_acquisition_M': 6,
     'Mobileye_goodwill_impairment_M': 3788, 'Mobileye_RSU_grant_M': 0, 'Mobileye_adjusted_profit_M': 95},
    {'quarter': 2, 'Intel_AllOther_profit_M': 230, 'Mobileye_GAAP_operating_M': -30,
     'Mobileye_amortization_M': 114, 'Mobileye_SBC_M': 88, 'Mobileye_acquisition_M': 0,
     'Mobileye_goodwill_impairment_M': 0, 'Mobileye_RSU_grant_M': 17, 'Mobileye_adjusted_profit_M': 155},
    {'quarter': 3, 'Intel_AllOther_profit_M': 179, 'Mobileye_GAAP_operating_M': -82,
     'Mobileye_amortization_M': 69, 'Mobileye_SBC_M': 103, 'Mobileye_acquisition_M': 0,
     'Mobileye_goodwill_impairment_M': 0, 'Mobileye_RSU_grant_M': 1, 'Mobileye_adjusted_profit_M': 89},
]
for row in quarters:
    rebuilt = sum(row[key] for key in ['Mobileye_GAAP_operating_M', 'Mobileye_amortization_M', 'Mobileye_SBC_M', 'Mobileye_acquisition_M', 'Mobileye_goodwill_impairment_M'])
    assert rebuilt - row['Mobileye_RSU_grant_M'] == row['Mobileye_adjusted_profit_M']
    row['Mobileye_comparable_before_RSU_grant_removal_M'] = rebuilt
    row['residual_if_Intel_retains_RSU_grant_M'] = row['Intel_AllOther_profit_M'] - rebuilt
    row['residual_if_Intel_removes_RSU_grant_M'] = row['Intel_AllOther_profit_M'] - row['Mobileye_adjusted_profit_M']

controls = []
for annual_profit in POLICY['controls_annual_other_profit_B']:
    rows = []
    for key, original in BASE['annual_rows'].items():
        year = int(key)
        delta = (annual_profit - .7) * (1.03 ** max(year - 2030, 0))
        new_ebit = original['EBIT_B'] + delta
        new_tax = max(new_ebit, 0) * original['tax_rate']
        cash_delta = delta - (new_tax - original['ordinary_operating_tax_B'])
        rows.append({'year': year, 'profit_delta_B': delta, 'operating_cash_delta_B': cash_delta})
    treasury_delta = math.fsum(row['operating_cash_delta_B'] for row in rows if row['year'] <= 2030)
    endpoints = {}
    for endpoint in [2026, 2030]:
        pv = math.fsum(row['operating_cash_delta_B'] / (1 + R) ** (row['year'] - endpoint)
                       for row in rows if endpoint < row['year'] <= 2040)
        terminal_delta = next(row['operating_cash_delta_B'] for row in rows if row['year'] == 2041)
        pv += terminal_delta / (R - G) / (1 + R) ** (2040 - endpoint)
        equity_delta = pv + (treasury_delta if endpoint == 2030 else 0)
        endpoints[endpoint] = {'operating_PV_delta_B': pv,
                               'treasury_cash_delta_B': treasury_delta if endpoint == 2030 else 0,
                               'equity_delta_B': equity_delta, 'per_share_delta_USD': equity_delta / SHARES,
                               'share_value_USD': BASE['values'][str(endpoint)]['price_USD'] + equity_delta / SHARES}
    controls.append({'annual_2027_2030_Other_profit_B': annual_profit, 'annual_rows': rows, 'endpoints': endpoints})

ytd_low = sum(row['residual_if_Intel_retains_RSU_grant_M'] for row in quarters)
ytd_high = sum(row['residual_if_Intel_removes_RSU_grant_M'] for row in quarters)
output = {
    'calculated_utc': datetime.now(timezone.utc).isoformat(),
    'input_hashes': {'policy': hashlib.sha256(POLICY_PATH.read_bytes()).hexdigest(), 'root_results': MODEL_HASH},
    'sources': {
        'Intel_Q2': 'https://www.intc.com/filings-reports/all-sec-filings/content/0000050863-26-000157/intc-20260627.htm',
        'Intel_Q3': 'https://www.intc.com/filings-reports/all-sec-filings/content/0000050863-26-000191/intc-20260926.htm',
        'Mobileye_Q1': 'https://ir.mobileye.com/news-releases/news-release-details/mobileye-releases-first-quarter-2026-results-updates-full-year',
        'Mobileye_Q2': 'https://ir.mobileye.com/news-releases/news-release-details/mobileye-releases-second-quarter-2026-results-updates-guidance',
        'Mobileye_Q3': 'https://ir.mobileye.com/news-releases/news-release-details/mobileye-releases-third-quarter-2026-results-updates-guidance',
        'Mobileye_scope_caveat': 'https://ir.mobileye.com/node/9466/html',
    },
    'source_locator_for_scope': 'Mobileye Q3 10-Q MD&A subsection Intel Segment Reporting: parent results may differ because of corporate overhead and materiality thresholds.',
    'quarterly_reconciliation_M': quarters,
    'aggregate_controls_M': {
        'YTD_Intel_AllOther': 511, 'YTD_Intel_AllOther_annualized': 511 * 4 / 3,
        'Q3_Intel_AllOther_annualized': 179 * 4, 'forecast': 700,
        'YTD_residual_partial_treatment_interval': [ytd_low, ytd_high],
        'YTD_residual_annualized_partial_treatment_interval': [ytd_low * 4 / 3, ytd_high * 4 / 3],
        'Q3_residual_annualized_partial_treatment_interval': [89 * 4, 90 * 4],
        'forecast_residual': 300,
        'forecast_above_YTD_annualized_fraction_range': [300 / (ytd_high * 4 / 3) - 1, 300 / (ytd_low * 4 / 3) - 1],
    },
    'scope_assessment': [
        'Intel excludes corporate SBC, restructuring and certain acquisition-related amortization/impairment from operating segments. Mobileye adjusted profit removes similar categories, so GAAP Mobileye losses are not the correct direct subtraction.',
        'Mobileye also removes the RSU-related grant. Intel does not separately identify this grant treatment by segment. The interval spans that known mapping choice only; undisclosed overhead/materiality differences prevent a full matched-scope IMS profit reconstruction.',
        'The Austrian filed entity has a different scope and accounting framework and includes intercompany revenues. Its figures are not substituted for consolidated IMS.',
        'The 0.7B policy predates this research. It is an analyst forecast, not issuer guidance or newly selected factual profit. Aggregate run rates do not contradict it, but 0.3B non-Mobileye residual requires stronger performance than YTD.',
        'The 0.60/0.63/0.76B cases are unweighted operating-profit controls. Revenue, minority reserves, capital expenditure and grant WC allocation are held fixed; no double charge for SBC or receivable timing.'
    ],
    'controls': controls,
    'verification': {'all_Mobileye_GAAP_to_adjusted_reconciliations_exact_M': True,
                     'YTD_profit_matches': sum(row['Intel_AllOther_profit_M'] for row in quarters) == 511 and sum(row['Mobileye_adjusted_profit_M'] for row in quarters) == 339,
                     'base_control_unchanged': all(abs(value['per_share_delta_USD']) < 1e-12 for value in controls[2]['endpoints'].values()),
                     'root_input_unchanged': hashlib.sha256(MODEL_PATH.read_bytes()).hexdigest() == MODEL_HASH},
}
(OUT / 'other_profit_scope_and_controls.json').write_text(json.dumps(output, indent=2) + '\n')
print(json.dumps({'aggregate_controls_M': output['aggregate_controls_M'], 'controls': [{'annual_profit': row['annual_2027_2030_Other_profit_B'], 'endpoints': row['endpoints']} for row in controls], 'verification': output['verification']}, indent=2))

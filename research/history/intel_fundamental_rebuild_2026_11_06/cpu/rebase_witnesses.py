import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
OUT = Path(__file__).resolve().parent
SOURCE = ROOT / "work/three_hour/active_research/intel_two_hour_comparison_2026_11_05/economic_underwriting/prior_year_ASP_extension_results.json"
data = json.loads(SOURCE.read_text())
q4_revenue = 6.81206
unit_factor = 1.176
quarter_unit_indices = [1.0, 1.05, 1.155, 1.2705]
quarter_asp_indices = [1.0, 1.02, 1.0506, 1.082118]

results = []
witnesses = [
    ("low_Q3_ASP_original_endpoint", data["endpoint_extension_results"][0]),
    ("high_Q3_ASP_original_endpoint", data["endpoint_extension_results"][1]),
    ("original_strict_interior_witness", data["interior_20pct_carryover_witness"]),
]
for label, witness in witnesses:
    units = witness["units_2024_to_2026_normalized"]
    revenue = witness["CPU_revenue_2024_to_2026_B"]
    checks = []
    for yi, ug, ag in [
        (1, [0.16, 0.13, 0.0, 0.15, 0.10], [-0.10, -0.08, 0.0, -0.09, -0.06]),
        (2, [-0.05, 0.09, 0.10, 0.02, 0.04], [0.27, 0.48, 0.54, 0.38, 0.44]),
    ]:
        for gi, group in enumerate([[0], [1], [2], [0, 1], [0, 1, 2]]):
            uc = sum(units[yi][j] for j in group)
            up = sum(units[yi - 1][j] for j in group)
            rc = sum(revenue[yi][j] for j in group)
            rp = sum(revenue[yi - 1][j] for j in group)
            u_growth = uc / up - 1
            a_growth = (rc / uc) / (rp / up) - 1
            residual = max(abs(u_growth - ug[gi]) - 0.005, abs(a_growth - ag[gi]) - 0.005, 0)
            checks.append({"year": 2024 + yi, "quarters": [j + 1 for j in group], "unit_growth": u_growth, "ASP_growth": a_growth, "rounding_band_violation": residual})
    ytd_units = sum(units[2])
    q4_units = unit_factor * ytd_units / (sum(quarter_unit_indices) - unit_factor)
    q3_asp = revenue[2][2] / units[2][2]
    q4_asp = q4_revenue / q4_units
    annual_revenue = sum(revenue[2]) + q4_revenue
    annual_asp = annual_revenue / (ytd_units + q4_units)
    next_revenue = sum(q4_revenue * u * a for u, a in zip(quarter_unit_indices, quarter_asp_indices))
    next_units = q4_units * sum(quarter_unit_indices)
    results.append({
        "name": label,
        "historical_units": units,
        "historical_revenue_B": revenue,
        "q4_2026_units_over_q3": q4_units / units[2][2],
        "q4_2026_ASP_over_q3_minus1": q4_asp / q3_asp - 1,
        "q4_2026_ASP_over_reconstructed_FY2026_minus1": q4_asp / annual_asp - 1,
        "reconstructed_2026_CPU_revenue_B": annual_revenue,
        "2027_CPU_revenue_B": next_revenue,
        "2027_unit_growth": next_units / (ytd_units + q4_units) - 1,
        "2027_ASP_growth": (next_revenue / next_units) / annual_asp - 1,
        "historical_checks": checks,
        "max_rounding_band_violation": max(c["rounding_band_violation"] for c in checks),
    })

result = {
    "computed_utc": datetime.now(timezone.utc).isoformat(),
    "source_file": str(SOURCE),
    "source_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
    "novelty": "Rebase of existing Nov5 feasible witnesses to current Q4 CPU sales and current 2027 quarterly unit/ASP path. Identification method and historical witnesses are not new research.",
    "policy": {
        "new_forecast": False,
        "main_model_edited": False,
        "units_formula": "Q4units = 1.176 * YTD2026units / (sum(2027 quarterly indices) - 1.176).",
        "q4_CPU_revenue_B": q4_revenue,
        "2027_unit_factor": unit_factor,
        "quarter_unit_indices_relative_to_Q4_2026": quarter_unit_indices,
        "quarter_ASP_indices_relative_to_Q4_2026": quarter_asp_indices,
        "rounding_assumption": "Original closed +/-0.5 percentage-point bands for reported whole percentages, including analyst convention for 2025Q3 'roughly flat'. Endpoints are mathematical witnesses, not observations or probabilities.",
        "scope": "Conditional on server unit/ASP statistics covering the same population as DCAI less Other revenue. Matching terminology and segment comparatives support, but do not establish, identical scope.",
        "revenue_residual_boundary": "Witnesses use unrounded latent Q3Other consistent with published rounded values. Their reconstructed FY2026sales differ by $40-50M from the active model's $22.14406B annual anchor. Do not silently overwrite that anchor or claim exact21.9%ASP from these witnesses.",
    },
    "results": results,
    "conclusion": "Both falling and rising Q4 sequential ASP can reconcile the same current revenue forecast and17.6% annual unit growth. This validates mathematical possibility, not forecast likelihood, and cannot substantiate pricing power or justify a higher valuation.",
}
assert max(r["max_rounding_band_violation"] for r in results) < 1e-12
assert max(abs(r["2027_unit_growth"] - 0.176) for r in results) < 1e-12
(OUT / "current_witness_results.json").write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps({"results": [{k: v for k, v in r.items() if k in ["name", "q4_2026_units_over_q3", "q4_2026_ASP_over_q3_minus1", "2027_CPU_revenue_B", "2027_ASP_growth"]} for r in results], "max_violation": max(r["max_rounding_band_violation"] for r in results)}, indent=2))

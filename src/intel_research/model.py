import copy
import hashlib
import json
import math
from datetime import date
from pathlib import Path


SHARES_B = 5.51
TERMINAL_GROWTH = 0.03
CORE_RATE = 0.10625
HIGHER_RATE = 0.11555
NET_OTHER_ASSETS_B = 4.502
BUFFER_B = 20.0
FUNDING_RATE = 0.08
INPUT_NAMES = (
    "active_case", "decision_policy", "cpu_ramp", "host_policy",
    "packaging_policy", "quarterly_base", "quarterly_policy", "funding_policy",
)


def load_inputs(directory: Path) -> tuple[dict, dict]:
    inputs, hashes = {}, {}
    for name in INPUT_NAMES:
        path = directory / f"{name}.json"
        content = path.read_bytes()
        inputs[name] = json.loads(content)
        hashes[path.name] = hashlib.sha256(content).hexdigest()
    years = set(inputs["active_case"]["annual_rows"])
    if years != {str(y) for y in range(2027, 2042)}:
        raise ValueError("active_case must contain every annual row from 2027 through 2041")
    return inputs, hashes


def close_cash(row: dict) -> None:
    row["ordinary_operating_tax_B"] = max(row["EBIT_B"], 0) * row["tax_rate"]
    row["NOPAT_B"] = row["EBIT_B"] - row["ordinary_operating_tax_B"]
    row["net_operating_investment_B"] = row["physical_capex_B"] - row["DA_B"] + row["WC_cash_use_B"]
    row["parent_unlevered_cash_B"] = (
        row["NOPAT_B"] - row["net_operating_investment_B"]
        - row["lease_cash_B"] - row["minority_cash_B"]
        + row["old_credit_collection_B"] + row["new_credit_collection_B"]
        - row["credit_basis_loss_tax_B"]
    )


def cash_bridge(row: dict) -> dict:
    credits = row["old_credit_collection_B"] + row["new_credit_collection_B"] - row["credit_basis_loss_tax_B"]
    keys = ("EBIT_B", "ordinary_operating_tax_B", "NOPAT_B", "physical_capex_B", "DA_B",
            "WC_cash_use_B", "net_operating_investment_B")
    return {
        **{key: row[key] for key in keys},
        "lease_and_minority_cash_B": row["lease_cash_B"] + row["minority_cash_B"],
        "normalized_parent_operating_cash_B": row["parent_unlevered_cash_B"] - credits,
        "net_finite_credits_B": credits,
        "parent_unlevered_cash_B": row["parent_unlevered_cash_B"],
    }


def apv(rows: dict, active: dict, rate: float, endpoint: int) -> dict:
    base = active["annual_rows"]
    explicit = math.fsum(rows[y]["parent_unlevered_cash_B"] / (1 + rate) ** (y - endpoint)
                         for y in range(endpoint + 1, 2041))
    terminal = rows[2041]["parent_unlevered_cash_B"] / (rate - TERMINAL_GROWTH) / (1 + rate) ** (2040 - endpoint)
    shield = math.fsum(rows[y]["financing_shield_B"] / (1 + rate) ** (y - endpoint)
                       for y in range(endpoint + 1, 2041))
    # The inherited financing shield is level in perpetuity, unlike operating cash.
    shield += rows[2041]["financing_shield_B"] / rate / (1 + rate) ** (2040 - endpoint)
    cash = active["values"][str(endpoint)]["cash_B"]
    if endpoint == 2030:
        cash += math.fsum(rows[y]["parent_unlevered_cash_B"] - base[str(y)]["parent_unlevered_cash_B"]
                          for y in range(2027, 2031))
    debt = active["values"][str(endpoint)]["debt_B"]
    escrow = math.fsum(active["treasury"][str(y)]["escrow_cash_B"] / (1 + rate) ** (y - endpoint)
                       for y in range(endpoint + 1, 2031))
    acquisition = math.fsum(active["treasury"][str(y)]["Classiq_cash_B"] / (1 + rate) ** (y - endpoint)
                            for y in range(endpoint + 1, 2031))
    equity = explicit + terminal + shield + cash - debt + NET_OTHER_ASSETS_B + escrow - acquisition
    return {
        "explicit_operating_PV_B": explicit, "terminal_operating_PV_B": terminal,
        "total_operating_value_B": explicit + terminal, "financing_shield_PV_B": shield,
        "cash_B": cash, "debt_B": debt, "net_other_assets_B": NET_OTHER_ASSETS_B,
        "remaining_escrow_PV_B": escrow, "remaining_acquisition_PV_B": acquisition,
        "equity_B": equity, "price_USD": equity / SHARES_B,
        "terminal_share_of_operating_value": terminal / (explicit + terminal),
    }


def delay_path(cpu: dict, base: dict) -> tuple[list, dict]:
    q4 = cpu["owned_Q4"]["CPU_B"]
    quarters = [q4 * q["unit_index_Q4_2026_100"] / 100 * q["ASP_index_Q4_2026_100"] / 100
                for q in cpu["quarterly_2027"]]
    delayed = [quarters[0], *quarters[:3]]
    ratio = sum(delayed) / base[2027]["CPU_revenue_B"]
    annual = {y: base[y]["CPU_revenue_B"] * ratio for y in range(2027, 2041)}
    annual[2041] = annual[2040] * (1 + TERMINAL_GROWTH)
    return delayed, annual


def delivery_rows(base: dict, annual_cpu: dict, host: dict, packaging: dict) -> dict:
    rows = copy.deepcopy(base)
    previous_delta = 0.0
    for year, row in rows.items():
        row["CPU_revenue_B"] = annual_cpu[year]
        delta = row["CPU_revenue_B"] - base[year]["CPU_revenue_B"]
        for key in ("DCAI_revenue_B", "Products_revenue_B", "consolidated_revenue_B", "host_capital_revenue_B"):
            row[key] = base[year][key] + delta
        if year <= 2030:
            row["DCAI_profit_B"] = base[year]["DCAI_profit_B"] + 0.5 * delta
            row["CPU_margin"] = (row["DCAI_profit_B"] - row["Other_DCAI_B"] * row["Other_DCAI_margin"]) / row["CPU_revenue_B"]
            row["EBIT_B"] = base[year]["EBIT_B"] + 0.5 * delta
            row["WC_cash_use_B"] = base[year]["WC_cash_use_B"] + 0.1 * (delta - previous_delta)
            previous_delta = delta
        else:
            phase = min((year - 2030) / 10, 1)
            row["CPU_margin"] = rows[2030]["CPU_margin"] + phase * (base[2040]["CPU_margin"] - rows[2030]["CPU_margin"])
            row["DCAI_profit_B"] = row["CPU_revenue_B"] * row["CPU_margin"] + row["Other_DCAI_B"] * row["Other_DCAI_margin"]
            row["Foundry_profit_B"] = rows[2030]["Foundry_profit_B"] / rows[2030]["Products_revenue_B"] * row["Products_revenue_B"]
            row["EBIT_B"] = sum(row[k] for k in ("DCAI_profit_B", "CCPG_profit_B", "Foundry_profit_B", "net_packaging_profit_B", "Other_profit_less_corporate_B"))
            growth = row["host_capital_revenue_B"] - rows[year - 1]["host_capital_revenue_B"]
            row["DA_B"] = host[year]["DA_fraction_of_Products_revenue"] * row["Products_revenue_B"] + packaging[year]["incremental_DA_B"]
            row["WC_cash_use_B"] = 0.1 * growth + packaging[year]["incremental_WC_cash_use_B"]
            investment = growth / 0.8 + packaging[year]["incremental_net_operating_investment_B"]
            row["physical_capex_B"] = row["DA_B"] + investment - row["WC_cash_use_B"]
        row["DCAI_margin"] = row["DCAI_profit_B"] / row["DCAI_revenue_B"]
        close_cash(row)
    return rows


def joint(rows: dict, capital060: bool = False) -> dict:
    rows = copy.deepcopy(rows)
    for year, row in rows.items():
        profit = {2027: -4, 2028: -2.5, 2029: -1}.get(year, 0)
        row["EBIT_B"] += profit - row["Foundry_profit_B"]
        row["Foundry_profit_B"] = profit
        close_cash(row)
        if capital060 and 2031 <= year <= 2040:
            growth = row["host_capital_revenue_B"] - rows[year - 1]["host_capital_revenue_B"]
            row["physical_capex_B"] += growth * (1 / 0.6 - 1 / 0.8)
            close_cash(row)
    row = rows[2041]
    row["physical_capex_B"] += TERMINAL_GROWTH * row["NOPAT_B"] / 0.15 - row["net_operating_investment_B"]
    close_cash(row)
    return rows


def quarterly_cash(annual: dict, inputs: dict, delayed_quarters: list | None) -> dict:
    active = inputs["active_case"]
    source = inputs["quarterly_base"]["concentrated_timing_stress"]["quarterly_rows"]
    weights = inputs["quarterly_policy"]["investment"]["WC_cash_use_weights"]
    cash = active["values"]["2026"]["cash_B"]
    result, errors = [], []
    for year in range(2027, 2031):
        rows = copy.deepcopy([r for r in source if r["year"] == year])
        if len(rows) != 4 or [r["quarter"] for r in rows] != [1, 2, 3, 4]:
            raise ValueError(f"Expected four ordered quarters for {year}")
        for i, row in enumerate(rows):
            old_cpu = row["CPU_revenue_B"]
            if delayed_quarters is not None:
                row["CPU_revenue_B"] = delayed_quarters[i] if year == 2027 else annual[year]["CPU_revenue_B"] * [0.23, 0.24, 0.26, 0.27][i]
                row.pop("CPU_unit_index", None)
                row.pop("CPU_ASP_index", None)
            cpu_delta = row["CPU_revenue_B"] - old_cpu
            foundry_delta = (annual[year]["Foundry_profit_B"] - active["annual_rows"][str(year)]["Foundry_profit_B"]) / 4
            for key in ("DCAI_revenue_B", "Products_revenue_B", "consolidated_revenue_B"):
                row[key] += cpu_delta
            row["DCAI_profit_B"] += 0.5 * cpu_delta
            row["Foundry_profit_B"] += foundry_delta
            row["EBIT_B"] += 0.5 * cpu_delta + foundry_delta
        positive = sum(max(r["EBIT_B"], 0) for r in rows)
        for i, row in enumerate(rows):
            a = annual[year]
            row["ordinary_operating_tax_B"] = a["ordinary_operating_tax_B"] * max(row["EBIT_B"], 0) / positive if positive else 0
            row["WC_cash_use_B"] = a["WC_cash_use_B"] * weights[i]
            row["net_operating_investment_B"] = row["physical_capex_B"] - row["DA_B"] + row["WC_cash_use_B"]
            row["parent_unlevered_cash_B"] = (row["EBIT_B"] - row["ordinary_operating_tax_B"] - row["net_operating_investment_B"]
                - row["lease_cash_B"] - row["minority_cash_B"] + row["old_credit_collection_B"]
                + row["new_credit_collection_B"] - row["credit_basis_loss_tax_B"])
            row["owner_cash_B"] = (row["parent_unlevered_cash_B"] - row["ordinary_interest_B"] - row["capitalized_interest_B"]
                + row["cash_income_B"] * (1 - a["tax_rate"]) + row["financing_shield_B"])
            row["opening_cash_B"] = cash
            cash += row["owner_cash_B"] + row["escrow_cash_B"] - row["Classiq_cash_B"] - row["principal_B"]
            row["ending_cash_B"] = cash
        for key in ("CPU_revenue_B", "consolidated_revenue_B", "DCAI_profit_B", "Foundry_profit_B", "EBIT_B",
                    "ordinary_operating_tax_B", "WC_cash_use_B", "physical_capex_B", "parent_unlevered_cash_B"):
            errors.append(abs(sum(r[key] for r in rows) - annual[year][key]))
        expected_cash = active["treasury"][str(year)]["ending_cash_B"] + sum(
            annual[y]["parent_unlevered_cash_B"] - active["annual_rows"][str(y)]["parent_unlevered_cash_B"] for y in range(2027, year + 1))
        errors.append(abs(cash - expected_cash))
        result.extend(rows)
    minimum = min(result, key=lambda r: r["ending_cash_B"])
    return {
        "minimum_quarter_cash_B": minimum["ending_cash_B"], "minimum_period": period_name(minimum),
        "headroom_above_assumed20B_buffer_B": minimum["ending_cash_B"] - BUFFER_B,
        "buffer_shortfall_B": max(BUFFER_B - minimum["ending_cash_B"], 0),
        "quarters_below20B": [period_name(r) for r in result if r["ending_cash_B"] < BUFFER_B],
        "annual_reconciliation_max_error_B": max(errors), "quarterly_rows": result,
    }


def period_name(row: dict) -> str:
    return f"Q{row['quarter']} {row['year']}"


def funded_case(quarterly: list, policy: dict) -> dict:
    debt, financing_cash, pretax_npv = 0.0, 0.0, 0.0
    quarter_rate = FUNDING_RATE / 4
    rows = []
    for period, original in enumerate(quarterly, 1):
        opening_debt = debt
        cash_before = original["ending_cash_B"] + financing_cash
        draw = max((BUFFER_B - cash_before + opening_debt * quarter_rate) / (1 - quarter_rate), 0)
        debt += draw
        interest = debt * quarter_rate
        repayment = min(max(cash_before + draw - interest - BUFFER_B, 0), debt)
        debt -= repayment
        financing_cash += draw - repayment - interest
        pretax_npv += draw / (1 + quarter_rate) ** (period - 1) - (interest + repayment) / (1 + quarter_rate) ** period
        rows.append({
            "year": original["year"], "quarter": original["quarter"], "no_draw_cash_B": original["ending_cash_B"],
            "opening_revolver_B": opening_debt, "start_quarter_draw_B": draw,
            "full_quarter_interest_B": interest, "conditional_cash_tax_benefit_B": 0.0,
            "end_quarter_repayment_B": repayment, "end_quarter_revolver_B": debt,
            "end_quarter_cash_B": original["ending_cash_B"] + financing_cash,
            "net_cash_minus_revolver_delta_B": financing_cash - debt,
        })
    used = [r for r in rows if r["start_quarter_draw_B"] > 1e-10 or r["opening_revolver_B"] > 1e-10]
    peak = max(r["opening_revolver_B"] + r["start_quarter_draw_B"] for r in rows)
    facts = policy["facility_facts"]
    first_maturity = min(facts["three_year_maturity"], facts["five_year_maturity"])
    repaid_before = not used or (debt < 1e-10 and f"{used[-1]['year']}-{used[-1]['quarter'] * 3:02d}" < first_maturity)
    interest = sum(r["full_quarter_interest_B"] for r in rows)
    return {
        "annual_simple_rate": FUNDING_RATE, "immediate_cash_tax_benefit_fraction": 0,
        "minimum_funded_quarter_cash_B": min(r["end_quarter_cash_B"] for r in rows),
        "peak_revolver_B": peak, "peak_share_of_total15B_capacity": peak / facts["total_capacity_B"],
        "peak_share_of_smaller5B_facility": peak / facts["three_year_capacity_B"],
        "first_draw_period": period_name(used[0]) if used else None,
        "fully_repaid_period": period_name(used[-1]) if used and debt < 1e-10 else None,
        "fully_repaid_before_both_disclosed_maturities": repaid_before,
        "total_gross_interest_B": interest, "total_conditional_cash_tax_benefit_B": 0.0,
        "total_after_tax_interest_B": interest, "ending_revolver_2030_B": debt,
        "Dec2030_equity_value_delta_B": financing_cash - debt,
        "Dec2030_per_share_delta_USD": (financing_cash - debt) / SHARES_B,
        "paired_pretax_financing_NPV_at_assumed_loan_rate_B": pretax_npv,
        "conditional_tax_shield_NPV_at_assumed_loan_rate_B": 0.0,
        "conditional_tax_shield_per_share_USD": 0.0,
        "headline_Dec2026_planning_adjustment_credited_USD": 0,
        "quarterly_rows": rows,
    }


def mix_controls(cpu: dict, base: dict) -> dict:
    q4 = cpu["owned_Q4"]["CPU_B"]
    fy26 = cpu["runrate_bridge"]["FY2026E_CPU_B"]
    units = [q["unit_index_Q4_2026_100"] / 100 for q in cpu["quarterly_2027"]]
    asps = [q["ASP_index_Q4_2026_100"] / 100 for q in cpu["quarterly_2027"]]
    quarterly_revenue = [q4 * unit * asp for unit, asp in zip(units, asps)]
    revenue27 = sum(quarterly_revenue)
    flat = q4 * sum(units)
    weighted_asp = revenue27 / flat
    unit_factor = 1.4 * 0.42 / 0.50
    annual_asp = revenue27 / fy26 / unit_factor
    exit_premium = annual_asp / weighted_asp - 1
    q4_27 = quarterly_revenue[-1]
    revenue28 = base[2028]["CPU_revenue_B"]
    unit_carry = 4 * units[-1] / sum(units) - 1
    asp_carry = asps[-1] / weighted_asp - 1
    q3 = cpu["actual"]["Q3_DCAI_B"] - cpu["actual"]["Q3_OtherDCAI_rounded_B"]
    # Frozen consensus observations used by the original mix control, in $B.
    consensus = {2027: 69.267, 2028: 83.719}

    def company_control(cpu27: float) -> dict:
        result = {}
        for year, revenue in ((2027, cpu27), (2028, cpu27 * 1.25 * 1.08)):
            company = base[year]["consolidated_revenue_B"] - base[year]["CPU_revenue_B"] + revenue
            result[f"FY{year}_CPU_B"] = revenue
            result[f"FY{year}_company_B"] = company
            result[f"FY{year}_company_beat"] = company / consensus[year] - 1
        return result

    return {
        "assumptions": {"FY2027_unit_growth": unit_factor - 1, "FY2028_unit_growth": 0.25,
            "FY2028_ASP_growth": 0.08, "frozen_consensus_company_revenue_B": consensus,
            "status": "Conditional arithmetic controls; estimated Q4 exit and unit/mix paths are not observations. No profit or valuation extrapolation."},
        "forecast_2027_bridge_B": {
            "FY2026E_CPU": fy26, "carry_2026_Q4_runrate_into_2027": 4 * q4 - fy26,
            "incremental_units_at_Q4_2026_ASP": flat - 4 * q4,
            "incremental_2027_ASP_at_forecast_units": revenue27 - flat, "FY2027E_CPU": revenue27,
        },
        "actual_runrate_check": {
            "Q3_2026_CPU_residual_B": q3, "Q3_2026_annualized_B": 4 * q3,
            "owned_2027_lift_over_actual_Q3_runrate": revenue27 / (4 * q3) - 1,
            "Q4_2026_owned_lift_over_Q3": q4 / q3 - 1,
        },
        "price_level_identity": {
            "implied_Q4_2026_ASP_over_FY2026_average": exit_premium,
            "core_2027_weighted_ASP_over_Q4_2026": weighted_asp - 1,
            "10pct_annual_ASP_counterexample_weighted_ASP_over_Q4": 1.1 / (1 + exit_premium) - 1,
        },
        "flat_exit_ASP_control": company_control(flat),
        "10pct_annual_ASP_counterexample": company_control(fy26 * unit_factor * 1.1),
        "forecast_2028_bridge": {
            "Q4_2027_CPU_B": q4_27, "Q4_2027_annualized_CPU_B": 4 * q4_27,
            "FY2028_CPU_B": revenue28, "carryover_from_2027_annual_to_flat_exit_B": 4 * q4_27 - revenue27,
            "further_revenue_above_flat_exit_B": revenue28 - 4 * q4_27,
            "FY2028_lift_over_Q4_2027_annualized": revenue28 / (4 * q4_27) - 1,
            "unit_carry_if_all_2028_quarters_equal_Q4_2027": unit_carry,
            "ASP_carry_if_all_2028_quarters_equal_Q4_2027": asp_carry,
            "required_2028_average_units_above_Q4_2027": 1.25 / (1 + unit_carry) - 1,
            "required_2028_average_ASP_above_Q4_2027": 1.08 / (1 + asp_carry) - 1,
        },
    }


def calculate(inputs: dict, hashes: dict) -> dict:
    active = inputs["active_case"]
    policy = inputs["decision_policy"]
    base = {int(y): copy.deepcopy(row) for y, row in sorted(active["annual_rows"].items())}
    for row in base.values():
        close_cash(row)
    host = {r["year"]: r for r in inputs["host_policy"]["annual_rows"]}
    packaging = {r["year"]: r for r in inputs["packaging_policy"]["annual_rows"]}
    delayed_quarters, annual_cpu = delay_path(inputs["cpu_ramp"], base)
    delayed = delivery_rows(base, annual_cpu, host, packaging)
    cases = {"core": base, "selected_joint": joint(base), "joint_plus_CPU_delay": joint(delayed),
             "joint_plus_CPU_delay_plus_2031_2040_capital060": joint(delayed, True)}
    start = date.fromisoformat(policy["new_reference_date"])
    end = date.fromisoformat(policy["target_date"])
    horizon = (end - start).days / 365.25
    quote = policy["new_reference_price_USD"]
    entry = policy["selected_entry_rule"]["round_down_to_USD"]
    results = {}
    for name, rows in cases.items():
        value = apv(rows, active, HIGHER_RATE, 2030)
        quarters = quarterly_cash(rows, inputs, delayed_quarters if name.startswith("joint_plus_CPU") else None)
        funding = funded_case(quarters["quarterly_rows"], inputs["funding_policy"])
        target = value["price_USD"] + funding["Dec2030_per_share_delta_USD"]
        bridge = {str(y): cash_bridge(row) for y, row in rows.items()}
        results[name] = {
            "APV_at11_555pct": {
                "explicit_operating_PV_B": value["explicit_operating_PV_B"], "terminal_operating_PV_B": value["terminal_operating_PV_B"],
                "financing_shield_PV_B": value["financing_shield_PV_B"], "cash_B_before_new_funding": value["cash_B"],
                "debt_B_before_new_funding": value["debt_B"], "net_other_assets_B": value["net_other_assets_B"],
                "equity_B_before_new_funding": value["equity_B"], "target_USD_before_new_funding": value["price_USD"],
            },
            "funded_target_USD": target, "funded_annual_return_at40": (target / entry) ** (1 / horizon) - 1,
            "funded_annual_return_at56_28": (target / quote) ** (1 / horizon) - 1,
            "diagnostic_entry12_not_adopted_USD": target / 1.12 ** horizon,
            "cash_bridge": bridge,
            "cumulative_2027_2030_cash_bridge": {k: math.fsum(bridge[str(y)][k] for y in range(2027, 2031)) for k in bridge["2027"]},
            "cash2030_after_new_funding_B": value["cash_B"] + funding["Dec2030_equity_value_delta_B"],
            "operating_quarter_cash_before_funding": {k: v for k, v in quarters.items() if k != "quarterly_rows"},
            "operating_quarterly_rows": quarters["quarterly_rows"], "funding": funding,
            "2031_2040_net_investment_B": math.fsum(rows[y]["net_operating_investment_B"] for y in range(2031, 2041)),
        }
    valuations = {label: {str(y): apv(base, active, rate, y) for y in (2026, 2030)}
                  for label, rate in (("10.625pct", CORE_RATE), ("11.555pct", HIGHER_RATE))}
    entry_rule = policy["selected_entry_rule"]
    ceiling_core = valuations["11.555pct"]["2030"]["price_USD"] / (1 + entry_rule["higher_rate_core_return_hurdle"]) ** horizon
    ceiling_joint = results["selected_joint"]["funded_target_USD"] / (1 + entry_rule["selected_joint_stress_return_hurdle"]) ** horizon
    reconstructed = delivery_rows(base, {y: r["CPU_revenue_B"] for y, r in base.items()}, host, packaging)
    return {
        "scope": "Recompute cash, APV, inherited controls and funding from frozen annual operating forecasts. Does not regenerate forecasts from filings or fetch live data.",
        "input_sha256": hashes, "horizon_years": horizon,
        "assumptions": {"shares_B": SHARES_B, "terminal_growth": TERMINAL_GROWTH,
            "core_asset_rate": CORE_RATE, "higher_asset_rate": HIGHER_RATE, "net_other_assets_B": NET_OTHER_ASSETS_B,
            "funding_rate": FUNDING_RATE, "funding_cash_tax_benefit": 0, "quarter_end_cash_buffer_B": BUFFER_B,
            "joint_terminal_return_on_modeled_net_investment": 0.15,
            "capital_control_incremental_sales_to_net_investment_2031_2040": 0.6},
        "valuation": valuations, "cases": results,
        "decision": {
            "reference_date": start.isoformat(), "reference_price_USD": quote, "target_date": end.isoformat(),
            "annual_return_current_core": (valuations["10.625pct"]["2030"]["price_USD"] / quote) ** (1 / horizon) - 1,
            "annual_return_current_higher_rate": (valuations["11.555pct"]["2030"]["price_USD"] / quote) ** (1 / horizon) - 1,
            "higher_rate_core_entry_ceiling_USD": ceiling_core,
            "selected_funded_joint_entry_ceiling_USD": ceiling_joint,
            "adopted_entry_USD": entry, "entry_meets_selected_hurdles": entry <= min(ceiling_core, ceiling_joint),
            "current_quote_meets_entry_rule": quote <= entry,
        },
        "cpu_delay": {"quarterly_2027_B": delayed_quarters, "annual_CPU_B": annual_cpu,
            "persistent_level_loss": 1 - annual_cpu[2027] / base[2027]["CPU_revenue_B"]},
        "mix": mix_controls(inputs["cpu_ramp"], base),
        "reconciliation": {
            "zero_delay_cash_max_error_B": max(abs(reconstructed[y]["parent_unlevered_cash_B"] - r["parent_unlevered_cash_B"]) for y, r in base.items()),
            "base_cash_recalculation_max_error_B": max(abs(r["parent_unlevered_cash_B"] - active["annual_rows"][str(y)]["parent_unlevered_cash_B"]) for y, r in base.items()),
            "annual_quarter_max_error_B": max(r["operating_quarter_cash_before_funding"]["annual_reconciliation_max_error_B"] for r in results.values()),
        },
        "limitations": [
            "Selected forecasts and sensitivities are not guidance, measured probabilities or evidence of future execution.",
            "The estimated Q4 CPU exit and unit/mix paths remain assumptions; the pricing control does not value a new forecast.",
            "Future facility access and costs remain conditional. Fees and daily liquidity are not modeled; baseline cash income remains fixed.",
            "R&D remains expensed. Terminal return on modeled net investment is not fully capitalized economic ROIC.",
            "Planning values use December endpoints; entry returns use the recorded November 6 quote and date. No winning probability is estimated.",
        ],
    }

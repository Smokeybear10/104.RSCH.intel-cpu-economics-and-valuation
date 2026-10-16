import argparse
import csv
import json
import math
import sys
from pathlib import Path

from .model import calculate, load_inputs


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def write_analysis(output: Path, analysis: dict) -> None:
    output.mkdir(parents=True, exist_ok=True)
    write_json(output / "analysis.json", analysis)
    first_bridge = analysis["cases"]["core"]["cash_bridge"]["2027"]
    with (output / "annual_cash.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=["case", "year", *first_bridge])
        writer.writeheader()
        for name, case in analysis["cases"].items():
            for year, row in case["cash_bridge"].items():
                writer.writerow({"case": name, "year": year, **row})


def verify(analysis: dict, inputs: dict, directory: Path) -> dict:
    expected = json.loads((directory / "expected_results.json").read_text())
    expected_mix = json.loads((directory / "expected_mix_results.json").read_text())
    failures, count = [], 0

    def compare(actual: object, reference: object, path: str) -> None:
        nonlocal count
        if isinstance(reference, dict):
            if not isinstance(actual, dict):
                failures.append({"path": path, "error": "expected an object"})
                return
            for key, value in reference.items():
                if key not in actual:
                    failures.append({"path": f"{path}.{key}", "error": "missing result"})
                else:
                    compare(actual[key], value, f"{path}.{key}")
            return
        if isinstance(reference, list):
            if not isinstance(actual, list) or len(actual) != len(reference):
                failures.append({"path": path, "error": "list length or type differs"})
                return
            for index, (left, right) in enumerate(zip(actual, reference)):
                compare(left, right, f"{path}[{index}]")
            return
        count += 1
        if isinstance(reference, (int, float)) and not isinstance(reference, bool):
            matches = (isinstance(actual, (int, float)) and not isinstance(actual, bool)
                       and math.isfinite(actual) and math.isclose(actual, reference, rel_tol=1e-10, abs_tol=1e-8))
        else:
            matches = actual == reference
        if not matches:
            failures.append({"path": path, "actual": actual, "expected": reference})

    compare(analysis["horizon_years"], expected["horizon_years"], "horizon_years")
    compare(analysis["cases"], expected["cases"], "cases")
    compare(analysis["valuation"]["10.625pct"], inputs["active_case"]["values"], "core_APV")
    decision = inputs["decision_policy"]
    for key in ("annual_return_current_core", "annual_return_current_higher_rate"):
        compare(analysis["decision"][key], decision[key], f"decision.{key}")
    for key in ("higher_rate_core_entry_ceiling_USD", "selected_funded_joint_entry_ceiling_USD"):
        compare(analysis["decision"][key], decision["selected_entry_rule"][key], f"decision.{key}")
    for key in ("quarterly_2027_B", "persistent_level_loss"):
        compare(analysis["cpu_delay"][key], inputs["cpu_ramp"]["delay_no_catchup"][key], f"cpu_delay.{key}")
    compare({str(y): v for y, v in analysis["cpu_delay"]["annual_CPU_B"].items()},
            inputs["cpu_ramp"]["delay_no_catchup"]["annual_CPU_B"], "cpu_delay.annual_CPU_B")
    excluded = {"qualification", "definition", "classification", "Q3_2026_residual_lift_over_Q2"}
    for section, reference in expected_mix.items():
        if section == "basis":
            continue
        compare(analysis["mix"][section], {k: v for k, v in reference.items() if k not in excluded}, f"mix.{section}")
    for key, error in analysis["reconciliation"].items():
        compare(error, 0, f"reconciliation.{key}")
    for name, case in analysis["cases"].items():
        for year, row in case["cash_bridge"].items():
            residual = row["NOPAT_B"] - row["net_operating_investment_B"] - row["lease_and_minority_cash_B"] - row["normalized_parent_operating_cash_B"]
            compare(residual, 0, f"identities.{name}.{year}.cash_bridge")
        funding = case["funding"]
        compare(funding["Dec2030_equity_value_delta_B"] + funding["total_after_tax_interest_B"], 0, f"identities.{name}.funding_net_claim")
        compare(funding["ending_revolver_2030_B"], 0, f"identities.{name}.funding_repaid")
        compare(funding["paired_pretax_financing_NPV_at_assumed_loan_rate_B"], 0, f"identities.{name}.financing_NPV")
        compare(funding["minimum_funded_quarter_cash_B"] >= 20 - 1e-8, True, f"identities.{name}.buffer_restored")
        compare(funding["peak_revolver_B"] <= inputs["funding_policy"]["facility_facts"]["three_year_capacity_B"], True, f"identities.{name}.smaller_facility_capacity")
    compare(analysis["cases"]["joint_plus_CPU_delay"]["funding"],
            analysis["cases"]["joint_plus_CPU_delay_plus_2031_2040_capital060"]["funding"], "identities.same_pre2031_funding")
    return {
        "passed": not failures, "checks": count, "failures": failures,
        "absolute_tolerance": 1e-8, "relative_tolerance": 1e-10,
        "scope": "Frozen output regression and cash/financing identities; not empirical validation of forecasts or a live data audit.",
        "mix_exclusions": ["Text annotations", "Q3-over-Q2 residual comparison: Q2 observation is outside these runtime inputs"],
        "input_sha256": analysis["input_sha256"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Recompute the frozen Intel research model without network access.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command, help_text in (("reproduce", "write recalculated valuation, cash and mix controls"),
                               ("verify", "recalculate and compare frozen results and cash identities")):
        sub = subparsers.add_parser(command, help=help_text)
        sub.add_argument("--data", type=Path, default=Path("data"), help="input JSON directory (default: data)")
        sub.add_argument("--output", type=Path, default=Path("results"), help="output directory (default: results)")
    args = parser.parse_args()
    try:
        inputs, hashes = load_inputs(args.data)
        analysis = calculate(inputs, hashes)
        if args.command == "verify":
            result = verify(analysis, inputs, args.data)
            args.output.mkdir(parents=True, exist_ok=True)
            write_json(args.output / "verification.json", result)
            status = "PASS" if result["passed"] else "FAIL"
            print(f"{status}: {result['checks']} comparisons; {len(result['failures'])} failures. {args.output / 'verification.json'}")
            for failure in result["failures"][:10]:
                print(json.dumps(failure))
            return 0 if result["passed"] else 1
        write_analysis(args.output, analysis)
    except (OSError, ValueError, KeyError) as error:
        print(f"Cannot {args.command}: {error}", file=sys.stderr)
        return 2
    print(f"Wrote {args.output / 'analysis.json'} and {args.output / 'annual_cash.csv'}")
    print(f"Frozen reference: ${analysis['decision']['reference_price_USD']:.2f} on {analysis['decision']['reference_date']}; conditional entry ${analysis['decision']['adopted_entry_USD']:.0f}.")
    print("Scenario targets below use the 11.555% asset rate. The 10.625% headline valuation is separately recorded in analysis.json.")
    for name, case in analysis["cases"].items():
        print(f"{name}: funded 2030 target ${case['funded_target_USD']:.2f}; return at $40 {case['funded_annual_return_at40']:.2%}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

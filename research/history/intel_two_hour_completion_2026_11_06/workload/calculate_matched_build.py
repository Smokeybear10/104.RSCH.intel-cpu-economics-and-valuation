import calendar
import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median

BASE = Path(__file__).resolve().parent
SOURCES = BASE / "sources"
RUNNERS = {
    "runson-m8i-large": "m8i.large",
    "runson-m8i-xlarge": "m8i.xlarge",
    "runson-m8i-2xlarge": "m8i.2xlarge",
    "runson-m8a-large": "m8a.large",
    "runson-m8a-x64": "m8a.xlarge",
    "runson-m8a-2xlarge": "m8a.2xlarge",
    "runson-m9g-large": "m9g.large",
    "runson-m9g-arm64": "m9g.xlarge",
    "runson-m9g-arm64-8x32": "m9g.2xlarge",
}
PRIMARY = {"m8i.2xlarge", "m8a.2xlarge"}
prices = json.loads((SOURCES / "aws_ec2_prices.json").read_text())
price_rows = {
    row["Instance Type"]: row
    for row in prices["regions"]["US East (N. Virginia)"].values()
    if row["Instance Type"] in RUNNERS.values()
}
assert len(price_rows) == len(RUNNERS)
records = []
checks = []
quality_checks = []

for file in sorted(SOURCES.glob("results__rust__*.json")):
    raw = json.loads(file.read_text())
    configs = {row["id"]: row for row in raw["runners"]}
    assert raw["workload"]["ref"] == "7dc9d17a7bf5671eb6129fdf9127729f659637fc"
    assert raw["workload"]["toolchain"] == "rust 1.98.1"
    date = raw["run"]["date"]
    month_hours = calendar.monthrange(int(date[:4]), int(date[5:7]))[1] * 24
    for result in raw["results"]:
        runner = result["runnerId"]
        if runner not in RUNNERS:
            continue
        instance = RUNNERS[runner]
        config = configs[runner]
        host = result["host"]
        cost = result.get("cost", {})
        assert host["ec2"]["instanceType"] == instance
        assert host["ec2"]["region"] == "us-east-1"
        assert config["storage"] == "ebs"
        assert config["vcpu"] == int(price_rows[instance]["vCPU"])
        assert config["ramGiB"] == int(price_rows[instance]["Memory"].split()[0])
        assert cost.get("billedSeconds") is not None
        assert cost.get("ebsHourlyUsd") is not None
        assert abs(cost["ebsHourlyUsd"] - 13.4 / 730) < 0.000001
        assert result["workloadSeconds"] == sum(p["seconds"] for p in result["phases"])
        price = float(price_rows[instance]["price"])
        seconds = cost["billedSeconds"]
        reconstructed_recorded = seconds / 3600 * (cost["ec2HourlyUsd"] + cost["ebsHourlyUsd"])
        assert abs(reconstructed_recorded - cost["usd"]) < 0.00002
        success = result["status"] == "success" and all(p["status"] == "success" for p in result["phases"])
        job_id = int(result["jobUrl"].split("/")[-1])
        log_file = SOURCES / f"github_job_{job_id}.log"
        log = log_file.read_text() if log_file.exists() else None
        passed = re.search(r"test result: ok\. (\d+) passed; (\d+) failed", log or "")
        log_billed = re.search(r"Billed duration\s*\|\s*(\d+)m(\d+)s", log or "")
        log_seconds = int(log_billed[1]) * 60 + int(log_billed[2]) if log_billed else None
        if instance in PRIMARY:
            assert passed and int(passed[1]) == 45 and int(passed[2]) == 0
            assert success
            clean_log = re.sub(r"\x1b\[[0-9;]*m", "", log)
            test_names = sorted(re.findall(r"Z test (.+?) \.\.\. ok", clean_log))
            crates = sorted(set(re.findall(r"Compiling\s+(\S+)\s+(v[^\s]+)", clean_log)))
            assert len(test_names) == 45
            assert raw["workload"]["ref"] in clean_log and "1.98.1" in clean_log
            quality_checks.append({
                "job_id": job_id, "instance": instance, "date": date,
                "test_names": test_names, "test_names_count": len(test_names),
                "test_name_set_SHA256": hashlib.sha256("\n".join(test_names).encode()).hexdigest(),
                "observed_compiled_crate_versions": crates,
                "observed_compiled_crate_version_count": len(crates),
                "observed_compiled_crate_set_SHA256": hashlib.sha256(json.dumps(crates).encode()).hexdigest(),
                "pinned_workload_hash_and_toolchain_seen_in_log": True,
            })
        calendar_ebs = 13.4 / month_hours
        row = {
            "date": date,
            "run_id": raw["run"]["id"],
            "harness_commit": raw["run"]["sha"],
            "runner_id": runner,
            "instance": instance,
            "vCPU": config["vcpu"],
            "RAM_GiB": config["ramGiB"],
            "cpu_model": host["cpu"]["model"],
            "threads_per_core": host["cpu"]["threadsPerCore"],
            "implied_physical_cores": config["vcpu"] / host["cpu"]["threadsPerCore"],
            "os": host["os"],
            "kernel": host["kernel"],
            "AMI": host["ec2"]["amiId"],
            "zone": host["ec2"]["availabilityZone"],
            "lifecycle": host["ec2"]["lifecycle"],
            "status": result["status"],
            "success": success,
            "job_url": result["jobUrl"],
            "job_seconds": result["jobSeconds"],
            "workload_seconds": result["workloadSeconds"],
            "queue_seconds": result["queueSeconds"],
            "queue_plus_job_seconds": result["queueSeconds"] + result["jobSeconds"],
            "control_plane_estimated_billed_seconds": seconds,
            "job_log_estimated_billed_seconds_with_shutdown_allowance": log_seconds,
            "tests_passed_in_direct_log": int(passed[1]) if passed else None,
            "tests_failed_in_direct_log": int(passed[2]) if passed else None,
            "phase_statuses": {p["name"]: p["status"] for p in result["phases"]},
            "raw_reported_cost": cost,
            "current_on_demand_compute_USD_hour": price,
            "recomputed_recorded_EC2_EBS_USD": reconstructed_recorded,
            "normalized_on_demand_EC2_EBS_USD": seconds / 3600 * (price + cost["ebsHourlyUsd"]),
            "scenario_one_IPv4_calendar_EBS_USD": seconds / 3600 * (price + calendar_ebs + 0.005),
            "scenario_job_log_window_one_IPv4_calendar_EBS_USD": log_seconds / 3600 * (price + calendar_ebs + 0.005) if log_seconds else None,
            "source_file": file.name,
        }
        records.append(row)
    pair = [row for row in records if row["date"] == date and row["instance"] in PRIMARY]
    assert len(pair) == 2
    matched = {field: len({row[field] for row in pair}) == 1 for field in ["vCPU", "RAM_GiB", "os", "kernel", "AMI", "harness_commit"]}
    assert all(matched.values())
    checks.append({"date": date, "matched_fields": matched, "same_zone": pair[0]["zone"] == pair[1]["zone"]})

assert len(quality_checks) == 10
assert len({q["test_name_set_SHA256"] for q in quality_checks}) == 1
assert len({q["observed_compiled_crate_set_SHA256"] for q in quality_checks}) == 1
quality_output = {
    "checked_utc": datetime.now(timezone.utc).isoformat(),
    "all_ten_logs_identical_45_test_names": True,
    "all_ten_logs_pinned_source_and_toolchain_seen": True,
    "observed_compile_set_matches_all_ten": True,
    "checks": quality_checks,
    "limits": "Textual execution checks; no produced executable hash, full OS package lock or independent workload rerun.",
}
(BASE / "quality_verification.json").write_text(json.dumps(quality_output, indent=2) + "\n")

summaries = {}
for instance in RUNNERS.values():
    rows = [row for row in records if row["instance"] == instance]
    successful = [row for row in rows if row["success"]]
    assert len(rows) == 5
    summaries[instance] = {
        "observed_jobs": len(rows),
        "successful_jobs": len(successful),
        "failures": [{"date": r["date"], "job_url": r["job_url"], "status": r["status"]} for r in rows if not r["success"]],
        "lifecycles": dict(Counter(row["lifecycle"] for row in rows)),
        "vCPU": rows[0]["vCPU"],
        "RAM_GiB": rows[0]["RAM_GiB"],
        "implied_physical_cores": rows[0]["implied_physical_cores"],
        "job_seconds": {"median": median(r["job_seconds"] for r in successful), "min": min(r["job_seconds"] for r in successful), "max": max(r["job_seconds"] for r in successful)},
        "workload_seconds": {"median": median(r["workload_seconds"] for r in successful), "min": min(r["workload_seconds"] for r in successful), "max": max(r["workload_seconds"] for r in successful)},
        "queue_plus_job_seconds": {"median": median(r["queue_plus_job_seconds"] for r in successful), "min": min(r["queue_plus_job_seconds"] for r in successful), "max": max(r["queue_plus_job_seconds"] for r in successful)},
        "mean_control_plane_billed_seconds": mean(r["control_plane_estimated_billed_seconds"] for r in rows),
        "normalized_on_demand_EC2_EBS_cost_per_success_USD": sum(r["normalized_on_demand_EC2_EBS_USD"] for r in rows) / len(successful),
        "normalized_on_demand_EC2_EBS_median_USD": median(r["normalized_on_demand_EC2_EBS_USD"] for r in successful),
        "scenario_one_IPv4_calendar_EBS_cost_per_success_USD": sum(r["scenario_one_IPv4_calendar_EBS_USD"] for r in rows) / len(successful),
        "original_lifecycle_reported_estimate_cost_per_success_USD": sum(r["raw_reported_cost"]["usd"] for r in rows) / len(successful),
    }
    if instance in PRIMARY:
        summaries[instance]["scenario_job_log_window_one_IPv4_calendar_EBS_cost_per_success_USD"] = mean(r["scenario_job_log_window_one_IPv4_calendar_EBS_USD"] for r in rows)

comparisons = []
for size in ["large", "xlarge", "2xlarge"]:
    intel = summaries[f"m8i.{size}"]
    for competitor in ["m8a", "m9g"]:
        other = summaries[f"{competitor}.{size}"]
        pairs = []
        for date in sorted({r["date"] for r in records}):
            a = next(r for r in records if r["date"] == date and r["instance"] == f"m8i.{size}")
            b = next(r for r in records if r["date"] == date and r["instance"] == f"{competitor}.{size}")
            pairs.append({"date": date, "competitor_job_faster": b["job_seconds"] < a["job_seconds"], "competitor_normalized_cost_lower": b["normalized_on_demand_EC2_EBS_USD"] < a["normalized_on_demand_EC2_EBS_USD"], "cost_ratio": b["normalized_on_demand_EC2_EBS_USD"] / a["normalized_on_demand_EC2_EBS_USD"]})
        comparisons.append({
            "intel": f"m8i.{size}", "competitor": f"{competitor}.{size}",
            "competitor_median_job_time_reduction_pct": 100 * (1 - other["job_seconds"]["median"] / intel["job_seconds"]["median"]),
            "competitor_cost_per_success_reduction_pct": 100 * (1 - other["normalized_on_demand_EC2_EBS_cost_per_success_USD"] / intel["normalized_on_demand_EC2_EBS_cost_per_success_USD"]),
            "competitor_scenario_IPv4_calendar_cost_reduction_pct": 100 * (1 - other["scenario_one_IPv4_calendar_EBS_cost_per_success_USD"] / intel["scenario_one_IPv4_calendar_EBS_cost_per_success_USD"]),
            "pairs": pairs,
        })

intel = summaries["m8i.2xlarge"]
amd = summaries["m8a.2xlarge"]
direct_gap = intel["normalized_on_demand_EC2_EBS_cost_per_success_USD"] - amd["normalized_on_demand_EC2_EBS_cost_per_success_USD"]
break_even_intel_compute = amd["normalized_on_demand_EC2_EBS_cost_per_success_USD"] * 3600 / intel["mean_control_plane_billed_seconds"] - 0.018356
output = {
    "calculated_utc": datetime.now(timezone.utc).isoformat(),
    "type": "Original reanalysis of third-party public raw measurements; no new workload executed",
    "price_manifest": prices["manifest"],
    "selected_price_rows": price_rows,
    "formulas": {
        "normalized_direct_cost": "estimated billedSeconds / 3600 * (AWS current on-demand instance rate + raw EBS hourly estimate)",
        "cost_per_success": "sum of all observed job cost estimates / number of successful jobs; no failed job silently dropped",
        "scenario_IPv4_calendar_EBS": "estimated billedSeconds / 3600 * (on-demand EC2 + $13.40/calendar-month-hours + $0.005/hour for one assumed public IPv4)",
        "warning": "Repricing spot execution at on-demand is a counterfactual estimate, not an observed on-demand invoice. Complete invoice costs and independent workload rerun remain missing.",
    },
    "pair_matching_checks": checks,
    "summaries": summaries,
    "comparisons": comparisons,
    "primary_8vCPU_sensitivity": {
        "AMD_additional_unmeasured_cost_per_build_to_erase_direct_cost_advantage_USD": direct_gap,
        "Intel_cloud_instance_compute_rate_to_equal_AMD_direct_cost_USD_hour": break_even_intel_compute,
        "Intel_current_cloud_compute_rate_USD_hour": float(price_rows["m8i.2xlarge"]["price"]),
        "required_Intel_cloud_compute_discount_pct": 100 * (1 - break_even_intel_compute / float(price_rows["m8i.2xlarge"]["price"])),
        "job_log_window_scenario_AMD_savings_pct": 100 * (1 - amd["scenario_job_log_window_one_IPv4_calendar_EBS_cost_per_success_USD"] / intel["scenario_job_log_window_one_IPv4_calendar_EBS_cost_per_success_USD"]),
        "interpretation": "Cloud retail break-even, never Intel CPU invoice price or retained producer margin. Shared fixed cost leaves absolute savings unchanged but lowers percentage savings; a differential cost above the threshold could reverse the direct-cost ranking.",
    },
    "records": records,
    "source_SHA256": {f.name: hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(SOURCES.iterdir()) if f.is_file()},
}
(BASE / "matched_build_results.json").write_text(json.dumps(output, indent=2) + "\n")
print(json.dumps({"primary": {k: summaries[k] for k in ["m8i.2xlarge", "m8a.2xlarge", "m9g.2xlarge"]}, "sensitivity": output["primary_8vCPU_sensitivity"], "checks": len(checks), "rows": len(records)}, indent=2))

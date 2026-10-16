from pathlib import Path
import csv
import json

ROOT = Path(__file__).parent
SOURCES = ROOT / "sources"
INSTANCES = ["m8i.4xlarge", "m8a.4xlarge", "m9g.4xlarge"]


def load_json(path: Path):
    return json.loads(path.read_text())


def analyze_benchmarks():
    hardware = {}
    prices = {}
    for instance in INSTANCES:
        raw = load_json(SOURCES / f"{instance}_lscpu_stdout.txt")
        fields = {item["field"]: item["data"] for item in raw["lscpu"]}
        hardware[instance] = {
            key: fields.get(key)
            for key in ["Model name:", "BIOS Model name:", "CPU(s):", "Thread(s) per core:", "Core(s) per socket:", "NUMA node(s):"]
        }
        candidates = [row for row in load_json(SOURCES / f"{instance}_prices.json") if row["allocation"] == "ondemand"]
        values = {row["price"] for row in candidates}
        assert len(values) == 1
        assert all(row["operating_system"] == "Linux" and row["region_id"] == "us-east-1" and row["currency"] == "USD" for row in candidates)
        prices[instance] = {"price_per_hour_USD": values.pop(), "observed_at": candidates[0]["observed_at"]}

    result = {"hardware": hardware, "prices": prices, "workloads": {}}
    for task, key_fields in [("redis", ["operation", "threads", "pipeline"]), ("static_web", ["size", "threads", "connections"])]:
        metadata = {instance: load_json(SOURCES / f"{instance}_{task}_meta.json") for instance in INSTANCES}
        assert len({row["task_hash"] for row in metadata.values()}) == 1
        assert all(row["exit_code"] == 0 for row in metadata.values())
        maps = {}
        for instance in INSTANCES:
            with (SOURCES / f"{instance}_{task}_stdout.txt").open() as source:
                rows = list(csv.DictReader(source))
            maps[instance] = {tuple(row[key] for key in key_fields): row for row in rows}
            assert len(maps[instance]) == len(rows)
        common = set.intersection(*(set(rows) for rows in maps.values()))
        assert all(set(rows) == common for rows in maps.values())
        pairs = []
        for key in sorted(common):
            config = dict(zip(key_fields, key))
            record = {"config": config, "measurements": {}}
            intel_rps = float(maps[INSTANCES[0]][key]["rps"])
            for instance in INSTANCES:
                row = maps[instance][key]
                rps = float(row["rps"])
                assert rps > 0
                if task == "static_web":
                    assert int(row["failed"]) == 0
                price = prices[instance]["price_per_hour_USD"]
                intel_price = prices[INSTANCES[0]]["price_per_hour_USD"]
                record["measurements"][instance] = {
                    "rps": rps,
                    "mean_latency": float(row["latency"]),
                    "latency_unit": "ms" if task == "redis" else "seconds",
                    "throughput_relative_to_Intel": rps / intel_rps,
                    "rental_cost_per_operation_relative_to_Intel": (price / intel_price) / (rps / intel_rps),
                    "mean_latency_relative_to_Intel": float(row["latency"]) / float(maps[INSTANCES[0]][key]["latency"]),
                }
            pairs.append(record)
        summary = {}
        for instance in INSTANCES[1:]:
            ratios = [row["measurements"][instance]["rental_cost_per_operation_relative_to_Intel"] for row in pairs]
            speed = [row["measurements"][instance]["throughput_relative_to_Intel"] for row in pairs]
            latency = [row["measurements"][instance]["mean_latency_relative_to_Intel"] for row in pairs]
            summary[instance] = {
                "comparison_count": len(pairs),
                "lower_cost_configurations": sum(value < 1 for value in ratios),
                "cost_ratio_range": [min(ratios), max(ratios)],
                "throughput_ratio_range": [min(speed), max(speed)],
                "no_worse_mean_latency_configurations": sum(value <= 1 for value in latency),
                "mean_latency_ratio_range": [min(latency), max(latency)],
                "lower_cost_and_no_worse_mean_latency_configurations": sum(cost < 1 and delay <= 1 for cost, delay in zip(ratios, latency)),
            }
        result["workloads"][task] = {"metadata": metadata, "all_common_configurations": pairs, "summary": summary}
    result["interpretation"] = {
        "measurement": "Derived comparison of archival third-party measurements and separately dated cloud rental prices; no newly executed workload experiment.",
        "matching": "All 69 static-web configurations and 6 Redis configurations shared across three 16-vCPU, 64-GiB AWS product sizes; identical task hashes and same recorded server/tool versions. Redis memtier client version is not recorded and is not pinned. Intel exposes 8 physical cores with SMT while AMD/Arm expose 16 cores. Dates and binaries are not identical.",
        "not_estimated": ["Intel net CPU prices", "per-package gross margin", "CPU-only causal performance", "representative production application economics", "market share", "statistical significance"],
        "purpose": "Evidence that customer choice depends on completed-work economics and software/workload fit. A low advertised cloud price or higher CPU package ASP alone cannot validate the investment thesis.",
        "pricing_scope": "Linux, Shared tenancy, No License required, NA preinstalled software, Used capacity, OnDemand in us-east-1 per Spare Cores crawler filter; no EBS, network, discounts, tax, migration or licenses. Measured server and client share the VM.",
        "license": "Spare Cores raw records CC BY-SA 4.0. All ratios are our derived calculations, not reported manufacturer comparisons.",
        "configuration_count_warning": "75 parameter configurations are correlated observations on three archived VM test runs, not 75 independent experiments. There are no confidence intervals or population-level statistical claims.",
        "latency_warning": "No independent production service-level objective was specified. Mean latency is retained with each throughput observation and descriptive dominance is counted; there are no tail-latency measurements in these files. No-worse latency is a post-computation robustness diagnostic, not a claim of an ex ante threshold.",
        "Redis_aggregation": "rps sums SET operations per second from all client processes. Latency is the unweighted mean of each client's mean; it is not an operation-weighted mean. One client/server pair is launched per CPU in the container affinity set. A positive aggregate does not prove every client succeeded.",
        "harness_error_limits": "Redis harness does not enforce memtier exit codes or successful flush. Static-web failed counts only non-2xx/3xx responses; connect/read/write/timeout errors are not saved. Task exit zero and failed zero do not establish error-free execution.",
        "run_design": "Each workload configuration runs once for 10 seconds, with no warmup or repetitions. Both workloads use loopback. Redis tests SET only; static-web tests zero-filled in-memory cached files over plain HTTP.",
        "post_audit_disposition": "Exploratory comparison of reported benchmark throughput normalized by current rental price. Do not present this as validated production request cost, a controlled experiment, or definitive CPU economics. Missing per-client/error records cannot be repaired from these aggregate outputs.",
    }
    (ROOT / "public_cloud_benchmark_diagnostic.json").write_text(json.dumps(result, indent=2))
    return {task: result["workloads"][task]["summary"] for task in result["workloads"]}


def analyze_margin_and_capacity():
    original = load_json(ROOT.parent.parent / "intel_directional_build_2026_11_05/independent_long_underwriting.json")
    mature_other_share = original["owned_inputs"]["mix_diagnostic"]["modeled_2040_Other_share"]
    actual_margin = 3.039 / 7.318
    actual_other_share = 1.4 / 7.318
    other_margin = 0.20
    cpu_margin = (actual_margin - actual_other_share * other_margin) / (1 - actual_other_share)
    data = {
        "formula": "CPU operating margin = 1 - (1 - baseline CPU margin) * (1 + all-in unit cost change) / (1 + realized ASP change); fixed-weight mature blend = (1 - mature Other share) * CPU margin + mature Other share * Other margin.",
        "baseline": {"DCAI_margin": actual_margin, "current_Other_share": actual_other_share, "illustrative_Other_margin": other_margin, "inferred_CPU_margin": cpu_margin, "mature_Other_share": mature_other_share},
        "conditional_grid": [],
        "target_margin_thresholds": [],
    }
    for price_change in [0, -0.05, -0.10, -0.15]:
        for cost_change in [0, -0.05, -0.10, -0.15]:
            margin = 1 - (1 - cpu_margin) * (1 + cost_change) / (1 + price_change)
            blend = (1 - mature_other_share) * margin + mature_other_share * other_margin
            data["conditional_grid"].append({"ASP_change": price_change, "all_in_unit_cost_change": cost_change, "CPU_margin": margin, "mature_DCAI_blend": blend})
    for target in [0.35, 0.40]:
        target_cpu = (target - mature_other_share * other_margin) / (1 - mature_other_share)
        price_ratio = (1 - cpu_margin) / (1 - target_cpu)
        data["target_margin_thresholds"].append({"target_DCAI_margin": target, "required_CPU_margin": target_cpu, "ASP_change_at_unchanged_unit_cost": price_ratio - 1})
    mature_cpu_share = 1 - mature_other_share
    base_blend = mature_cpu_share * cpu_margin + mature_other_share * other_margin
    data["fixed_quantities_and_other_revenue_diagnostic"] = {
        "formula": "New DCAI margin = (baseline DCAI margin + baseline CPU revenue share * ASP change) / (1 + baseline CPU revenue share * ASP change).",
        "assumptions": "CPU packages and all-in dollar costs unchanged; Other revenue and dollar profit unchanged. CPU revenue share changes mechanically when ASP changes. This repairs the fixed-mix simplification in the separate grid.",
        "unchanged_ASP_DCAI_margin": base_blend,
        "margin_at_10pct_ASP_decline": (base_blend - mature_cpu_share * 0.1) / (1 - mature_cpu_share * 0.1),
        "ASP_change_for_35pct_DCAI_margin": (0.35 - base_blend) / (mature_cpu_share * (1 - 0.35)),
    }
    data["limitations"] = [
        "Other profitability and standalone CPU profitability are not disclosed. This reexpresses an existing conditional margin illustration, not a new forecast.",
        "Holding all-in cost per CPU implicitly holds allocated OpEx per unit; real fixed cost leverage, volumes, customer/SKU mix and transfer prices can differ.",
        "Intel 3 cost learning is a manufacturing cost metric, not a proportional reduction in all DCAI costs; it cannot be dropped directly into this grid.",
        "The conditional grid holds mature Other revenue share fixed. The separate fixed-quantities diagnostic allows share weights to change mechanically with ASP."
    ]
    capacity = []
    for calendar_weighted_capacity_increase in [0.10, 0.20]:
        for resources_per_good_package_increase in [0, 0.10, 0.20]:
            required_carryover_times_yield_factor = 1.20 * (1 + resources_per_good_package_increase) / (1 + calendar_weighted_capacity_increase)
            capacity.append({"calendar_weighted_capacity_increase": calendar_weighted_capacity_increase, "resources_per_good_package_increase": resources_per_good_package_increase, "required_carryover_times_yield_factor_for_20pct_units": required_carryover_times_yield_factor})
    data["capacity_calendar_diagnostic"] = {
        "equation": "Annual good-package factor = starting run-rate carryover * calendar-weighted capacity factor * yield/utilization factor / resource use per good-package factor; the tightest wafer/substrate/assembly stage binds.",
        "cases": capacity,
        "interpretation": "An illustrative 40% capacity addition active for a full half-year contributes 20% annual capacity if the other half is unchanged; a linear ramp from 0 to 40% during the half contributes 10%. Exact Intel capacity units, timing, baseline and mix are not disclosed, so this is not an Intel shipment estimate.",
        "warning": "Management's reported ~40% substrate capacity remark is from Q&A transcriptions; prepared remarks directly verify bottlenecks but not that numerical capacity specification. Do not assert capacity equals CPU units."
    }
    (ROOT / "margin_and_capacity_diagnostics.json").write_text(json.dumps(data, indent=2))
    return data["target_margin_thresholds"]


def analyze_package_and_workload_economics():
    products = {
        "Xeon 8592+": {"cores": 64, "threads": 128, "price_USD": 12992, "TDP_W": 350, "package_mm": [77.5, 56.5], "core_class": "performance", "source_file": "intel_8592plus.html"},
        "Xeon 6980P": {"cores": 128, "threads": 256, "price_USD": 13955, "TDP_W": 500, "package_mm": [104.5, 70.5], "core_class": "performance", "source_file": "intel_6980P.html"},
        "Xeon 6780E": {"cores": 144, "threads": 144, "price_USD": 9535, "TDP_W": 330, "package_mm": [77.5, 56.5], "core_class": "efficiency", "source_file": "intel_6780E.html"},
        "Xeon 6990E+": {"cores": 288, "threads": 288, "price_USD": 14995, "TDP_W": 450, "package_mm": [104.5, 70.5], "core_class": "efficiency", "source_file": "intel_6990Eplus.html"},
    }
    pairs = []
    for old_name, new_name in [("Xeon 8592+", "Xeon 6980P"), ("Xeon 6780E", "Xeon 6990E+")]:
        old, new = products[old_name], products[new_name]
        price_factor = new["price_USD"] / old["price_USD"]
        core_factor = new["cores"] / old["cores"]
        pairs.append({
            "old": old_name,
            "new": new_name,
            "recommended_customer_price_change": price_factor - 1,
            "core_count_change": core_factor - 1,
            "recommended_price_per_core_change": price_factor / core_factor - 1,
            "TDP_change": new["TDP_W"] / old["TDP_W"] - 1,
            "package_footprint_change": (new["package_mm"][0] * new["package_mm"][1]) / (old["package_mm"][0] * old["package_mm"][1]) - 1,
        })
    result = {
        "observed_date": "2026-11-05",
        "products": products,
        "pair_illustrations": pairs,
        "limitations": [
            "Recommended customer prices are current advertised Intel guidance, not realized net prices or prices available to every buyer. This is not a historical launch-price series.",
            "Selected high-core pairs illustrate content change. They do not represent sales-weighted product mix, replacement rates or actual average selling prices.",
            "Cores are not interchangeable across generations or workload types. No throughput, latency, power consumed, system TCO or price-performance claim follows from core count or TDP alone.",
            "Package footprint is not actual wafer area, yield, substrate-layer demand, cost or the limiting manufacturing resource. It indicates physical change only.",
        ],
        "owned_model_requirement": {
            "2027_package_unit_growth": 0.20,
            "2027_realized_ASP_growth": 0.20,
            "CPU_revenue_growth": 0.44,
            "formula": "Completed-work capacity = package units * workload throughput per package. CPU revenue per unit of completed-work capacity = realized package ASP / workload throughput per package.",
            "illustrative_workload_cases": [
                {"throughput_per_package_change": gain, "total_workload_capacity_growth_required_by_20pct_more_packages": 1.2 * (1 + gain) - 1, "CPU_revenue_per_workload_capacity_change": 1.2 / (1 + gain) - 1}
                for gain in [0.10, 0.25, 0.50]
            ],
            "interpretation": "Richer packages can raise Intel revenue per package while lowering the customer's CPU expenditure per workload. That can support adoption, but a package-volume forecast additionally needs sufficiently expanding workload demand, replacement demand or share gains. The illustrative throughput gains are not measured Intel forecasts.",
        },
        "share_volume_identity": {
            "formula": "Intel package units = addressable package market units * Intel unit share. Required market growth = 1.20 / (1 + relative Intel share change) - 1.",
            "cases": [{"relative_Intel_unit_share_change": change, "required_addressable_package_market_growth_for_20pct_Intel_units": 1.2 / (1 + change) - 1} for change in [0, -0.05, -0.10, -0.20]],
            "limitation": "Do not substitute hyperscaler Arm share, server-system shipment share, x86 revenue share or core share into a CPU-package unit-share identity. No particular market growth or future Intel share is forecast here.",
        },
    }
    (ROOT / "package_and_workload_economics.json").write_text(json.dumps(result, indent=2))
    return pairs


if __name__ == "__main__":
    print(json.dumps({"benchmarks": analyze_benchmarks(), "margin_thresholds": analyze_margin_and_capacity(), "SKU_illustrations": analyze_package_and_workload_economics()}, indent=2))

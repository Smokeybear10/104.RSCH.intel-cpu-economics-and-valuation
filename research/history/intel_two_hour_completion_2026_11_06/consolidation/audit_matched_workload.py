from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
import calendar
import hashlib
import json
import math
import re

OUT = Path(__file__).resolve().parent
WORK = OUT.parent / 'workload'
SOURCE = WORK / 'sources'
SOURCE_HASHES = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in SOURCE.iterdir() if p.is_file()}
PRICES = json.loads((SOURCE / 'aws_ec2_prices.json').read_text())
EXPECTED = json.loads((WORK / 'matched_build_results.json').read_text())
MANIFEST = json.loads((WORK / 'github_source_manifest.json').read_text())
ROWS, LOGS, PAIRS, BLOBS = [], [], [], []
PRIMARY = ('m8i.2xlarge', 'm8a.2xlarge')
SELECTED_RUNNERS = {'runson-m8i-large', 'runson-m8i-xlarge', 'runson-m8i-2xlarge',
                    'runson-m8a-large', 'runson-m8a-x64', 'runson-m8a-2xlarge',
                    'runson-m9g-large', 'runson-m9g-arm64', 'runson-m9g-arm64-8x32'}
PIN = '7dc9d17a7bf5671eb6129fdf9127729f659637fc'
FUNCTIONS = ['checkout', 'system packages', 'toolchain', 'cargo fmt', 'cargo test', 'cargo clippy', 'cargo clippy (no features)']
price_rows = {}
for row in PRICES['regions']['US East (N. Virginia)'].values():
    instance = row['Instance Type']
    if re.fullmatch(r'm8[ia]\.(large|xlarge|2xlarge)', instance) or re.fullmatch(r'm9g\.(large|xlarge|2xlarge)', instance):
        assert instance not in price_rows
        price_rows[instance] = row

for file in sorted(SOURCE.glob('results__rust__*.json')):
    data = json.loads(file.read_text())
    date, suite = data['run']['date'], data['run']['id']
    assert data['workload']['ref'] == PIN
    assert data['workload']['toolchain'] == 'rust 1.98.1'
    assert data['run']['event'] == 'schedule'
    assert data['selection']['missingDefaultRunners'] == []
    configs = {row['id']: row for row in data['runners']}
    selected = [r for r in data['results'] if r['runnerId'] in SELECTED_RUNNERS]
    assert len(selected) == 9
    assert len({r['host']['ec2']['instanceType'] for r in selected}) == 9
    pair = []
    for row in selected:
        config, host, cost = configs[row['runnerId']], row['host'], row['cost']
        instance = host['ec2']['instanceType']
        success = row['status'] == 'success' and all(p['status'] == 'success' for p in row['phases'])
        assert [p['name'] for p in row['phases']] == FUNCTIONS
        assert row['workloadSeconds'] == sum(p['seconds'] for p in row['phases'])
        assert host['ec2']['region'] == 'us-east-1'
        assert cost['source'] == 'runs-on-control-plane'
        rate = float(price_rows[instance]['price'])
        seconds = cost['billedSeconds']
        assert seconds >= 60
        direct = seconds * (rate + cost['ebsHourlyUsd']) / 3600
        calendar_ebs = (30 * .08 + (400 - 125) * .04) / (calendar.monthrange(int(date[:4]), int(date[5:7]))[1] * 24)
        record = {'date': date, 'instance': instance, 'success': success, 'full_job_seconds': row['jobSeconds'],
                  'queue_plus_job_seconds': row['queueSeconds'] + row['jobSeconds'], 'billed_seconds': seconds,
                  'direct_cost_USD': direct, 'reported_lifecycle_cost_estimate_USD': cost['usd'],
                  'ceil_second_direct_cost_control_USD': math.ceil(seconds) * (rate + cost['ebsHourlyUsd']) / 3600,
                  'calendar_EBS_IPv4_control_USD': seconds * (rate + calendar_ebs + .005) / 3600,
                  'lifecycle': host['ec2']['lifecycle'], 'job_url': row['jobUrl']}
        if instance in PRIMARY:
            job_id = row['jobUrl'].split('/')[-1]
            log = re.sub(r'\x1b\[[0-9;]*m', '', (SOURCE / f'github_job_{job_id}.log').read_text())
            result = re.findall(r'test result: ok\. (\d+) passed; (\d+) failed; (\d+) ignored; (\d+) measured; (\d+) filtered out', log)
            assert result == [('45', '0', '0', '0', '0')]
            tests = sorted(re.findall(r'^\S+Z test ([^\n]+) \.\.\. ok$', log, re.MULTILINE))
            assert len(tests) == len(set(tests)) == 45
            crates = sorted(set(re.findall(r'Compiling\s+(\S+)\s+(v\S+)', log)))
            assert len(crates) == 470
            assert PIN in log and '1.98.1' in log
            assert 'cargo fmt --all -- --check' in log
            assert 'cargo test --no-default-features --features "$RUST_FEATURES"' in log
            assert 'cargo clippy --no-default-features --features "$RUST_FEATURES" -- -D warnings' in log
            assert 'cargo clippy --no-default-features -- -D warnings' in log
            assert 'Process completed with exit code' not in log
            minutes, remainder = re.search(r'Billed duration\s*\|\s*(\d+)m(\d+)s', log).groups()
            log_seconds = int(minutes) * 60 + int(remainder)
            record['log_window_seconds'] = log_seconds
            record['log_window_calendar_EBS_IPv4_control_USD'] = log_seconds * (rate + calendar_ebs + .005) / 3600
            record['physical_core_count'] = host['cpu']['logicalCpus'] / host['cpu']['threadsPerCore']
            record['model'] = host['cpu']['model']
            assert config['vcpu'] == host['cpu']['logicalCpus'] == 8
            assert config['ramGiB'] == 32
            assert host['memory']['swapGiB'] == 0
            assert host['storage']['devices'][0]['sizeGiB'] == 30
            LOGS.append({'date': date, 'job_id': job_id, 'instance': instance, 'test_names': tests,
                         'tests': len(tests), 'compiled_crates': len(crates),
                         'test_names_sha256': hashlib.sha256(json.dumps(tests).encode()).hexdigest(),
                         'compiled_crates_sha256': hashlib.sha256(json.dumps(crates).encode()).hexdigest(),
                         'phase_statuses': {p['name']: p['status'] for p in row['phases']}})
            pair.append((row, record))
        ROWS.append(record)
    assert len(pair) == 2 and all(item[1]['success'] for item in pair)
    indexed = {row['instance']: (raw, row) for raw, row in pair}
    intel, amd = indexed[PRIMARY[0]], indexed[PRIMARY[1]]
    for field in ['os', 'kernel']:
        assert intel[0]['host'][field] == amd[0]['host'][field]
    assert intel[0]['host']['ec2']['amiId'] == amd[0]['host']['ec2']['amiId']
    assert intel[0]['host']['runner']['imageVersion'] == amd[0]['host']['runner']['imageVersion']
    PAIRS.append({'date': date, 'same_AZ': intel[0]['host']['ec2']['availabilityZone'] == amd[0]['host']['ec2']['availabilityZone'],
                  'AMD_faster_full_job': amd[1]['full_job_seconds'] < intel[1]['full_job_seconds'],
                  'AMD_lower_normalized_cost': amd[1]['direct_cost_USD'] < intel[1]['direct_cost_USD'],
                  'normalized_cost_savings_pct': 100 * (1 - amd[1]['direct_cost_USD'] / intel[1]['direct_cost_USD'])})
    record = next(r for r in MANIFEST['raw_repository_files'] if r['path'].endswith(file.name.replace('results__rust__', '')))
    raw = file.read_bytes()
    digest = hashlib.sha1(f'blob {len(raw)}\0'.encode() + raw).hexdigest()
    BLOBS.append({'file': file.name, 'git_blob_sha': digest, 'matches_source_manifest': digest == record['git_blob_sha']})

assert len(LOGS) == 10
assert len({r['test_names_sha256'] for r in LOGS}) == 1
assert len({r['compiled_crates_sha256'] for r in LOGS}) == 1
summaries = {}
for instance in price_rows:
    rows = [r for r in ROWS if r['instance'] == instance]
    successes = sum(r['success'] for r in rows)
    assert len(rows) == 5
    summaries[instance] = {'runs': len(rows), 'successful_runs': successes,
                           'median_full_job_seconds': median(r['full_job_seconds'] for r in rows),
                           'full_job_range_seconds': [min(r['full_job_seconds'] for r in rows), max(r['full_job_seconds'] for r in rows)],
                           'mean_billed_seconds': sum(r['billed_seconds'] for r in rows) / len(rows),
                           'lifecycles': dict(Counter(r['lifecycle'] for r in rows))}
    for key in ['direct_cost_USD', 'reported_lifecycle_cost_estimate_USD', 'ceil_second_direct_cost_control_USD', 'calendar_EBS_IPv4_control_USD']:
        summaries[instance][key + '_per_success'] = sum(r[key] for r in rows) / successes
    if instance in PRIMARY:
        summaries[instance]['log_window_calendar_EBS_IPv4_control_USD_per_success'] = sum(r['log_window_calendar_EBS_IPv4_control_USD'] for r in rows) / successes

intel, amd = (summaries[k] for k in PRIMARY)
metrics = ['direct_cost_USD', 'reported_lifecycle_cost_estimate_USD', 'ceil_second_direct_cost_control_USD', 'calendar_EBS_IPv4_control_USD', 'log_window_calendar_EBS_IPv4_control_USD']
savings = {m: 100 * (1 - amd[m + '_per_success'] / intel[m + '_per_success']) for m in metrics}
assert abs(savings['direct_cost_USD'] - 11.155866028795957) < 1e-10
checks = []
for instance, row in summaries.items():
    expected = EXPECTED['summaries'][instance]
    checks.append({'instance': instance, 'direct_cost_difference_USD': row['direct_cost_USD_per_success'] - expected['normalized_on_demand_EC2_EBS_cost_per_success_USD'],
                   'success_count_difference': row['successful_runs'] - expected['successful_jobs']})

fresh_logs = []
for name, job in [('intel', 126341529750), ('amd', 126341529652)]:
    fresh = (OUT / f'sources/workload_rechecked_{name}.log').read_text().lstrip('\ufeff').rstrip('\n')
    old = (SOURCE / f'github_job_{job}.log').read_text().lstrip('\ufeff').rstrip('\n')
    fresh_logs.append({'job': job, 'fresh_connector_log_matches_archived_after_BOM_final_newline_normalization': fresh == old})

workflows = [{'path': p.name, 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in SOURCE.glob('rust_workflow_*.yml')]
assert len(workflows) == 5 and len({r['sha256'] for r in workflows}) == 1
report = {
    'checked_utc': datetime.now(timezone.utc).isoformat(), 'method': 'Independent raw-JSON and original-log parse, without importing or executing the author calculation. Every primary log checked programmatically; latest Intel/AMD logs also inspected at test, compile and shutdown-cost sections and freshly retrieved through GitHub connector.',
    'bounded_headline_passes': True, 'source_hashes': SOURCE_HASHES, 'raw_records_checked': len(ROWS),
    'denominator': 'Sum estimated costs of all selected executions divided by successful complete jobs, not 45 tests. All five jobs per instance succeeded; no failed primary execution was dropped.',
    'primary_summaries': {k: summaries[k] for k in PRIMARY}, 'AMD_savings_pct_by_cost_basis': savings,
    'paired_controls': PAIRS, 'log_quality_checks': LOGS, 'source_git_blob_checks': BLOBS,
    'fresh_original_log_checks': fresh_logs, 'workflow_hashes': workflows, 'author_result_comparisons': checks,
    'AWS_current_rate_recheck': json.loads((OUT / 'workload_live_rate_recheck.json').read_text()),
    'official_resource_mapping_crosscheck': {
        'specifications': 'https://docs.aws.amazon.com/ec2/latest/instancetypes/gp.html',
        'CPU_options': 'https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/cpu-options-supported-instances-values.html',
        'confirmed': 'Official AWS tables independently confirm m8i.2xlarge = 8 vCPU / 4 cores / 2 threads per core, m8a.2xlarge = 8 vCPU / 8 cores / 1 thread per core. Both list 32 GiB and the same 312.5/1250 MB/s baseline/burst EBS throughput.'
    },
    'important_limits': [
        'The 11.16% result is current on-demand EC2 repricing of source-estimated instance windows plus source-estimated EBS, not an observed paid invoice.',
        'Original mixed-lifecycle estimates give only 3.08% AMD savings in aggregate, and the latest pair instead favors Intel. All Intel runs used spot, versus four AMD spot and one AMD on-demand run. Do not substitute the normalized conclusion for observed spot economics.',
        'Both products advertise 8 vCPU and 32 GiB, but Intel exposes four physical cores with SMT and AMD eight physical cores. This is a purchasable cloud-product comparison, not equal-core architectural efficiency.',
        'All ten logs pass identical 45 named tests; these establish this workflow acceptance criterion, not production correctness for every buyer or a reliability percentile. Five paired suite dates are the experimental units, not 450 independent observations.',
        'Workload source, Rust version, feature flags, observed compiled crate/version set, pair OS/kernel/AMI and storage size match. The 45 tests belong to a debug build; the result is CI completion time, not runtime application performance or AI inference performance.',
        'No independent workload rerun, binary hash comparison, full package lock, randomized placement or invoice-resource reconciliation was performed. Some pairs use different availability zones.',
        'The public original log uses a longer boot/job/shutdown allowance than the control-plane window. Repricing that window with calendar-month EBS and one assumed IPv4 leaves 7.76% savings, but neither window has an invoice tie-out.',
        'Network/IP allocation, software/controller allocation, storage/artifact requests, discounts, support, migration and failure/retry risk are not completely measured. Differential omitted AMD costs of about $0.001735 per job erase the main direct-cost gap.',
        'RunsOn operates and publishes the tests and has a commercial interest. The source was chosen after seeing rankings; this is original reanalysis of public measurements, not a blind experiment or customer interview.',
        'Nothing here identifies Intel procurement price, chip ASP, manufacturing cost, retained producer profit or company-wide share. No direct valuation or DCAI-margin adjustment follows.'
    ],
    'all_workload_source_hashes_unchanged': all(hashlib.sha256((SOURCE / name).read_bytes()).hexdigest() == digest for name, digest in SOURCE_HASHES.items()),
}
(OUT / 'independent_matched_workload_audit.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps({k: report[k] for k in ['bounded_headline_passes', 'raw_records_checked', 'primary_summaries', 'AMD_savings_pct_by_cost_basis', 'fresh_original_log_checks', 'author_result_comparisons', 'all_workload_source_hashes_unchanged']}, indent=2))

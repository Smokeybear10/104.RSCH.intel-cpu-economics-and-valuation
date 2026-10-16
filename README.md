# Intel | Investment Research

Python valuation models, source records and a ten-page Intel stock pitch for the M37 competition.

The thesis tests whether server CPU market growth and richer product mix can offset Intel's shipment-share losses—and whether the resulting profit survives manufacturing costs and capital spending.

## Research Snapshot

The November 7, 2026 case uses a 3–5 year investment horizon:

| Item | Frozen case |
|---|---|
| Recommendation | Conditional long at $40 or below |
| Reference price | $56.28, November 6, 2026 close |
| Action at reference price | No new position |
| Core target | $82.47 at December 31, 2030 |
| Annual price return from reference price | 9.6%, excluding dividends |

These are dated research conclusions, not live prices. The $40 entry is a judgment under selected return requirements, not a predicted price decline or proof of current mispricing. The [decision policy](data/decision_policy.json) records the quote sources, assumptions and selection process.

Read the [pitch](artifacts/m37_intel_initial_screen.pdf), [defense notes](artifacts/m37_intel_defense_notes.pdf), [comparison with other pitches](artifacts/m37_intel_pitch_comparison.pdf) and [valuation workbook](artifacts/intel_revenue_to_cash_model.xlsx).

## Quick Start

Requires Python 3.10 or newer; these commands use Python 3.12. From the repository root:

```sh
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
python -m intel_research reproduce
python -m intel_research verify
```

`reproduce` writes `results/analysis.json` and `results/annual_cash.csv`. `verify` recomputes the model, compares it with frozen expected results and writes `results/verification.json`; a mismatch returns a nonzero exit code. Both commands accept `--data PATH` and `--output PATH`. The calculation code uses the Python standard library.

## What the Model Covers

The runnable model reconstructs cash conversion and adjusted present value from frozen annual operating forecasts. It includes CPU growth and mix controls, factory and capital-productivity stresses, quarterly financing, and entry-price sensitivities. Verification establishes arithmetic consistency; it does not establish that the forecasts will occur.

The historical archive also contains source audits and a reanalysis of five paired public Rust-build records collected by RunsOn.[^1] This was not a newly conducted benchmark. The comparison matches advertised AWS instance capacity, not physical core counts; normalized cloud-cost estimates are not paid invoices or enterprise total cost of ownership.

## Project Structure

```text
artifacts/                 # Current pitch PDFs and workbook
data/                      # Frozen model inputs, policies and expected results
src/intel_research/         # Portable calculation and verification CLI
research/sources.json      # Source index
research/history/          # Earlier research, scripts and audit records
results/                   # Generated locally
```

[Input provenance](data/provenance.json) records original paths and hashes. Historical files preserve the research process, including superseded recommendations and the earlier $52.25 quote. Some retain original workstation paths and dependencies; the supported reproduction entry point is the CLI above. It does not rebuild every historical script, PDF or workbook.

## Evidence and Limits

Intel's filings and earnings materials support observed demand and product-mix changes.[^2] Future CPU growth, pricing, factory recovery and durable cash generation remain assumptions. The case compares company revenue with aggregate consensus; it does not establish matched consensus forecasts for CPU units, share or parent cash. Long-run cash generation drives most modeled value, and combined downside scenarios can miss the selected return hurdles even at $40.

Developed by Thomas Ou with substantial Codex assistance in research, modeling, code, writing and verification. Source measurements and third-party materials retain their original attribution; see [third-party notices](THIRD_PARTY_NOTICES.md) and the [source index](research/sources.json).

[^1]: RunsOn, [benchmark methodology](https://runs-on.com/benchmarks/methodology/) and [frozen source records](https://github.com/runs-on-demo/benchmark-public/tree/3691c0856de7597b2c73d86e4e2f0ee3cd934849/results).
[^2]: Intel, [Q3 2026 Form 10-Q](https://www.intc.com/filings-reports/all-sec-filings/content/0000050863-26-000191/intc-20260926.htm) and [Q1 2026 earnings remarks](https://download.intel.com/newsroom/2026/earnings/1Q2026-Earnings-Call.pdf).

Built by Thomas Ou

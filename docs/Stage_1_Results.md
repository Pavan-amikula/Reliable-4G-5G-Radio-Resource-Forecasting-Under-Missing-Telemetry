# Stage 1: measured extraction and naive forecasting baselines

Measured on 16 October 2026 using the included Dataset_02 archive. This report covers the fixed-rule baselines; learned-model results are recorded separately.

Extracted 114,460 observed targets across 20 technology/band/station/sector series, with 166,032 first-to-last clock slots. Blank targets remain unavailable.

Stations: Site 5, Site 7, Site 16, Site 22, Site 53.
Station holdout: Site 53 (four series). Remaining stations supply 16 development series.

## Frozen protocol

First five numeric station IDs with >=2 sectors having >=70% observed slots in BOTH technologies during the early window; first two numeric sectors each. Fifth station reserved.

Selection window: 2025-02-08T00:00:00+00:00 through 2025-02-22T00:00:00+00:00 exclusive. Each selected series needed at least 941/1344 observed slots (70%); actual minimum was 1115. This favors well-observed early stations and does not represent all 59 observed stations.

| Partition | Start UTC inclusive | End UTC exclusive |
|---|---|---|
| train | 2025-02-07T19:45:00+00:00 | 2025-03-01T00:00:00+00:00 |
| tuning | 2025-03-01T00:00:00+00:00 | 2025-04-12T00:00:00+00:00 |
| calibration | 2025-04-12T00:00:00+00:00 | 2025-04-26T00:00:00+00:00 |
| test | 2025-04-26T00:00:00+00:00 | 2025-05-05T07:30:00+00:00 |

Train includes February and cohort window. Tuning includes March 1-11 and April 5-11, spanning the documented recording gap. Calibration uses April 12-25; final test April 26-May 5. Shared calendar cutoffs; no target-value-based selection.

No fit or tuning. Labels crossing ANY split end purged. Persistence requires observation at origin, no stale carry. Daily seasonal uses exact t+h-24h only, abstaining if absent. Available and paired rows reported separately; paired rows are the fair comparison. Features may read only past/current observations. Holdout early data used solely for eligibility, no learned fit; holdout scores only in final time block. Online prior observations from all roles may be used for history.

Daily seasonal predicts y(t+h-24h), rather than y(t-24h). It may issue a forecast when the current reading is absent; persistence requires a current observed reading. Paired comparison requires both predictions and observed ground truth. No input or ground-truth zero filling occurs.

Holdout is a station-exclusion protocol for later models, not evidence of learned cross-station transfer from naive methods. It uses its own causal target history at replay time. Features carry role labels; exclude holdout rows from every learned fitting/preprocessing/tuning/calibration step.

## Final-period baseline results

Errors are percentage points. Both models below use exactly the same scored rows within each technology/horizon/role.

| Role | Technology | Horizon min | Paired rows | Persistence MAE / RMSE | Daily seasonal MAE / RMSE |
|---|---|---:|---:|---:|---:|
| development | LTE | 15 | 6,750 | 3.653 / 5.409 | 7.731 / 12.182 |
| development | LTE | 30 | 6,724 | 4.481 / 6.735 | 7.737 / 12.184 |
| development | LTE | 60 | 6,688 | 5.330 / 7.994 | 7.753 / 12.203 |
| development | NR | 15 | 7,138 | 1.410 / 2.687 | 2.606 / 4.883 |
| development | NR | 30 | 7,130 | 1.740 / 3.301 | 2.607 / 4.884 |
| development | NR | 60 | 7,114 | 2.007 / 3.795 | 2.606 / 4.884 |
| station_holdout | LTE | 15 | 1,575 | 2.445 / 3.813 | 5.012 / 7.472 |
| station_holdout | LTE | 30 | 1,565 | 3.035 / 4.609 | 5.026 / 7.489 |
| station_holdout | LTE | 60 | 1,544 | 3.545 / 5.337 | 5.061 / 7.530 |
| station_holdout | NR | 15 | 1,786 | 0.762 / 1.769 | 1.099 / 2.200 |
| station_holdout | NR | 30 | 1,784 | 0.873 / 1.853 | 1.088 / 2.139 |
| station_holdout | NR | 60 | 1,780 | 0.948 / 1.944 | 1.088 / 2.141 |

## Scored-row coverage in the final period

Grid origins have in-partition future timestamps. Observed future labels may still lack current or seasonal inputs. Counts include missing-clock intervals; they are not raw padded-row missingness rates.

| Role | Technology | Horizon min | Grid origins | Observed future labels | Persistence scored | Seasonal scored | Paired / observed labels |
|---|---|---:|---:|---:|---:|---:|---:|
| development | LTE | 15 | 7,144 | 6,902 | 6,859 | 6,778 | 6,750 / 6,902 (97.8%) |
| development | LTE | 30 | 7,136 | 6,894 | 6,823 | 6,770 | 6,724 / 6,894 (97.5%) |
| development | LTE | 60 | 7,120 | 6,879 | 6,782 | 6,755 | 6,688 / 6,879 (97.2%) |
| development | NR | 15 | 7,144 | 7,138 | 7,138 | 7,138 | 7,138 / 7,138 (100.0%) |
| development | NR | 30 | 7,136 | 7,130 | 7,130 | 7,130 | 7,130 / 7,130 (100.0%) |
| development | NR | 60 | 7,120 | 7,114 | 7,114 | 7,114 | 7,114 / 7,114 (100.0%) |
| station_holdout | LTE | 15 | 1,786 | 1,657 | 1,643 | 1,583 | 1,575 / 1,657 (95.1%) |
| station_holdout | LTE | 30 | 1,784 | 1,655 | 1,629 | 1,581 | 1,565 / 1,655 (94.6%) |
| station_holdout | LTE | 60 | 1,780 | 1,651 | 1,609 | 1,577 | 1,544 / 1,651 (93.5%) |
| station_holdout | NR | 15 | 1,786 | 1,786 | 1,786 | 1,786 | 1,786 / 1,786 (100.0%) |
| station_holdout | NR | 30 | 1,784 | 1,784 | 1,784 | 1,784 | 1,784 / 1,784 (100.0%) |
| station_holdout | NR | 60 | 1,780 | 1,780 | 1,780 | 1,780 | 1,780 / 1,780 (100.0%) |

Persistence has lower pooled MAE than daily seasonal on all paired final-period technology/horizon groups in this selected cohort. This is a descriptive baseline result, without statistical significance or a learned-model improvement claim.

## Files and limits

- `data/processed/observed_v1.sqlite`: unique observed percentages, full keys, archive member and source CSV row (header is row 1).
- `data/processed/manifest_v1.json`: hashes, early cohort counts, per-series gap histograms and frozen cutoffs.
- `outputs/baselines_v1/forecasts.csv.gz`: labels and both forecasts; blanks denote abstention. Missing labels are counted in coverage, never scored.
- `outputs/baselines_v1/features.csv.gz`: full first-to-last grid, exact history lags, observed-only last-hour mean/count and age; blank lag fields signal unavailable inputs. No future label or future KPI is an input.
- `outputs/baselines_v1/metrics.json`: available-row and paired-row pooled/macro errors plus per-series errors, including training/tuning/calibration where permitted.
- `outputs/baselines_v1/coverage.json`: per-series origin, missing-label, input availability and boundary-purge counts.
- `outputs/baselines_v1/split_manifest.json`: frozen protocol and extraction/evaluation code hashes.

Validation: eight protocol regression checks passed. The saved-artifact validator checked all 286,331 forecast rows against extracted targets, exact input timestamps, roles and split boundaries; it recomputed all 816 per-series metric groups. SHA-256 checks confirmed all 12 protected original raw/audit/research/audit-script/instruction files were unchanged.

The row cap is 180,000 observations; grid cap 200,000 rows. SQLite cache is capped at 16 MiB; no peak-process RAM benchmark was performed. Only one series is loaded for feature generation. Raw files and prior audits were not rewritten; no complete audit was rerun.

UTC publisher timestamps; assume each counter is available at its timestamp. Interval start/end and export delay are not confirmed. This is an idealized replay availability assumption.

Other KPI uniqueness and availability remain unverified, so no field-wise merge was attempted. Energy is excluded. No congestion model, uncertainty calibration, missing-input stress experiment or live deployment is claimed. The large recording gap remains missing rather than bridged. Subsequent natural-gap and simulated-outage comparisons are documented in Missing_Readings_Step.md.

The final period has now been evaluated for these fixed baselines. Preserve the cutoffs and policies; use training/tuning for subsequent model decisions, calibration for intervals, and avoid choosing later changes from final-test scores.

Related experiments: Ridge, HGB, LightGBM, calibrated ranges and missing-input checks are indexed in [Project_Progress.md](Project_Progress.md).

Dataset attribution: Lehoczky et al., Performance Management Counters from Live 5G, 4G and 2G Radio Access Network, Zenodo dataset version https://doi.org/10.5281/zenodo.17815388; descriptor https://doi.org/10.1038/s41597-026-07723-0. CC BY 4.0. Extraction and derived forecasts are project transformations.

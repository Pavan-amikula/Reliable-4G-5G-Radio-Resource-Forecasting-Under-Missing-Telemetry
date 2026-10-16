# Ridge regression experiment

Ridge provides a compact learned baseline for the fixed chronological forecasting protocol.

## Purpose

Test whether a small learned combination of recent utilization and calendar inputs beats simple persistence and yesterday's value. We reused the prepared tables and existing chronological cutoffs; no new raw-data extraction was needed.

## Process

1. Verified installed library imports and pip dependency consistency.
2. Fit missing-input replacements from training medians; retained explicit missing flags. Fit scaling from training only. No future or held-out-station information was used.
3. Fitted Ridge for each technology and horizon. Tested alpha 0.1, 1 and 10; selected using tuning MAE. This regularization setting controls how much the linear coefficients are constrained.
4. Saved selected pipelines before opening test tables. Predicted within the fixed physical 0..100 range. Calibration remained reserved.
5. Compared against the two baselines on identical paired rows, separately for familiar stations and Site 53 holdout.

## Measured familiar-station final-test MAE

Percentage points, lower is better:

| Horizon | LTE persistence | LTE Ridge | NR persistence | NR Ridge |
|---|---:|---:|---:|---:|
| 15 min | 3.653 | 3.488 | 1.410 | 1.352 |
| 30 min | 4.481 | 4.225 | 1.740 | 1.620 |
| 60 min | 5.330 | 5.002 | 2.007 | 1.865 |

Ridge improved pooled MAE in these six comparisons. It did not improve every group: held-out-station LTE 60-minute MAE was 3.560 versus persistence's 3.545. These are descriptive results on the selected small cohort; no statistical significance was established.

The script took 9.5 seconds in this run, using at most two numerical-library threads. Peak process RAM was not benchmarked.

## Files and why they exist

| File | Purpose |
|---|---|
| `scripts/train_ridge.py` | Reproducible train/tune/evaluate procedure; existing output version cannot be overwritten accidentally |
| `requirements-ml-lock.txt` | Installed Python package versions |
| `outputs/ridge_v1/Results.md` | Full readable comparison, including holdout and limitations |
| `outputs/ridge_v1/LTE_15m.joblib` and five companions | Fitted preprocessing and model for each technology/horizon |
| `outputs/ridge_v1/selection.json` | Protocol and selected settings frozen before test reads |
| `outputs/ridge_v1/tuning_trials.json` | Results of the 18 bounded candidate fits |
| `outputs/ridge_v1/preprocessing.json` | Training medians, scaling, coefficient values and fit-row counts |
| `outputs/ridge_v1/forecasts.csv.gz` | Individual predictions and observed answers |
| `outputs/ridge_v1/metrics.json` | Pooled, macro and per-series MAE/RMSE |
| `outputs/ridge_v1/coverage.json` | Scored and paired row counts |
| `outputs/ridge_v1/run_manifest.json` | Versions, runtime, source/output hashes and frozen rules |

## Verification

All 15 protocol tests passed. Additional artifact checks confirmed train-only medians/scaling, tuning-only choices, equality with the saved paired baseline scores, recomputed 648 per-series metric groups from 127,756 saved forecasts, and verified recorded artifact hashes.

This experiment evaluates the first learned baseline. Subsequent comparisons, calibrated ranges and missing-current tests are documented in [project status](Project_Progress.md). Extra KPI inputs and live deployment remain outside the implemented scope.

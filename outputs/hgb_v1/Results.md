# Tree-model comparison: HistGradientBoosting

Measured CPU experiment. Six selected models, two leaf budgets each (15/31), 200 boosting iterations, two numerical threads. Selection uses development tuning MAE only; no random internal validation or calibration access. Native missing-value handling, same exact-history features and partitions as Ridge.

## Final-period comparison

Same paired rows for all four methods. MAE is in percentage points; lower is better. These are descriptive small-cohort results, not significance tests.

| Role | Technology | Horizon | Rows | Persistence MAE | Daily MAE | Ridge MAE | HGB MAE | HGB RMSE |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| development | LTE | 15m | 6,750 | 3.653 | 7.731 | 3.488 | 3.428 | 5.040 |
| development | LTE | 30m | 6,724 | 4.481 | 7.737 | 4.225 | 4.006 | 5.931 |
| development | LTE | 60m | 6,688 | 5.330 | 7.753 | 5.002 | 4.432 | 6.655 |
| development | NR | 15m | 7,138 | 1.410 | 2.606 | 1.352 | 1.335 | 2.436 |
| development | NR | 30m | 7,130 | 1.740 | 2.607 | 1.620 | 1.563 | 2.845 |
| development | NR | 60m | 7,114 | 2.007 | 2.606 | 1.865 | 1.703 | 3.050 |
| station_holdout | LTE | 15m | 1,575 | 2.445 | 5.012 | 2.351 | 2.386 | 3.455 |
| station_holdout | LTE | 30m | 1,565 | 3.035 | 5.026 | 2.904 | 2.906 | 4.026 |
| station_holdout | LTE | 60m | 1,544 | 3.545 | 5.061 | 3.560 | 3.347 | 4.535 |
| station_holdout | NR | 15m | 1,786 | 0.762 | 1.099 | 0.731 | 0.730 | 1.476 |
| station_holdout | NR | 30m | 1,784 | 0.873 | 1.088 | 0.820 | 0.798 | 1.462 |
| station_holdout | NR | 60m | 1,780 | 0.948 | 1.088 | 0.906 | 0.846 | 1.502 |

## Model family choice uses tuning only

The proposed candidate below is the lowest pooled *tuning* MAE among persistence, Ridge and HGB on their common available rows. It is not chosen from test performance. LightGBM remains an untested planned candidate.

| Technology | Horizon | Tuning-selected candidate | Tuning MAE |
|---|---:|---|---:|
| LTE | 15m | hgb | 3.601 |
| LTE | 30m | hgb | 4.220 |
| LTE | 60m | hgb | 4.582 |
| NR | 15m | hgb | 1.395 |
| NR | 30m | hgb | 1.644 |
| NR | 60m | hgb | 1.805 |

## Saved files

- `selection.json`: parameter choices and frozen protocol before test reads.
- `tuning_trials.json`: the 12 candidate fits and timings.
- Six `.joblib` files: fitted HGB models.
- `forecasts.csv.gz`: the original Ridge/baseline rows plus HGB predictions.
- `metrics.json`: available/paired, per-series, pooled and macro errors.
- `coverage.json`: scored-row counts.
- `run_manifest.json`: versions, source hashes and output hashes.

Measured script runtime: 17.6 seconds. Peak RAM not benchmarked.

The held-out station is excluded from all learned fitting and selection. Current readings are still required, so outage robustness is not yet demonstrated. Timestamp availability is assumed, not verified. No extra KPI merging, energy modeling or live deployment. No old artifacts were overwritten.

Next stages: a bounded LightGBM comparison; prediction intervals and separate calibration; missing-telemetry stress tests; station/day block uncertainty and compute benchmarks; API and historical replay dashboard. Neural models remain optional. Keep any later feature/hyperparameter decisions on training/tuning, never the already-viewed final test.

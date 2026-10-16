# First learned model: Ridge

This is a measured CPU experiment, not a proposed score. Six models (technology × horizon) were fitted on training rows, with three alpha candidates each and selection on tuning only.

Missing inputs were replaced by training medians, then standardized using training statistics. Flags preserve missingness. Calibration was not used. Test and Site 53 were excluded from every fit and parameter choice. Models were frozen before test data were opened. IDs are metadata only.

## Final-period fair comparison

All three methods use the same paired rows in each row below. Errors are percentage points; lower is better.

| Role | Tech | Horizon | Rows | Ridge MAE | Persistence MAE | Daily MAE | Ridge RMSE |
|---|---|---:|---:|---:|---:|---:|---:|
| development | LTE | 15m | 6,750 | 3.488 | 3.653 | 7.731 | 5.107 |
| development | LTE | 30m | 6,724 | 4.225 | 4.481 | 7.737 | 6.225 |
| development | LTE | 60m | 6,688 | 5.002 | 5.330 | 7.753 | 7.350 |
| development | NR | 15m | 7,138 | 1.352 | 1.410 | 2.606 | 2.484 |
| development | NR | 30m | 7,130 | 1.620 | 1.740 | 2.607 | 2.946 |
| development | NR | 60m | 7,114 | 1.865 | 2.007 | 2.606 | 3.351 |
| station_holdout | LTE | 15m | 1,575 | 2.351 | 2.445 | 5.012 | 3.531 |
| station_holdout | LTE | 30m | 1,565 | 2.904 | 3.035 | 5.026 | 4.164 |
| station_holdout | LTE | 60m | 1,544 | 3.560 | 3.545 | 5.061 | 4.916 |
| station_holdout | NR | 15m | 1,786 | 0.731 | 0.762 | 1.099 | 1.532 |
| station_holdout | NR | 30m | 1,784 | 0.820 | 0.873 | 1.088 | 1.518 |
| station_holdout | NR | 60m | 1,780 | 0.906 | 0.948 | 1.088 | 1.574 |

## What files mean

- Six `.joblib` files: fitted train-only imputer/scaler/Ridge pipelines. Load only these locally generated trusted artifacts.
- `selection.json`: selected parameters and protocol frozen before test access.
- `tuning_trials.json`: 18 bounded candidate results; selection uses tuning MAE only.
- `preprocessing.json`: training medians, scales, coefficients and fitted-row counts.
- `forecasts.csv.gz`: individual predictions and measured answers.
- `metrics.json`: per-series, pooled and macro MAE/RMSE on available and paired rows.
- `coverage.json`: eligible and scored-row counts.
- `run_manifest.json`: versions, runtime, hashes and evaluation rules.

Total script time: 9.5 seconds, with numerical-library threads capped at two. Peak process RAM has not been measured.

Current measurements are required at forecast origins. This does not test missing-current outages. Counters are assumed available at their recorded timestamps; reporting delay remains unverified. The cohort contains 16 familiar series and four holdout series, not all network stations. Historical replay does not establish deployment, congestion detection, energy savings, or statistical significance. A small Ridge comparison does not determine whether boosting or neural methods will win.

The final period has already been scored. Future feature and hyperparameter decisions must use training/tuning only. Calibration remains for later interval work. No extra KPI or energy fields were merged.

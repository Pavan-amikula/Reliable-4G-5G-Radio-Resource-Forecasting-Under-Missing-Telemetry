# LightGBM: did another model help?

We trained another model using the same past readings, dates and forecast questions. Two small tree sizes were tried; settings were chosen using the tuning period only. The final test answers and reserved calibration period were not used for fitting or selection.

## Average distance between prediction and actual reading

Lower numbers are better. A distance of 4 percentage points means that predicting 44% when the reading was 40% gives an error of 4 for that example. These tables average that distance across many forecasts; individual errors can be larger. The technical name is MAE.

All methods below use the same paired rows. Familiar stations are different from the separate station excluded from training.

| Station group | Technology | Forecast ahead | Rows | Latest reading | Yesterday | Ridge | Earlier tree (HGB) | LightGBM |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Familiar | 4G | 15 min | 6,750 | 3.653 | 7.731 | 3.488 | 3.428 | 3.416 |
| Familiar | 4G | 30 min | 6,724 | 4.481 | 7.737 | 4.225 | 4.006 | 4.000 |
| Familiar | 4G | 60 min | 6,688 | 5.330 | 7.753 | 5.002 | 4.432 | 4.467 |
| Familiar | 5G | 15 min | 7,138 | 1.410 | 2.606 | 1.352 | 1.335 | 1.340 |
| Familiar | 5G | 30 min | 7,130 | 1.740 | 2.607 | 1.620 | 1.563 | 1.567 |
| Familiar | 5G | 60 min | 7,114 | 2.007 | 2.606 | 1.865 | 1.703 | 1.707 |
| Excluded station | 4G | 15 min | 1,575 | 2.445 | 5.012 | 2.351 | 2.386 | 2.368 |
| Excluded station | 4G | 30 min | 1,565 | 3.035 | 5.026 | 2.904 | 2.906 | 2.939 |
| Excluded station | 4G | 60 min | 1,544 | 3.545 | 5.061 | 3.560 | 3.347 | 3.406 |
| Excluded station | 5G | 15 min | 1,786 | 0.762 | 1.099 | 0.731 | 0.730 | 0.733 |
| Excluded station | 5G | 30 min | 1,784 | 0.873 | 1.088 | 0.820 | 0.798 | 0.800 |
| Excluded station | 5G | 60 min | 1,780 | 0.948 | 1.088 | 0.906 | 0.846 | 0.847 |

## Candidate chosen without looking at final-test performance

Below we compare the models using the earlier tuning period. This keeps final answers out of the selection decision. Candidate selection here is for point forecasts; interval models and calibration are a separate pending step.

| Technology | Forecast ahead | Lowest average tuning error | Error in percentage points |
|---|---:|---|---:|
| 4G | 15 min | hgb | 3.601 |
| 4G | 30 min | hgb | 4.220 |
| 4G | 60 min | hgb | 4.582 |
| 5G | 15 min | hgb | 1.395 |
| 5G | 30 min | hgb | 1.644 |
| 5G | 60 min | lightgbm | 1.805 |

## Files: what each one is for

- `selection.json`: chosen tree settings and rules saved before test access.
- `tuning_trials.json`: all 12 small training experiments and their earlier-period errors.
- Six `.joblib` files: saved models for 4G/5G and 15/30/60 minutes.
- `forecasts.csv.gz`: each prediction, actual answer and unchanged predictions from earlier models.
- `metrics.json`: average errors, including separate sectors and station groups; RMSE is also saved and gives extra weight to large errors.
- `coverage.json`: number of forecast questions that could be scored.
- `run_manifest.json`: software versions, timing, file fingerprints and evaluation rules.

The full experiment took 14.9 seconds. Training used the CPU with two threads, at most 300 rounds and 15/31 leaves. Native missing-input handling preserves observed zeros. Peak memory was not measured.

These are small-cohort historical results. They do not establish statistical significance, universal superiority, network congestion detection, energy savings or live deployment. The current setup still requires a current reading. Its reporting-time availability is assumed. Calibration was not accessed. Later choices must continue to use train/tuning, not the already-viewed final test.

Next: add and check a likely range around forecasts, using the reserved calibration period only for adjustment. Then test missing readings, finish reliability/compute checks, and build the API and historical replay dashboard.

# Implementation and evaluation status

NetworkPRB is a local historical forecasting prototype. It extracts observed 4G/5G radio-resource utilization, compares CPU forecasting models, evaluates prediction ranges and missing inputs, and serves recorded-data replay through a local API and dashboard.

## Completed components

| Component | Implementation and evidence |
|---|---|
| Dataset research | Focused source review, counter interpretation and saved raw-data audits |
| Clean observations | 114,460 genuine utilization readings across 20 series; original archive preserved |
| Training tables | 284,200 exact-time input/answer pairs; chronological train/tuning/calibration/test partitions |
| Fixed-rule baselines | Persistence and daily seasonal predictions; available and paired-row counts |
| Ridge | Six selected train-only preprocessing/model pipelines; three alpha candidates per group |
| HistGradientBoosting | Six selected models; two leaf budgets per group |
| LightGBM | Six selected point models; two leaf budgets per group |
| Forecast ranges | 18 quantile models and separate development-period calibration |
| Missing inputs | Natural gaps and deterministic simulated outages; fixed stale-reading fallback |
| Reliability and cost | Exploratory station/day resampling, prediction-worker timing/memory and high-load support checks |
| API | Past-only inputs, strict validation, cached models and fresh/stale/no-estimate states |
| Dashboard | Sector/time selection, predictions/ranges, later actuals and missing-input demonstrations |
| Verification | 91 data/artifact fingerprints verified, pinned packages consistent, models load and 41 automated tests pass |

## Serving choices

Tuning-period comparisons selected HGB for all 4G horizons and 5G 15/30 minutes; LightGBM supplies the 5G 60-minute point forecast. Separate LightGBM quantile models supply the ranges. Site 53 is excluded from training, preprocessing, tuning and calibration.

For one matched familiar-station comparison, 4G 60-minute mean absolute error decreased from 5.002 percentage points with Ridge to 4.432 with HGB. This descriptive improvement is not universal across stations or individual forecasts. Full tables are in `outputs/ridge_v1/Results.md`, `outputs/hgb_v1/Results.md` and `outputs/lightgbm_v1/Results.md`.

## Evidence boundaries

- The initial cohort covers five stations, not the entire network.
- Ranges use separate calibration; temporal dependence prevents treating their target inclusion rate as a guarantee.
- Missing inputs can reduce range reliability. A fixed illustrative 60-minute stale-reading limit withholds ranges.
- Prediction-worker timing/memory exclude HTTP, disk, browser rendering, concurrency and training peak memory.
- No selected final-test reading reaches 80% utilization; high-load warning performance cannot be established.
- Availability at the recorded counter timestamp is assumed; reporting delay remains unverified.
- Live network control, energy savings and performance on unseen operators are not demonstrated.
- The current local environment is verified; a clean-machine installation has not been tested.

## Documentation

- [Overview, architecture and dataset](START_HERE.md)
- [Windows setup and reproduction](Reproduce.md)
- [Development and evaluation rules](../CONTRIBUTING.md)
- [API contract](API_Contract.md)
- [Dashboard walkthrough](Dashboard_Step.md)
- [Range experiment](Forecast_Ranges_Step.md)
- [Missing-input experiment](Missing_Readings_Step.md)
- [Reliability and compute checks](Reliability_Step.md)

Further experiments should use new output versions and preserve the evaluation rules. Additional stations, another dataset and live integration are possible extensions rather than demonstrated features.

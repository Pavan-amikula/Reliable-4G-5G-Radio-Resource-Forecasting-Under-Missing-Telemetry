# CPU forecasting methods: evidence and proposed scope

Reviewed 16 October 2026. Primary-source reading only; no training, dependency installation or dataset changes. This supplements the university-library review. Our task remains measured sector RB-utilization percentage at 15/30/60 minutes.

## Relevant tree-model paper

Kolesh and Basikolo, *Enhancing network resource management through machine learning for spatio-temporal beam-level traffic forecasting*, ITU Journal 6(4), 2025, DOI [10.52953/ISPZ6433](https://doi.org/10.52953/ISPZ6433). [Publisher full text](https://www.itu.int/dms_pub/itu-s/opb/jnl/S-JNL-VOL6.ISSUE4-2025-A27-PDF-E.pdf).

Verified from Sections 3–5:

- Operational network: five weeks, hourly observations, 2,880 beams and 30 stations. Target is **DLThpVol traffic volume**; PRB utilization and users are explanatory variables. Predicts Weeks 6 and 11.
- LightGBM/CatBoost use separate near/far-horizon feature sets: lag/rolling/expanding features versus more stable calendar/spatial aggregates. Target receives a square-root transformation and predictions are inverted for evaluation.
- Describes fold-aware categorical target encoding, 10-fold validation stratified by station, Optuna and early stopping. MAE is the primary metric.
- The stated folds contain observations from all stations. This is not a station holdout. Stratification/out-of-fold encoding alone does not establish chronological availability; code was not inspected. Missing-telemetry robustness and our laptop runtime are not established here.

Interpretation: supports trying engineered-history boosted trees. It does **not** prove they outperform neural models on our PRB target. Do not transfer its MAE, square-root transform, feature availability, split protocol or energy/congestion claims to this project. No paper score is our achieved score.

## Official implementation capabilities

| Method | Verified capability | Project implication (proposed) |
|---|---|---|
| Ridge | Linear least squares plus L2 penalty; `alpha` controls regularization. [Official API](https://scikit-learn.org/stable/modules/generated/sklearn.linear_model.Ridge.html) | Transparent first learned baseline. Fit imputing/scaling only on permitted training rows; tune a few alpha values on the later tuning block. |
| HistGradientBoostingRegressor | Histogram tree boosting, native NaN inputs, squared/absolute/quantile losses, bounded iterations/leaves and early stopping. Default automatic early stopping can create an internal split. [Official API](https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.HistGradientBoostingRegressor.html) | First nonlinear comparison; missing inputs need not be zero-filled. Disable internal random validation or supply explicit chronological validation when the installed API supports it. Missing target labels remain excluded. |
| LightGBM | CPU device, `num_threads`, leaf/depth/minimum-leaf controls, `quantile` objective with `alpha`, and quantile metric. [Official parameters](https://lightgbm.readthedocs.io/en/stable/Parameters.html) | Candidate point/quantile tree implementation. Three separate quantile levels can yield a proposed central interval; coverage must be measured and calibrated separately. |

The links describe current stable APIs, not the installed environment. Check `.venv` Python and compatible package versions before choosing installation pins. Do not assume newer fit/validation arguments exist locally.

## Bounded CPU experiment design

This is engineering judgment, not a paper result or training authorization:

1. Reuse the saved 20-series extraction, exact timestamp features and cutoffs. Keep the held-out station excluded from fitting, preprocessing and tuning. Start with utilization history/calendar/missingness only; other KPIs remain unverified.
2. Compare Ridge with alpha 0.1/1/10, one model per horizon. Fit train-only preprocessing; select on tuning only. Run sequentially and cap numerical-library CPU threads at two initially.
3. Then compare HistGradientBoosting with two declared configurations, at most 200 iterations and 15/31 leaves. Use explicit later validation or disable internal early stopping and keep the fixed iteration budget. Check installed-version compatibility first.
4. If justified, try LightGBM with CPU, two threads, at most 300 boosting rounds, 15/31 leaves and chronological early stopping; at most four configurations per horizon. Quantiles 0.05/0.50/0.95 come after point-model review.
5. Record elapsed time, peak RAM, scored coverage and per-series/pooled errors on matched rows. Preserve calibration and final test; do not retune from the already viewed naive test results. Stop and inspect causes if persistence remains stronger. No GPU, large neural search or new dataset is required for these comparisons.

No trained-model winner, speed, memory usage, calibrated coverage or improvement has been measured by this note.

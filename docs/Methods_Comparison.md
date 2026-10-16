# Methods comparison and proposed experiment order

Reviewed 16 October 2026. This stage compares evidence and proposes experiments; it does not train a model. Completed baseline measurements remain in Stage_1_Results.md.

## Our exact task

Use observed historical LTE1800/NR2100 RB-utilization percentages to forecast each station-sector series at t+15, t+30 and t+60 minutes. Keep the included real commercial-network dataset, natural gaps, measured-target provenance, common chronological partitions and separate station holdout. Target units and data caveats come from the included descriptor and saved audits; see [dataset research](Dataset_Research.md).

## Paper comparison

| Paper and reading scope | Data and target | Forecast approach | Match and limit for our project |
|---|---|---|---|
| [Jang et al., IEEE Access 2021](https://ieeexplore.ieee.org/document/9406027/), full-text data description, methods and evaluation text inspected through IEEE | Real measurements from two anonymous operators in Seoul over 38 months, March 2017–April 2020. Monthly samples summarize busy-hour usage in the top 10% of cells. | Fit three parameters to each month's ordered utilization curve; predict those parameters with LSTM/GRU, reconstruct future network summaries. Compare FNN and VAR. | Real RB-usage evidence, but monthly population summaries and month-ahead horizons differ from our 15-minute per-sector task. Do not reorder our sectors into monthly population quantiles or import its reported scores. |
| [Kasuluru et al., IEEE TNSM 2026](https://ieeexplore.ieee.org/document/11418715/), full-text methods and simulation setup inspected through university subscription | Simulated traffic/mobility data; experiment uses coverage and capacity base stations and summed allocated PRBs. | Multivariate LSTM, GPVAR and TFT; 48-hour forecast, 120-hour context, probabilistic outputs for GPVAR/TFT. | Supports investigating uncertainty. Different units, source and horizon; modeled power savings do not establish our energy savings or operational deployment. |
| [Gutterman et al., ACM MobiHoc 2019](https://dl.acm.org/doi/10.1145/3323679.3326521), abstract and references inspected | LTE testbed; REVA, a resource-availability metric for an active bearer. | X-LSTM compared with LSTM and ARIMA. | Resource forecasting precedent. REVA is different from our recorded utilization percentage. Full-text horizon/split/implementation and data reuse remain unchecked. |
| [Kolesh and Basikolo, ITU Journal 2025](https://www.itu.int/dms_pub/itu-s/opb/jnl/S-JNL-VOL6.ISSUE4-2025-A27-PDF-E.pdf), Sections 3–5 checked against publisher full text | Hourly beam traffic volume (DLThpVol); PRB is an input. Five weeks, 30 stations, 2,880 beams. | LightGBM/CatBoost with engineered history/calendar/spatial features. | Supports tree-model candidates but not a PRB-target ranking. Station-stratified folds include all stations; do not copy those as proof of chronological or unseen-station evaluation. |

Jang et al. split earlier and later monthly matrices for training/testing and report the last six months as test months. Their text discusses choosing best hyperparameters from prediction-result tables; a separate tuning/calibration protocol like ours was not established by this inspection. Do not copy that selection procedure. Their metric summarizes multiple frequency bands using bandwidth/coverage weights; our target is already a percentage and should not be divided by bandwidth.

The earlier Scopus search returned 69 documents, and the earlier ACM search returned 14 results. Only the specific records and sections described here and in [University_Library_Review.md](University_Library_Review.md) were inspected. This is a focused review, not exhaustive screening or reproduction of published experiments. Public availability of each paper's underlying dataset/code has not been established here.

## Proposed method ladder — engineering judgment, not paper-proven ranking

| Order | Method | Purpose in our experiment |
|---|---|---|
| Already completed | Persistence and daily seasonal | Minimum comparisons and input-availability reference. |
| 1 | Ridge regression | Determine whether a small learned linear combination of exact historical lags and calendar information improves on the naive forecasts. |
| 2 | HistGradientBoosting | Test whether nonlinear relationships add value at bounded CPU cost. |
| 3 | LightGBM point/quantile models | Compare an efficient boosting implementation, then estimate lower/median/upper outcomes and assess calibration. |
| Optional later | One small GRU or LSTM | Test whether sequential modeling earns its added compute and complexity after the simpler comparisons. |
| Deferred | GPVAR/TFT/X-LSTM | Research leads; adaptation, dependencies and compute need justification before implementation. |

This order is chosen to make comparisons understandable and bounded on an i7-1165G7 with 16 GB RAM and no NVIDIA GPU. It does not assert that Ridge, boosting or a neural model will win. A recent or more complex architecture is not evidence of better performance on this dataset.

Official implementation capabilities and the ITU boosting-paper review are recorded separately in [CPU_Methods_Evidence.md](CPU_Methods_Evidence.md). That evidence should be read alongside this proposal; it does not establish a ranking for our measured PRB task.

## Implemented experiment design

Ridge uses train-only median imputation and scaling with alpha candidates 0.1, 1 and 10. HGB and LightGBM compare two bounded leaf budgets. All models use historical utilization and deterministic calendar inputs, common chronological cutoffs, tuning-only choices and a separate calibration period. Site 53 is excluded from fitting, tuning and calibration. See [project status](Project_Progress.md) for measured results and [development rules](../CONTRIBUTING.md) for invariants. Extra KPI inputs and energy modeling remain excluded.

## Plain-language explanation

Persistence says: “keep the current value.” Ridge asks: “can a learned combination of recent readings do better?” Boosting asks: “do nonlinear patterns help?” Quantiles ask: “what range of utilization might occur?” Neural models are an optional comparison after those questions have been tested.

Serving models were selected using tuning data under the fixed evaluation protocol; final-test results are reported separately.

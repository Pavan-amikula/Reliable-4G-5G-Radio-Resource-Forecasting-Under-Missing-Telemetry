# Real network forecasting: dataset and method review

Research date: 16 October 2026. Prepared for Pavan Amikula.

## Recommendation

Build **Reliable 4G/5G Radio Resource Forecasting Under Missing Telemetry**. The commercial RAN counters in Zenodo Dataset_02 are the leading candidate. The new archive audit found repeated observation keys; observed non-empty utilization rows are unique and can be extracted safely for an initial forecasting experiment. Predict percentage RB utilization 15, 30 and 60 minutes ahead. Use uncertainty intervals, missing-data robustness tests and honest chronological evaluation as the core contribution. Add a separately labelled high-load advisory only if the target contains enough independent high-load episodes.

This is a project recommendation, not a claim of a new algorithm or an already achieved result. No forecasting models were trained for this review. No dataset can yet be certified to satisfy every requirement, especially congestion labels, operational interventions and per-cell energy accounting.

## Access and evidence boundaries

The initial review used public IEEE, ACM, ITU, author/university and dataset sources. Institutional searches and selected publisher full-text inspection are documented in [University_Library_Review.md](University_Library_Review.md). Coverage is focused rather than exhaustive; access limitations are not evidence that a paper or dataset is unavailable.

The original GitHub project's implementation was not independently rerun or audited in this review. Only independently checked statistics are reported as measured findings. The report distinguishes repository documentation, paper findings, any new local data audit and proposed experiments.

## Dataset decision

| Candidate | Verified fit | Main limitation | Decision |
| --- | --- | --- | --- |
| Zenodo commercial RAN, Dataset_02 | Live operational sector counters; 15-minute sampling; LTE 1800 / NR 2100; archive listed at 49.4 MB | Repeated observation keys; irregular coverage; sparse high-load events | Main candidate, conditional on resolving the audit |
| ITU/Zindi beam data | 2,880 beams, 30 stations, five weeks, hourly PRB/traffic/users | Challenge predicts traffic volume; hourly sampling; hidden challenge targets do not provide ordinary public PRB test labels | Separate benchmark |
| Tsinghua NetData | Real 4G/5G reports; explicitly defines PRB usage as a percentage | Public portion covers one weekday and one weekend day; reuse terms should be checked | Secondary cross-sectional experiment |
| DoNext | Real 4G/5G measurement collection; IEEE dataset paper | Device/measurement task differs from continuous station resource-counter forecasting | Consider for a separate throughput/QoS project |

Sources: [Zenodo record](https://zenodo.org/records/17815388), [official README](https://zenodo.org/records/17815388/files/README.md?download=1), [Zindi data description](https://zindi.world/competitions/spatio-temporal-beam-level-traffic-forecasting-challenge/data), [NetData authors' repository](https://github.com/tsinghua-fib-lab/NetData), [DoNext authors' publication page](https://comnets.etit.tu-dortmund.de/newsdetail/donext-an-open-access-measurement-dataset-for-machine-learning-driven-5g-mobile-network-analysis-51675/).

### Commercial RAN counter caveats

The official README preserves missing and zero values, requires RB interpretation alongside configured bandwidth, and locates energy at radio-unit/baseband level. License: CC BY 4.0, with attribution to the descriptor and dataset version. [Official README](https://zenodo.org/records/17815388/files/README.md?download=1).

The downloaded [accepted descriptor](https://www.nature.com/articles/s41597-026-07723-0_reference.pdf), Tables 1, 2 and 4, clarifies that both RB utilization fields are already **percentages**. Dataset_02 configurations use 20 MHz bandwidth. Bandwidth changes the absolute capacity represented by a percentage; it does not require dividing this percentage by bandwidth. The descriptor lists 64 observation days for Dataset_02 and 35 for Dataset_01. Observation days are not equivalent to a continuous recording period.

The descriptor attributes missing utilization generally to little/no traffic and permits zero imputation. It separately warns that simultaneous absent energy and broadly absent KPIs indicate unavailable/non-operational intervals. Therefore distinguish probable inactivity from unavailable telemetry. Preserve the original observations, test the author's rule against other counters, and label inferred zeros separately from measured targets. Never globally replace missing records with zero. Shared hardware energy must not be summed repeatedly across technology rows.

### Benchmark scope

The Zindi challenge forecasts DLThpVol for weeks 6 and 11 from five observed weeks. Its PRB file can support a separately defined PRB task using a chronological split inside the available period, but that is not the official leaderboard task. Its challenge page permits reuse under CC BY-SA 4.0. Do not interpolate hourly data and call the output a measured 15-minute benchmark. [Challenge description and rules](https://zindi.world/competitions/spatio-temporal-beam-level-traffic-forecasting-challenge).

## New archive audit: reproduced results

The archive was downloaded and its MD5 matched the publisher: `7d9c1c019e5d18bf318b4e4ad9393d91`. CSVs were streamed without training a model. The counts below come from the saved independent archive audit.

| Audit item | NR 2100 | LTE 1800 |
| --- | ---: | ---: |
| Raw rows | 1,800,920 | 1,800,920 |
| Unique station-sector-timestamp keys | 722,545 | 722,545 |
| Non-empty utilization records | 690,499 | 643,732 |
| Keys with multiple non-empty utilization values | 0 | 0 |
| All stations / sector groups | 63 / 184 | 63 / 184 |
| Stations / sector groups with observed target | 59 / 174 | 59 / 174 |
| Utilization at least 80% | 143 | 0 |
| Maximum observed utilization | 92.46% | 74.51% |

Both files span 7 February 2025 19:45 UTC to 5 May 2025 07:15 UTC, with 64 distinct recorded calendar dates, not every date in that span. This is the archive-wide coverage; individual series can cover less. Each file contains 722,137 keys represented by multiple rows. There are no identical complete rows. Repeated rows differ in energy counters and often have blank technology fields. The missing equipment identity or export semantics behind those rows are not established by this audit. This differs from the descriptor's assertion that station-sector-timestamp tuples are unique; it should be reported as a reproducible observation, not explained away by inventing identifiers.

The raw blank-target rates (61.66% NR and 64.26% LTE) therefore **are not clean series-level missingness rates**. Blank padded rows inflate their denominators. Non-empty target rows themselves are unique by the observation key, making observed-target forecasting viable. Their absence on the unique grid, and the interpretation of missing intervals, still need a separate policy.

Recommended extraction: retain unique non-empty utilization observations; verify uniqueness for every additional KPI before coalescing; reindex by actual timestamps; retain observation provenance and missingness. Never take an arbitrary first repeated row, average padded rows, sum shared energy, or replace every blank target with zero. Keep ambiguous absent target keys unavailable initially. Compare conservative observed-target evaluation with a separately labelled author-rule inactivity treatment only after reconciling the export structure.

The 143 high readings occur in 15 station-sector groups across 13 stations and form 62 contiguous 15-minute runs. These runs are not necessarily statistically independent and their distribution across future train/calibration/test blocks remains to be checked. An 80% rule is an experimental high-load threshold, not a universal congestion definition.

## Literature evidence

| Paper and evidence read | What it contributes | What to take into this project |
| --- | --- | --- |
| Jang et al., IEEE Access 2021, DOI 10.1109/ACCESS.2021.3073670. ETRI author record and abstract read. | Forecasts real LTE resource-block usage; summarizes upper-tail stations before RNN forecasting | Study high-load behavior separately; do not copy population summaries as per-cell forecasts |
| Raca et al., IEEE INFOCOM Workshops 2023, DOI 10.1109/INFOCOMWKSHPS57453.2023.10226095. Author PDF read. | Compares device/network features for user RB allocation with Random Forest | Test whether historical users, traffic and radio quality add value beyond PRB history |
| Zhang & Patras, ACM MobiHoc 2018, DOI 10.1145/3209582.3209606. Author abstract and university publication record read. | Spatial-temporal neural forecasting on 60-day traffic data | Spatial structure may help, but traffic volume is a different target; use real adjacency or clearly label learned similarity |
| Kolesh & Basikolo, ITU Journal 2025, DOI 10.52953/ISPZ6433. Full PDF read. | LightGBM/CatBoost with engineered temporal and spatial features for beam DLThpVol | Strong justification for efficient boosted-tree candidates; retain our own chronological protocol |
| Kasuluru et al., 2024, arXiv:2407.14400. Full HTML read. | Compares probabilistic PRB models and modeled provisioning/power tradeoffs | Include quantiles, calibration and under/overestimation; do not transfer modeled savings to our network |
| Larumbe-Lizarraga et al., September 2026, arXiv:2609.17297. Indexed author abstract read; full text fetch failed. | Proposes cost-aware DeepAR/TFT quantile training for PRB allocation | Candidate extension only; verify full methodology and code before reproducing |

Primary paper links:

1. [Jang et al., ETRI author record](https://ksp.etri.re.kr/ksp/article/read?id=63890).
2. [Raca et al., university-hosted author PDF](https://cora.ucc.ie/server/api/core/bitstreams/1ddfe779-cc3e-498d-9921-f9f755c3e702/content).
3. [Zhang & Patras, author preprint](https://arxiv.org/abs/1712.08083) and [University of Edinburgh publication record](https://www.research.ed.ac.uk/en/publications/long-term-mobile-traffic-forecasting-using-deep-spatio-temporal-n/).
4. [Kolesh & Basikolo, ITU publisher PDF](https://www.itu.int/dms_pub/itu-s/opb/jnl/S-JNL-VOL6.ISSUE4-2025-A27-PDF-E.pdf).
5. [Kasuluru et al., original preprint](https://arxiv.org/html/2407.14400v1).
6. [Larumbe-Lizarraga et al., preprint record](https://arxiv.org/abs/2609.17297).

Critical reading matters: Raca et al. use **ns-3 simulation**, not a public real-operator dataset. Their horizon is five seconds and target is user allocation, unlike our sector forecasts. The ITU paper's target is traffic volume and its challenge horizons differ from ours. The 2024 uncertainty paper evaluates a 24-hour forecast with ten weeks of historical data and an analytical power model; it does not establish our future performance. The 2026 work is a preprint here, not confirmed peer-reviewed publication. Published scores across these tasks cannot rank models for our data.

The Frontiers 2025 [GRU multi-task beam forecasting paper](https://www.frontiersin.org/journals/communications-and-networks/articles/10.3389/frcmn.2025.1658461/full) is another optional comparator. Check its exact architecture before calling its XGBoost and linear columns standalone baselines: its hyperparameter table embeds GRU components. Its point-forecast experiments do not establish calibrated uncertainty.

## Proposed research question

**Can a compact quantile boosting model produce useful multi-horizon resource forecasts, with reliable intervals and robust behavior when network telemetry is incomplete?**

Three separable hypotheses:

1. Historical covariates improve forecasting over persistence and seasonal baselines.
2. Calibration improves interval coverage/width tradeoffs on later weeks.
3. Missingness indicators, recency features and a fallback policy reduce failures under realistic telemetry gaps.

These are testable hypotheses, not guaranteed outcomes or claims of scientific novelty. Reliability under incomplete operational counters is a coherent extension beyond a simple synthetic regression demo.

## Experiment design

### Forecast definition

For each unique technology/band/station/sector series, issue forecasts at the end of an observed interval. Target the recorded value at t+15, t+30 and t+60 minutes. Use completed measurements available at issuance, allowing for any export delay. Explain whether timestamps mark interval starts or ends. Separate direct models per horizon initially.

Use exact timestamp joins or reindex to a complete 15-minute grid before making lag features. A one-row shift after dropping missing records may represent hours rather than 15 minutes. Score measured targets separately from author-rule inferred inactive zeros; do not silently call inferred zeros ground truth. Unavailable target labels remain excluded, with exclusion rates reported. Forward fills, if used for inputs, must be bounded, causal and accompanied by age/missingness flags. Never fill missing ground truth to improve the score.

### Features

- Available PRB/RB history at issuance and lags 15/30/60 minutes, plus 24 hours and 7 days where supported.
- Past-only rolling averages, variability, maxima and slope over 1/4/24 hours.
- Historical users, traffic, CQI and MIMO counters when definitions and reporting timing are confirmed.
- Hour/day cyclical features, technology/band and documented bandwidth.
- Missing flags, time since last valid reading and recent reporting completeness.

Ablate features in groups: PRB history; calendar; users/traffic; radio quality; missingness/recency; spatial aggregates. Learn spatial similarity on training history only. Do not describe station numbers as geographic coordinates or invent a physical neighbor graph.

### Models in order

| Stage | Model | Purpose |
| --- | --- | --- |
| 1 | Latest available observation and daily/weekly seasonal naive | Operationally meaningful minimum comparisons, with explicit stale-data policies |
| 2 | Ridge regression with causal preprocessing | Simple learned baseline |
| 3 | HistGradientBoosting | Practical first nonlinear CPU model |
| 4 | LightGBM point and quantile models | Main candidate for speed, covariates and prediction intervals |
| 5, optional | Small GRU or TCN | Test whether sequence learning is worth additional cost |
| 6, optional | DeepAR | Literature-aligned probabilistic comparison if earlier results justify it |

LightGBM officially supports CPU execution, quantile objectives, thread limits and bounded tree complexity. These are implementation capabilities, not proof that it will win. [Official parameter documentation](https://lightgbm.readthedocs.io/en/stable/Parameters.html). The scikit-learn [lagged forecasting example](https://scikit-learn.org/stable/auto_examples/applications/plot_time_series_lagged_features.html) supports chronological evaluation rather than shuffled row splits.

### Splits and leakage control

Use common chronological cutoffs across all series. Allocate earlier weeks to training, subsequent weeks to tuning, another later block to calibration and a final untouched test block. Select exact dates after continuity inspection. Use expanding-window validation inside development data, keeping labels within each allowed period. Purge training origins whose future targets extend into the next partition. Account for delayed feedback when updating calibration or retraining.

Keep a second test with entire stations excluded from all training/tuning/calibration. Separate its results from future-time testing on familiar stations. Fit imputers, scalers, station encodings, similarity graphs and thresholds using permitted development data only. Report the cohort selection rule and excluded stations. An ID-heavy model should have an explicit cold-start alternative.

### Uncertainty and decision usefulness

Start with 0.05/0.50/0.95 quantiles for a proposed central 90% interval. Check crossings, interval width, pinball loss and empirical coverage by horizon, cell and load range. Calibrate on later development observations. Standard conformal methods rely on assumptions that time dependence can violate; no automatic per-cell or conditional 90% guarantee is claimed.

Sources: Romano et al., [Conformalized Quantile Regression, NeurIPS 2019](https://proceedings.neurips.cc/paper/2019/hash/5103c3584b063c431bd1268e9b5e76fb-Abstract.html); Gibbs & Candes, [Adaptive Conformal Inference Under Distribution Shift, NeurIPS 2021](https://proceedings.neurips.cc/paper/2021/hash/0d441de75945e5acbc865406fc9a2559-Abstract.html). Online methods must update only after the forecast's outcome becomes available. Long-run coverage is different from coverage in every station and every high-load interval.

A later decision experiment can compare asymmetric under/overprediction penalties over several declared cost ratios. Treat these as **simulated resource-pressure proxy costs** unless actual operator costs and capacity actions are available. Observed utilization is served load and cannot by itself identify unmet demand above capacity or show the causal impact of adding resources. In a real allocation experiment, costs, capacity constraints, queueing and service-level effects need separate modeling.

### Metrics and stress tests

- MAE/RMSE in documented original counter units, and percentage points only after valid percentage normalization.
- Skill relative to each naive baseline on identical scored rows. If baseline MAE is positive, skill = 1 - model MAE / baseline MAE.
- Macro-average per series alongside pooled errors; high-load and sparse-series errors separately.
- Interval coverage, width and pinball loss by horizon and subgroup.
- Latency, batch size, peak RAM and training time on the actual laptop.
- Natural gap analysis plus simulated isolated drops and contiguous outages. Label simulated corruptions clearly; do not remove natural missingness.
- Paired uncertainty estimates using station/day blocks rather than assuming every row is independent.

If high-load advisories are feasible, count distinct contiguous episodes, precision/recall, false alerts per cell-day and first-warning lead time. Tune thresholds and alert cooldowns on development data. If positive episodes are too few, report counts and uncertainty, and retain forecasting as the main task. A training-percentile exceedance can be called an elevated-load event, not proven congestion. Confirmed congestion needs service evidence such as latency, throughput degradation or queueing.

## Laptop and demonstration scope

Start with approximately 10-20 well-observed station-sector series, selected only from development data, and a bounded row budget. Use float32 where appropriate, compact columns and cached feature tables. Limit CPU threads, train sequentially, use early stopping and cap model trials. Benchmark memory before scaling. There is no need to download foundation-model weights or a 700 MB archive before the smaller candidate is understood.

The finished demonstration can include a prediction API and dashboard with historical replay: actual counters, horizon forecasts, intervals, freshness indicator, fallback state and error monitoring. Save data hashes, package versions, split manifests and predictions. Historical replay is not a live operator deployment. Explanations of model drivers do not establish root causes.

## Acceptance gates before implementation

1. Resolve repeated keys and any conflicting measurements before engineering forecast rows. Percentage units are established; retain configuration bandwidth for interpretation.
2. Verify time range, per-series cadence, duplicate keys, missing targets and long gaps.
3. Check whether different technologies are paired observations and how shared equipment counters are represented.
4. Reserve enough later data for calibration and final testing; verify independent high-load episodes before adding warnings.
5. Train the naive baselines first. If they already dominate, inspect label timing, data continuity and available signal before spending on larger models.
6. Publish measured results and limitations. Do not insert expected improvements into a resume as completed results.

## Reproducible search continuation through BTH

The following are proposed searches to execute for broader literature coverage. They were **not** all run as part of this review.

```text
TITLE-ABS-KEY(("physical resource block" OR "PRB utilization" OR "resource block usage") AND (forecast* OR predict*) AND (dataset OR measurement OR "real network"))

TITLE-ABS-KEY(("radio access network" OR "cellular traffic") AND ("probabilistic forecasting" OR quantile OR conformal OR "missing data"))
```

In IEEE/ACM, search the quoted paper titles and follow their dataset/code links. Record target, units, observation length, forecast horizon, split protocol, feature availability, baselines, calibration and reuse terms for each paper. A paper appearing in a database is not evidence of a downloadable dataset, nor that its evaluation can be reproduced.

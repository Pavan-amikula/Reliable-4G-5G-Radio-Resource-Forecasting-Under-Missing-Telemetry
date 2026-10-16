# Step 2: turn measurements into input-and-answer tables

The table-building stage creates exact-time training examples without fitting models or preprocessing statistics.

## What changed and why

`scripts/build_supervised.py` reads the saved history features and looks up each future answer in the clean observed database using the complete technology/band/station/sector key and exact timestamp. It does not reopen the raw archive or repeat audits.

Output folder:

```text
data/processed/supervised_v1/
├── development/
│   ├── train_15m.csv.gz
│   ├── train_30m.csv.gz
│   ├── train_60m.csv.gz
│   ├── tuning_15m.csv.gz       (also 30m and 60m)
│   ├── calibration_15m.csv.gz  (also 30m and 60m)
│   └── test_15m.csv.gz         (also 30m and 60m)
├── station_holdout/
│   └── test_15m.csv.gz         (also 30m and 60m)
└── summary.json
```

`.csv.gz` is a compressed CSV table. `summary.json` records file hashes, source hashes, eligible/excluded counts, missing-input counts, input columns and example rows. A missing summary means construction did not finish successfully; inspect any partial directory before reuse.

## One actual example, not invented numbers

LTE 1800, Site 16, sector 1, on 7 February 2025, UTC:

| Input timestamp | Input value |
|---|---:|
| 21:45 (forecast origin) | 27.10% |
| 21:30 (15-minute lag) | 29.90% |
| 21:15 (30-minute lag) | 28.33% |
| 20:45 (60-minute lag) | 42.24% |

Answer: the observed utilization at **22:00 was 25.86%**. This value is stored as `target_utilization_pct`, the label to learn/predict, never as an input.

The previous-day and previous-week lags are missing for this example. They remain blank, with flags set to 1. No value was fabricated. Later Ridge preprocessing must learn any replacement values from training data alone.

Additional inputs include the count/mean of available readings in the trailing four clock slots ending at the origin, reading age, and cyclic encodings of UTC time of day and weekday. Calendar encodings require no fitted statistics. The last-hour mean does not include the answer or any reading after issuance.

## Measured row counts

| Horizon | Train | Tuning | Calibration | Familiar-station test | Holdout-station test |
|---|---:|---:|---:|---:|---:|
| 15 min | 31,516 | 25,340 | 20,847 | 13,997 | 3,429 |
| 30 min | 31,409 | 25,236 | 20,764 | 13,953 | 3,413 |
| 60 min | 31,266 | 25,103 | 20,642 | 13,896 | 3,389 |

Total: 284,200 horizon-specific examples across 15 tables. The same origin can contribute to multiple horizons; these are not 284,200 independent measurements. They derive from the same 114,460 observed measurements used in Stage 1.

## Rules applied

- A current observation and exact future observed label are required. This is the same current-input availability policy as persistence; it does not yet test prediction during missing-current telemetry outages.
- Missing history lags stay blank and have explicit indicators. Observed zero remains a valid value.
- Training labels cannot reach or cross the training end. The same rule applies to each partition's end.
- History before a partition's start is allowed because it is already available when that forecast is issued.
- Site 53 has final-test tables only. Its history may be used to make its forecasts, but no holdout rows enter fitting, preprocessing, tuning or calibration.
- Identity/timestamp/role/split fields are metadata. Only the declared `input_columns` in the summary can enter the initial model. The future timestamp and label are never inputs.
- No imputing, scaling, fitted encoding or model selection was performed here. Final-test rows are assembled by the fixed protocol; their target values were not used to choose features or settings.
- The inherited assumption remains that a completed counter is available at its recorded UTC timestamp. Interval semantics/export delay are not yet confirmed.

Validation: 13 protocol tests passed. A separate artifact check verified every one of the 284,200 saved rows against observed targets, exact historical lags, missing-lag flags, partition boundaries and station roles. All retained counts match the saved persistence baseline's available-row counts. Final learned-model comparisons with daily seasonal must additionally use the common scored subset.

## Reproduction

In a separate fresh workspace, run:

```powershell
.\.venv\Scripts\python.exe scripts\build_supervised.py
```

The builder prints partition counts for each horizon and the summary path. It rejects an existing output folder. See [Reproduce.md](Reproduce.md) for the complete dependency and experiment sequence.

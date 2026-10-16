# Reliable 4G/5G Radio Resource Forecasting Under Missing Telemetry: start here

## What did we build?

A program that uses past 4G/5G radio-resource readings to predict usage 15, 30 and 60 minutes later. It also gives a lower and upper estimate and handles missing recent readings. You can see the results in a local browser screen.

**Current position: the working local prototype is complete, including its screen.** Initial experiments and checks are saved. This is a small historical study, not a live network deployment.

## The project in six steps

```text
1. Original measurements      data/raw/Dataset_02.zip
              ↓ extract genuine nonempty utilization readings
2. Clean observations        data/processed/observed_v1.sqlite
              ↓ match exact past times to later measured answers
3. Training examples         data/processed/supervised_v1/
              ↓ train and compare on separate time periods
4. Saved models + results    outputs/ridge_v1/, hgb_v1/, lightgbm_v1/, intervals_v1/
              ↓ load the chosen models; accept past readings only
5. Prediction service        networkprb/inference.py + api.py
              ↓ show predictions next to later actual answers
6. Browser screen            networkprb/static/ + replay.py
```

## Which dataset?

The included **Dataset_02**, commercial radio-access-network measurements published by Lehoczky and colleagues. The original archive is `data/raw/Dataset_02.zip`. We did not invent the usage values.

We use **4G LTE at 1800 MHz and 5G NR at 2100 MHz**, sampled on a 15-minute clock. Usage is already a percentage. Our initial CPU experiment uses 114,460 observed values across 20 technology/station/sector series from five stations. Missing values remain missing; repeated padded raw rows are not treated as extra usage readings.

Four stations supply development data. **Site 53 is excluded from training, model selection and range adjustment**, then used to check performance on a different station. This does not prove that performance will hold at every new station.

## Which methods?

| Method | Meaning | Its job |
|---|---|---|
| Persistence | Assume the latest usage stays the same | Simple comparison rule |
| Daily seasonal | Reuse the reading from the same time yesterday | Another comparison rule |
| Ridge | Learn a weighted combination of past readings | First learned model |
| HistGradientBoosting (HGB) | Learn a sequence of small decision trees | Selected point prediction for 4G and 5G 15/30-minute forecasts |
| LightGBM | Another efficient implementation of boosted trees | Selected 5G 60-minute point prediction and all lower/upper range models |

Choices were made using the tuning period, not by picking whichever scored best on the final test. Range adjustments use another separate period, called calibration. The final test period is 26 April–5 May 2025. Research notes describe the original design; experiment-specific reports record the methods and measurements from each run.

## Read one result

For the familiar-station, matched 4G 60-minute comparison, the average absolute prediction error was **5.002 percentage points for Ridge** and **4.432 for HGB**. “Average absolute error” means: calculate the distance between every prediction and actual answer, then average those distances. Lower is better. That improvement is **0.570 percentage points**; it does not mean every prediction improved. See `outputs/hgb_v1/Results.md` for populations and other comparisons.

## Use the screen

Open http://127.0.0.1:8765 while the local service is running. Choose a sector and recorded time. The cards show predictions and later actual readings. See [the screen walkthrough](Dashboard_Step.md).

For a restart or another computer, use [the setup guide](Reproduce.md).

## What is checked, and what remains?

The existing suite has 41 passing checks covering time alignment, exclusion of future inputs, split boundaries, missing readings and serving behavior. Saved experiment checks, artifact fingerprints and runtime measurements are included. The final integrity check is `outputs/project_check_v1/verification.json`.

The initial local prototype is complete. Possible separate extensions include more stations, another dataset and actual live counter integration. High-load warnings need more suitable examples: this selected final-test cohort contains no readings at or above 80%. We have not demonstrated energy savings, guaranteed forecast ranges or live network operation.

## Source and credit

Dataset: Lehoczky et al., *Performance Management Counters from Live 5G, 4G and 2G Radio Access Network*, [Zenodo Dataset_02 record](https://doi.org/10.5281/zenodo.17815388), CC BY 4.0. [Data descriptor](https://doi.org/10.1038/s41597-026-07723-0). We extracted a subset and derived forecasting tables; preserve the original attribution when sharing these derivatives. The publisher's data license is not a license declaration for this project's original code.

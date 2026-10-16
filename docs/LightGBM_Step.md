# LightGBM comparison

LightGBM was evaluated using the same inputs, time partitions and scored-row rules as the earlier models.

## 1. What were we trying to do?

We already had a model that learned rules from past readings. We tested a second implementation, LightGBM, to see whether its predictions were closer to the actual readings.

We asked it the same questions: predict each sector's resource use 15, 30 and 60 minutes later. It received the same historical input columns and the same training dates. We trained separate 4G and 5G models. It never received final-test answers during training or setting selection.

## 2. What did we find?

For 4G one hour ahead, on matching final-period rows from familiar stations:

| Model | Average distance from the actual reading |
|---|---:|
| Ridge: the first learned model | 5.00 percentage points |
| Earlier tree model (HistGradientBoosting) | 4.43 percentage points |
| New LightGBM model | 4.47 percentage points |

Lower is better. So LightGBM was slightly worse in this comparison. At 15 minutes ahead, LightGBM was slightly better: about 3.42 versus 3.43. The differences between the two tree models are small. A new model does not automatically give better forecasts. We have not established a statistically significant difference.

What does "4.47 percentage points" mean? For one example, predicting 44.47% when the actual reading is 40% gives a distance of 4.47. Our reported figure averages the distance across many forecasts; it does not mean every forecast misses by exactly 4.47, or that errors are bounded by that amount.

## 3. How are settings and model candidates chosen?

We keep an earlier period for comparing settings, called the tuning period. The final test is only for reporting later performance. Of the models compared, the earlier tree model has the lowest tuning error in five technology/horizon combinations; LightGBM has the lowest in the 5G 60-minute combination, by a very small margin. This is a tuning-based point-forecast candidate list, not a universal ranking or a claim about prediction intervals.

## 4. What files did this step create?

| File | Meaning |
|---|---|
| `scripts/train_lightgbm.py` | The instructions Python executes to train and compare LightGBM |
| `outputs/lightgbm_v1/Results.md` | Full readable comparison with every earlier method |
| Six `.joblib` files in that folder | The saved models, so they can be loaded without training again |
| `forecasts.csv.gz` | A compressed table of predictions next to actual readings |
| `tuning_trials.json` | Results of the small setting comparison |
| `selection.json` | Settings fixed before reading final-test answers |
| `metrics.json` | Detailed error measurements |
| `coverage.json` | How many questions could be scored |
| `run_manifest.json` | Software versions, timing and file fingerprints |
| `validation.json` | Checks performed on the saved results |
| `requirements-ml-lock.txt` | Installed package versions, now including LightGBM 4.7.0 |

The training/comparison script finished in 14.9 seconds, using CPU with two numerical threads. This timing is for this run; peak memory is not yet measured. Nineteen code checks passed. Separate saved-result validation checked all 127,756 forecast rows, reproduced predictions from saved models and recomputed 1,080 per-sector error groups. Earlier datasets, model results and audits were preserved.

## Prediction ranges and serving

LightGBM quantile models and separate calibration are documented in [Forecast_Ranges_Step.md](Forecast_Ranges_Step.md). Missing-input checks, reliability measurements and the local API/dashboard reuse frozen artifacts; see [project status](Project_Progress.md). No live network control or energy savings are demonstrated.

# We added a range to our forecasts

The saved experiment evaluates calibrated prediction ranges for each technology and horizon.

## What our system can now return

Before: one predicted utilization value. Now: that prediction plus a lower and upper estimate. The existing point forecast remains from the model chosen on earlier tuning data; separate models estimate the bounds and a middle value.

## One actual saved forecast

This is the first saved 4G 60-minute familiar-station test example, not an invented number or a selected best case. Site 16, sector 1, 26 April 2025, UTC:

| Item | Value |
|---|---:|
| Forecast issued | 00:00 |
| Time being predicted | 01:00 |
| One-number forecast | 16.91% utilization |
| Lower end of adjusted range | 10.34% |
| Upper end of adjusted range | 26.43% |
| Actual reading later observed | 13.78% |

The actual 13.78% was inside 10.34%â€“26.43%. That is one successful inclusion, not proof that every range works.

## How often did the ranges contain actual readings?

For familiar stations in the later final-test period:

| Network | How far ahead | Actual readings inside after adjustment |
|---|---:|---:|
| 4G | 15 minutes | 91.2 out of 100 |
| 4G | 30 minutes | 90.8 out of 100 |
| 4G | 60 minutes | 90.7 out of 100 |
| 5G | 15 minutes | 91.2 out of 100 |
| 5G | 30 minutes | 91.7 out of 100 |
| 5G | 60 minutes | 91.3 out of 100 |

These decimals summarize many readings, not literal groups of 100. This fraction is called **coverage**. The goal was about 90 out of 100. These figures use all eligible observed-current/observed-future rows, not just the smaller subset where yesterday's seasonal prediction was also available.

For 4G one hour ahead, coverage rose from 83.8 out of 100 before adjustment to 90.7 after adjustment. Average range width increased from 15.78 to 18.11 percentage points. Width is upper minus lower: 30%â€“50% has width 20 percentage points. A wider range can include more outcomes but is less precise.

At the station excluded from training and calibration, measured coverage ranged from 92.7% to 94.9% across the six groups. Full results and widths are in `outputs/intervals_v1/Results.md`. These results do not guarantee the same behavior in another station or time period.

## How we built and checked them

1. Trained lower, middle and upper models on training data. These are technically 5th, 50th and 95th quantiles.
2. Chose between two small settings using only the earlier tuning period. Final-test and calibration answers were excluded from that choice.
3. Used the reserved calibration period to calculate a fixed widening amount for each network/horizon. This adjustment is called **calibration**. No held-out station rows were used.
4. Saved those amounts before reading final-test data. No test answers adjusted them.
5. Measured inclusion and width on final-test readings; saved results by sector and fixed load bands too.

Readings next to one another are related and conditions can change. This procedure does not promise 90% coverage at every sector or future day. We measured historical behavior, not future certainty. See [reliability checks](Reliability_Step.md) and [missing-input experiments](Missing_Readings_Step.md) for subsequent evaluations.

## Which files were created?

| File | Why it exists |
|---|---|
| `scripts/train_intervals.py` | Trains bounds, adjusts them using calibration, evaluates later data |
| `scripts/validate_intervals.py` | Reproduces saved predictions and checks corrections, times and roles |
| `tests/test_intervals.py` | Checks calculations on small known examples |
| `outputs/intervals_v1/Results.md` | Full readable results |
| 18 `.joblib` files in that folder | Saved lower/middle/upper models |
| `selection.json` and `tuning_trials.json` | Settings chosen before calibration |
| `calibration.json` | Widening amounts fixed before final testing |
| `forecasts.csv.gz` | Each prediction, range and actual answer |
| `metrics.json` | Inclusion rates, widths and error measurements |
| `crossings.json` | Unordered quantile counts; a frozen sorting rule repairs these |
| `coverage.json` | Number of eligible forecast questions with ranges |
| `run_manifest.json` | Software versions, timing, file fingerprints and rules |
| `validation.json` | Evidence of saved-output checks |

The full script took 28.5 seconds with two CPU threads. Peak memory was not measured. All 24 code tests passed. Validation reproduced 114,330 saved forecast rows, recomputed calibration amounts, verified point predictions, checked 348 range-summary groups and recorded output fingerprints. Previous artifacts were preserved.

## Related evaluation

[Missing-input experiments](Missing_Readings_Step.md) test simulated outages and natural gaps separately, preserving original future answers.

Method sources: [Conformalized Quantile Regression](https://papers.nips.cc/paper_files/paper/2019/hash/5103c3584b063c431bd1268e9b5e76fb-Abstract.html) and [LightGBM quantile support](https://lightgbm.readthedocs.io/en/stable/Parameters.html). Our implementation only widens bounds and clips to physical 0â€“100%; chronological dependence prevents assuming the standard exchangeability guarantee.

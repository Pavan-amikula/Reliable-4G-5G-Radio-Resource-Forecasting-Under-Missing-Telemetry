# What happens when readings disappear?

No model was retrained. No original measurements or future answers were changed. These are historical replay stress tests, not real outage incidents or a validated live operating policy.

## Three paired input conditions

- Clean: keep original history and originally observed-current forecast questions.
- Artificial 10% drops: hide roughly one in ten history readings; recompute every dependent feature.
- Artificial one-hour gaps: hide four consecutive clock slots once per UTC date for each series.

Natural missing-current origins are a separate population below. They cannot be directly ranked against the paired synthetic rows. Missing future answers are never scored; grid and exclusion counts are in populations.json.

## Average prediction error for familiar stations

The table deliberately shows the unrestricted frozen model first: it attempts predictions even with missing inputs. Lower error is better. Inside-range rate means how often the actual answer falls inside the previously calibrated range; those ranges were not recalibrated for outages.

| Network | Ahead | Input condition | Questions | Average error (percentage points) | Actual readings inside range |
|---|---:|---|---:|---:|---:|
| 4G | 15 min | Original history | 6,859 | 3.393 | 91.2% |
| 4G | 15 min | Artificial 10% drops | 6,859 | 3.897 | 87.6% |
| 4G | 15 min | Artificial one-hour gaps | 6,859 | 3.656 | 88.9% |
| 4G | 30 min | Original history | 6,823 | 3.967 | 90.8% |
| 4G | 30 min | Artificial 10% drops | 6,823 | 4.195 | 89.2% |
| 4G | 30 min | Artificial one-hour gaps | 6,823 | 4.109 | 89.3% |
| 4G | 60 min | Original history | 6,782 | 4.396 | 90.7% |
| 4G | 60 min | Artificial 10% drops | 6,782 | 4.544 | 90.3% |
| 4G | 60 min | Artificial one-hour gaps | 6,782 | 4.508 | 90.2% |
| 5G | 15 min | Original history | 7,138 | 1.335 | 91.2% |
| 5G | 15 min | Artificial 10% drops | 7,138 | 1.462 | 89.9% |
| 5G | 15 min | Artificial one-hour gaps | 7,138 | 1.397 | 90.5% |
| 5G | 30 min | Original history | 7,130 | 1.563 | 91.7% |
| 5G | 30 min | Artificial 10% drops | 7,130 | 1.609 | 91.1% |
| 5G | 30 min | Artificial one-hour gaps | 7,130 | 1.601 | 91.2% |
| 5G | 60 min | Original history | 7,114 | 1.707 | 91.3% |
| 5G | 60 min | Artificial 10% drops | 7,114 | 1.776 | 91.8% |
| 5G | 60 min | Artificial one-hour gaps | 7,114 | 1.723 | 91.1% |

## Fixed fallback rule tested

With a fresh current reading, return the model forecast/range. If it is missing but the last reading is at most 60 minutes old, return that last reading as a clearly labeled stale estimate and withhold the range. If older, return no estimate. This cutoff was declared before test scoring, not optimized from the test results. It is an illustrative policy, not proof of the safest or best action.

Withholding an interval reduces availability; it does not prove the remaining intervals are calibrated. Missing history can still affect fresh-current forecasts. Do not compare errors of policies on differing row subsets without also reporting availability.

## Naturally missing-current origins only

| Station group | Network | Ahead | Observed future answers | Stale estimates returned | No point estimate |
|---|---|---:|---:|---:|---:|
| development | 4G | 15 min | 43 | 27 | 16 |
| development | 4G | 30 min | 71 | 40 | 31 |
| development | 4G | 60 min | 97 | 45 | 52 |
| station_holdout | 4G | 15 min | 14 | 5 | 9 |
| station_holdout | 4G | 30 min | 26 | 8 | 18 |
| station_holdout | 4G | 60 min | 42 | 10 | 32 |

## Files

- `policy.json`: outage schedules, thresholds and population rules declared before scoring.
- `forecasts.csv.gz`: original future answers, stressed predictions, age, fallback/abstention and optional ranges.
- `metrics.json`: per-series and pooled errors, point/range availability and inclusion rate for both strategies, with station holdout separate.
- `populations.json`: clock origins, missing-answer exclusions and boundary purges.
- `masks.json`: measured hidden-history counts; no raw file mutation.
- `run_manifest.json`: timing, source/output hashes, versions and frozen rules.

Measured full script time: 17.2s; two numerical threads. Peak process memory not measured.

Next: quantify uncertainty across station/day blocks and benchmark memory/latency; then implement the prediction interface and historical replay screen. A degraded range must not be presented as reliably 90% during outages.

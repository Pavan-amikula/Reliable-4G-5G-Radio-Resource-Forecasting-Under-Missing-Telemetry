# What happens when readings disappear?

Completed on 17 October 2026 using frozen models and preserved original measurements.

## 1. What question did we ask?

Our model uses past readings to forecast future utilization. What happens if some of those past readings never arrive?

We copied the input history and tried these conditions:

- Original history, including its natural missing values.
- Artificially hide approximately one in ten recorded history readings.
- Artificially hide one complete hour per day for each station/sector.

The latter two are **simulated outages**, not measured real outage incidents. We kept the same real future answers for all three. When a historical reading was hidden, we also recomputed the lag values, recent averages, missing flags and reading age that depended on it. We did not replace missing readings with zero.

## 2. What happened to forecasts?

Example: familiar 4G stations, forecasting 15 minutes ahead, using exactly the same 6,859 forecast questions:

| History condition | Average distance from actual reading | Actual readings inside predicted range |
|---|---:|---:|
| Original history | 3.39 percentage points | About 91 out of 100 |
| Roughly 1 in 10 history readings hidden | 3.90 percentage points | About 88 out of 100 |
| One hour of readings hidden each day | 3.66 percentage points | About 89 out of 100 |

Lower average error is better. These averages include all forecast times in each scenario, including times outside the scheduled missing hour. They are not an error estimate limited to the outage itself.

The important finding is that missing readings made the forecasts worse. A model can accept blank inputs and still become less accurate. The ranges calibrated under ordinary inputs did not retain the same inclusion rate under all artificial outages.

These rows include every observed-current/observed-future question available before artificial masking. Earlier multi-model comparisons also required yesterday's reading, giving a slightly smaller subset. That is why the original-history error here can differ slightly from earlier tables.

## 3. What fallback did we test?

Before scoring the test data, we fixed this rule:

1. Latest current reading available: return the model prediction and range.
2. Current reading missing, but last known reading at most one hour old: return that last reading, labeled **stale estimate**; do not return a prediction range.
3. Last known reading older than one hour, or no known history: return **no estimate**.

“Stale” means old information. “No estimate” means the system declines to provide a number. The one-hour limit is an illustrative choice, not a proven safest operating threshold. We did not search test answers for a better limit.

For the artificial 10% drops in the 4G 15-minute example:

- 6,162 questions had a fresh current reading.
- 696 used the stale-reading fallback.
- 1 received no point estimate.
- Ranges were withheld for the 697 questions without a fresh current reading.

On the same 6,858 questions where the fallback returned a number, its average error was 3.54 percentage points versus 3.90 for the unrestricted model. This is a descriptive result for this fixed experiment. The comparison uses identical rows; availability is still reported separately. It does not prove this policy is universally best.

Fresh-current forecasts can still have missing older inputs. Withholding ranges only when the current reading is missing does not guarantee that the remaining ranges stay calibrated.

## 4. What about naturally missing readings?

We checked these separately, without injecting artificial drops. Only origins with an observed future answer can be scored. For familiar 4G stations, 15 minutes ahead, there were 43 such missing-current origins: 27 received a stale estimate and 16 received no estimate.

This is a different, small population. Do not directly compare its error with the synthetic tables. Entire gaps with no observed future answer cannot tell us forecasting accuracy; those exclusions are counted. No eligible natural missing-current cases were found for 5G in the final-period population used here; that is not proof that 5G has no gaps elsewhere.

## 5. What files were created?

| File | Purpose |
|---|---|
| `scripts/stress_telemetry.py` | Hide history in memory, recompute inputs, run frozen models and test the fallback |
| `scripts/validate_stress.py` | Reproduce predictions, labels, age and fallback decisions; verify original files |
| `scripts/summarize_stress.py` | Compare fallback and unrestricted errors on identical returned-answer rows |
| `tests/test_telemetry_stress.py` | Check future exclusion, masking, stale-value cutoffs and feature recomputation |
| `outputs/telemetry_stress_v1/Results.md` | Full readable results |
| `policy.json` | Schedules and decision rules saved before test scoring |
| `forecasts.csv.gz` | Each actual answer, stressed prediction, range and fallback state |
| `metrics.json` | Errors, range inclusion, availability, station and sector results |
| `populations.json` | Counts of eligible times, absent future answers and boundary exclusions |
| `masks.json` | Counts of hidden historical readings |
| `paired_fallback.json` | Error comparisons on identical returned-answer rows |
| `run_manifest.json` and `validation.json` | Timing, versions, hashes and validation evidence |

The main experiment ran in 17.2 seconds with two numerical threads. Peak process memory has not been measured. All 29 code tests passed. The saved-output validator reproduced 156,524 rows and checked 474 metric groups, unchanged real future answers, clean predictions matching the earlier experiment, matching synthetic populations, and original artifact hashes.

## Related evaluation

[Reliability checks](Reliability_Step.md) report station/day variation, prediction speed, process memory and high-load support.

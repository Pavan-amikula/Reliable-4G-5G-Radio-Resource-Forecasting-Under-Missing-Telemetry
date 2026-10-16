# Are the results consistent, and can the laptop run predictions?

Completed on 17 October 2026 using frozen models; no retraining was performed.

## 1. Does the improvement depend on one lucky station or day?

Many readings come from the same sector on the same day, so they are related. Treating every reading as a separate independent experiment would make the evidence look stronger than it is.

We repeatedly formed groups from entire stations and pairs of consecutive days, preserving all sector readings inside those groups. We compared the saved model forecasts with the simple rule “repeat the latest observed reading” on the same questions.

For the familiar stations, the selected model stayed better than that simple rule across the exploratory ranges from these grouped checks, at all three horizons for both 4G and 5G.

For the station excluded from training, the 4G improvement was less certain: the exploratory ranges included cases with no improvement. We cannot claim the same improvement at every unseen station.

There are only four familiar stations, one excluded station and ten final-period calendar dates. Reusing groups cannot create new independent stations or days, and the two-day grouping does not prove independence. These checks support cautious conclusions about this cohort; they are not a universal accuracy guarantee or a formal significance test.

## 2. How fast is one forecast request?

One measured call rebuilt the historical input features and produced all three forecast times—15, 30 and 60 minutes ahead—plus their ranges, for one sector.

| Network | Typical measured time |
|---|---:|
| 4G | About 10 milliseconds |
| 5G | About 7 milliseconds |

A millisecond is one-thousandth of a second. Around 10 milliseconds is about one-hundredth of a second.

These numbers come from repeated warmed-up calls, not a single best case. The 95th-percentile measured time was about 12 milliseconds for 4G and 10 milliseconds for 5G. That means about 95% of the measured calls were no slower than those values in this small run.

The models were already loaded, and historical readings were already in memory. We did not include reading files from disk, serving HTTP requests, transferring data over a network, drawing the screen or concurrent users. Those application costs remain to be measured after the API exists. The saved raw timing samples are in benchmark.json.

## 3. How much memory did it use?

We used a fresh Python worker process, loaded six point models and 18 lower/middle/upper models, cached representative histories and ran predictions with two numerical threads.

Its peak working set—the greatest amount of physical memory attributed to that process during this run—was **140.4 MiB**. Its peak committed-memory counter was **177.5 MiB**. These are different memory measures, so they should not be added together.

This is the prediction worker, including its imports and models. It is not total laptop usage, VS Code usage, training peak memory or a future web-server memory measurement. Loading the models after Python imports took about 0.21 seconds. Laptop activity and caching can change timing.

## 4. Can we claim the system detects congestion?

No. We checked the fixed experimental load marker of 80% utilization. The selected cohort had **zero readings at or above 80% in the final test period**, across 4G and 5G. Its development calibration period had only one such 5G reading.

We can evaluate ordinary utilization forecasts, but this test does not validate warning accuracy for rare high-load events. High utilization alone is also not confirmed congestion; service degradation would need separate evidence. The counts are for the selected cohort, not the whole raw archive.

## 5. Which files were created?

| File | Why it exists |
|---|---|
| `scripts/check_reliability.py` | Runs grouped consistency checks, rare-load counts and a fresh-process prediction benchmark |
| `scripts/validate_reliability.py` | Rechecks saved calculations without retraining or repeating speed tests |
| `tests/test_reliability.py` | Checks reproducibility, paired error calculations and Windows memory counters |
| `outputs/reliability_v1/Results.md` | Complete readable results and limits |
| `protocol.json` | Analysis rules saved before the checks |
| `resampling.json` | Exploratory results from repeating the station/day group comparisons |
| `station_days.json` | Each station/day's errors and range inclusion |
| `high_load_support.json` | Unique high-load readings and runs by data period |
| `benchmark.json` | Timing samples, memory counters and exactly what was measured |
| `run_manifest.json` and `validation.json` | Versions, file fingerprints and verification evidence |

All 32 code tests passed. Validation reproduced 12 grouped summaries from 300 station/day groups, checked 16 high-load support groups against the clean database, recomputed timing summaries, checked memory-counter consistency and verified recorded fingerprints. No raw audit, extraction or model training was repeated.

## Integration

Frozen models are served through the [local API](API_Contract.md) and [historical replay dashboard](Dashboard_Step.md). The timing and memory figures above measure the prediction worker, excluding HTTP, disk and browser costs.

Memory-counter references: [Microsoft GetProcessMemoryInfo](https://learn.microsoft.com/en-us/windows/win32/api/psapi/nf-psapi-getprocessmemoryinfo) and [PROCESS_MEMORY_COUNTERS](https://learn.microsoft.com/en-us/windows/win32/api/psapi/ns-psapi-process_memory_counters).

# Consistency, prediction speed and memory

No models were trained. We checked saved final-period predictions, resampled whole station/date groups, counted rare high readings, and timed cached-model forecasts in a fresh Windows process.

## Does the selected point model beat repeating the latest reading?

Negative error difference means the selected model has lower average error. The exploratory range shows how the difference varies when whole stations and consecutive two-day groups are resampled. It is not a guaranteed future improvement or a formal independence-based significance claim. Same observed-current/observed-future rows are used for both methods.

| Station group | Network | Ahead | Model minus latest-reading error | Exploratory resampling range |
|---|---|---:|---:|---|
| development | 4G | 15 min | -0.223 | -0.359 to -0.079 |
| development | 4G | 30 min | -0.469 | -0.629 to -0.335 |
| development | 4G | 60 min | -0.891 | -1.319 to -0.589 |
| development | 5G | 15 min | -0.076 | -0.166 to -0.024 |
| development | 5G | 30 min | -0.177 | -0.374 to -0.077 |
| development | 5G | 60 min | -0.300 | -0.756 to -0.092 |
| station_holdout | 4G | 15 min | -0.051 | -0.168 to 0.053 |
| station_holdout | 4G | 30 min | -0.122 | -0.248 to 0.006 |
| station_holdout | 4G | 60 min | -0.201 | -0.529 to 0.129 |
| station_holdout | 5G | 15 min | -0.032 | -0.063 to 0.000 |
| station_holdout | 5G | 30 min | -0.075 | -0.117 to -0.015 |
| station_holdout | 5G | 60 min | -0.101 | -0.175 to -0.043 |

Only four familiar stations, one excluded station and ten calendar dates are available. Resampling cannot create independent new stations or days. Adjacent-day dependence and partial-day/end-weight effects remain. Coverage resampling and per-station/day metrics are in the JSON files; do not treat pooled ~90% coverage as a per-station guarantee.

## Speed for one sector: all three horizons and their ranges

Each call rebuilds features from in-memory history and returns point forecasts plus calibrated ranges at 15/30/60 minutes. Models were already loaded. The timed path excludes HTTP/UI, serialization, disk history retrieval and model loading.

| Network | Typical single-call time | 95th percentile time | Typical batch of 128 histories |
|---|---:|---:|---:|
| 4G | 9.83 ms | 12.33 ms | 20.68 ms |
| 5G | 7.11 ms | 9.93 ms | 15.25 ms |

The fresh benchmark worker cached 6 point and18 quantile models. Its measured peak working set was 140.4 MiB; peak commit charge 177.5 MiB. These are process counters, not whole-laptop memory or training peak RAM. Model loading after imports took 0.21s. Timings vary with hardware, concurrent laptop activity and caching.

## Do we have enough high-load examples?

The 80% threshold is a fixed experimental load marker, not confirmed congestion. Counts below use unique observed timestamps, not repeated horizon labels. Contiguous15-minute runs need not be independent.

| Station group | Network | Split | Observed readings | At least80% | Contiguous runs |
|---|---|---|---:|---:|---:|
| development | 4G | calibration | 10,271 | 0 | 0 |
| development | 4G | test | 6,910 | 0 | 0 |
| development | 5G | calibration | 10,684 | 1 | 1 |
| development | 5G | test | 7,146 | 0 | 0 |
| station_holdout | 4G | calibration | 2,453 | 0 | 0 |
| station_holdout | 4G | test | 1,659 | 0 | 0 |
| station_holdout | 5G | calibration | 2,674 | 0 | 0 |
| station_holdout | 5G | test | 1,788 | 0 | 0 |

Do not claim validated congestion-warning precision/recall from sparse or absent positive examples. This remains a utilization-forecasting project.

## Files

- `protocol.json`: frozen analysis/resampling/benchmark rules.
- `resampling.json`: point differences, errors, range inclusion and width with exploratory ranges.
- `station_days.json`: individual station/day results.
- `high_load_support.json`: unique high-load readings/runs by split.
- `benchmark.json`: raw timings, process-memory counters and benchmark scope.
- `run_manifest.json`: versions, source/output hashes and elapsed time.

Overall analysis elapsed time: 5.2s. No raw audits, extraction or training were repeated.

Next: implement a local prediction API returning predictions/ranges plus fresh/stale/no-estimate status, with strict historical-input validation. Then add a historical replay screen. The API, HTTP latency, concurrent users and live-network operation have not been measured here.

Windows counter reference: [GetProcessMemoryInfo](https://learn.microsoft.com/en-us/windows/win32/api/psapi/nf-psapi-getprocessmemoryinfo) and [PROCESS_MEMORY_COUNTERS](https://learn.microsoft.com/en-us/windows/win32/api/psapi/ns-psapi-process_memory_counters).

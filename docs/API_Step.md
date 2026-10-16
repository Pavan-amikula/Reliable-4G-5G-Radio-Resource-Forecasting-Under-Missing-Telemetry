# The model now has a doorway: a local API

Implemented and tested on 17 October 2026. The default local address is `http://127.0.0.1:8765`.

## 1. What changed?

Before, Python experiment scripts called the models. Now another program can send historical readings and receive the answers through a local connection.

That connection is called an **API**, meaning application programming interface. Think of it as a doorway between the future screen and our saved models.

```text
Historical readings
        |
        v
Local API checks the request
        |
        v
Build exact historical inputs
        |
        v
Saved model + saved range adjustment
        |
        v
15 / 30 / 60-minute forecasts, ranges and freshness status
```

No model was retrained. The interface loads the saved models once and reuses them.

## 2. A real request we checked

The example contains past 4G readings for Site 16, sector 1, up to 26 April 2025 at 00:00 UTC. It contains no future readings or answers.

For 01:00 UTC, the service returned:

| Answer | Value |
|---|---:|
| Predicted utilization | 16.91% |
| Lower end of range | 10.34% |
| Upper end of range | 26.43% |
| Input status | Fresh current reading supplied |

These match the earlier saved experiment. The interface also returned the 15- and 30-minute answers. It does not return the later actual reading as part of prediction; actual readings belong in the separate evaluation/replay display.

## 3. What happens if input is missing or wrong?

- Current reading supplied: return the model prediction and range. Missing older readings are flagged; the range is not guaranteed reliable under outages.
- Current reading missing, last reading at most 60 minutes old: return the last value as a **stale estimate**, without a range.
- Older than that, or no history: return **no estimate**.
- A future history reading: reject the request.
- Duplicate timestamps, percentages below 0 or above 100, non-numeric values, ambiguous timestamps or unknown series: reject the request.

Observed zero is valid. Missing readings should be omitted, not converted into zero. The 60-minute stale threshold is the fixed illustrative policy from the stress experiment, not a proven safest rule.

This version supports only the 20-series cohort and final replay-origin period, 26 April to 5 May 2025. It is not connected to a live network. Every timestamp needs a timezone and an exact 15-minute clock position. The supplied history should include up to seven days of available observations so daily/weekly lags can be used; shorter history is accepted and marked as incomplete.

## 4. Which files were created?

| File | Why it exists |
|---|---|
| `networkprb/inference.py` | Validates history, rebuilds inputs and calls the saved models |
| `networkprb/api.py` | Receives local requests and sends JSON answers |
| `tests/test_api.py` | Checks forecasts, stale/no-estimate behavior and invalid requests through the local connection |
| `scripts/check_api.py` | Saves evidence from actual requests to the running service |
| `outputs/api_v1/examples.json` | Saved fresh/stale/no-history answers and future-reading rejection |
| `outputs/api_v1/validation.json` | Verification results and code fingerprints |
| `docs/API_Contract.md` | Technical request/response details for building the screen |

**JSON** is simply the structured text format programs use to exchange these readings and answers. The dashboard provides controls without requiring manual JSON entry.

All 39 code tests passed. Real local HTTP requests verified fresh, stale and no-estimate behavior, matched the known saved forecast, and rejected a future reading. Existing raw data, audits, experiments and models were not changed. An oversized-request test exposed a Windows connection-close issue, which was fixed before the complete passing run.

## Dashboard integration

The [historical replay screen](Dashboard_Step.md) selects recorded sector histories and displays forecasts, ranges and later actual readings. This API is a loopback-only sequential development service. Model-only latency and memory measurements do not include HTTP or browser costs.

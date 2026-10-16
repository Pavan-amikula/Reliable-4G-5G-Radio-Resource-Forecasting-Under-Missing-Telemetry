# Local replay API contract (schema version 1)

Start from the project root for reproduction: `.\.venv\Scripts\python.exe -m networkprb.api --port 8765`. It binds only to 127.0.0.1; requests are processed sequentially with two numerical-library threads. Stop a manually started instance with Ctrl+C.

## Routes

| Method/path | Meaning |
|---|---|
| GET `/health` | Ready status after all six forecast groups are loaded |
| GET `/series` | The 20 supported technology/band/station/sector identities, roles and replay window |
| GET `/example` | A measured historical request with at most seven days of inputs up to the origin; no future labels |
| POST `/predict` | Validate inputs and return three forecast horizons |
| GET `/` | Historical replay dashboard HTML; fixed `/app.js` and `/style.css` assets |
| POST `/replay/context` | Five identity/origin fields (prediction request without history); returns `prediction_request` with only past history, separate `display_only_observations` on a 15-minute grid from six hours before to one hour after origin, and station role |

The context route reads the saved SQLite observations without writing. Later actuals are display-only, missing observations are null, and values at or beyond the evaluated end are withheld. The browser sends only `prediction_request` to `/predict`. Optional missing-input demonstrations filter that history before submission; original answers stay unchanged. All screen times are UTC. Static assets use an exact path whitelist and a same-origin content security policy.

## Prediction request

Exactly these top-level fields are accepted:

```json
{
  "technology": "LTE",
  "band_mhz": 1800,
  "station": "Site 16",
  "sector": "1",
  "origin_utc": "2025-04-26T00:00:00+00:00",
  "history": [
    {"timestamp_utc": "2025-04-26T00:00:00+00:00", "utilization_pct": 20.0}
  ]
}
```

This short request is a schema illustration, not the complete measured example from GET /example. Supply available history through the origin, preferably seven days. Max800 observations and128KiB JSON body. Entries must have exactly timestamp_utc and utilization_pct. Missing observations are omitted. Observed zeros retained. Body uses UTF-8 JSON and Content-Type application/json. Explicit Content-Length required; no chunked/compressed bodies, NaN/Infinity or duplicate object keys.

Technology/band pairs are LTE/1800 and NR/2100. Sector is a string. Identity must appear in /series. Every datetime must include Z or an explicit offset and land on a 15-minute UTC clock tick. Offsets normalize to UTC. Reject future history, repeated timestamps even with equal values, or non-finite/out-of-range utilization.

Supported origins: 2025-04-26T00:00:00+00:00 inclusive through2025-05-05T07:30:00+00:00 exclusive. This restriction prevents replaying models/corrections before their declared availability. Some late-origin horizon targets exceed the evaluated period; each horizon's target_within_evaluated_period indicates this. Those forecasts have no reported accuracy guarantee.

## Response

The response includes schema_version, mode=historical_replay, series identity, normalized origin, last observation time, age_minutes, missing_inputs, status, range_status, forecasts and interpretation. There are always15/30/60-minute horizon entries, whose numerical predictions may be null when no estimate is returned.

Each horizon has target_utc, horizon_minutes, predicted_utilization_pct, range_lower_pct, range_upper_pct, quantile_median_pct, method and target_within_evaluated_period. Values are percentages, not RB counts. The point estimate comes from the tuning-selected point model; the quantile median is a separate output and need not be identical to that point estimate.

| Status | Prediction | Range |
|---|---|---|
| fresh_model | Frozen selected model | Frozen sorted/clipped quantiles with saved calibration adjustment |
| stale_persistence | Last observed value if age<=60min | null |
| abstain | null | null |

range_status distinguishes available, available_with_history_gaps and withheld. Fresh current does not mean complete historical inputs. range_target_fraction=.90 is the nominal experimental goal; range_coverage_guaranteed=false explicitly avoids promising conditional or outage coverage. Counter availability at its timestamp remains an assumption.

## Errors and local scope

422: invalid JSON/schema/history;413: body over cap;415: wrong content type;411: missing/ambiguous length;404: unknown route. Local Host checks and no cross-origin browser access; no wildcard CORS. This is a loopback development service, with no public deployment/authentication system. Models are loaded only from known local artifacts after hash checks, never from a request-uploaded path. Access logs omit request bodies. Invalid internal operations return generic500 errors rather than paths or model internals.

Tests: `.\.venv\Scripts\python.exe -m unittest discover -s tests -v`. Saved HTTP smoke evidence: outputs/api_v1/. No feature fitting, target filling or model selection occurs in the API.

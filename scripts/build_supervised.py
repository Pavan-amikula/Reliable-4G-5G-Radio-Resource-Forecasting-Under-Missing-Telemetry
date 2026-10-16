"""Pair saved causal inputs with exact future observations; no model fitting."""
from collections import Counter, defaultdict
from contextlib import ExitStack
import csv
from datetime import datetime, timezone
import gzip
import json
import math
from pathlib import Path
import sqlite3

import forecast_baselines as b

DEST = b.PROCESSED / "supervised_v1"
KEYS = ("technology", "band_mhz", "station", "sector")
HISTORY = ("current_pct", "lag_15_pct", "lag_30_pct", "lag_60_pct",
           "lag_1440_pct", "lag_10080_pct", "observed_last_hour",
           "mean_observed_last_hour", "age_minutes")
FLAGS = tuple(name + "_missing" for name in HISTORY)
CALENDAR = ("hour_sin", "hour_cos", "weekday_sin", "weekday_cos")


def eligibility(role, origin, horizon, values, splits):
    """Return a split or a single mutually exclusive exclusion reason."""
    target = origin + horizon * 60
    split = b.partition(origin, target, splits)
    if split is None:
        return None, "boundary_or_outside"
    if role == "station_holdout" and split != "test":
        return None, "holdout_non_test"
    if origin not in values:
        return None, "missing_current"
    if target not in values:
        return None, "missing_future_target"
    return split, None


def build(destination=DEST):
    if destination.exists():
        raise SystemExit(f"Output already exists; inspect/reuse it: {destination}")
    manifest = json.loads(b.MANIFEST.read_text(encoding="utf-8"))
    if b.digest(b.DB) != manifest["database_sha256"]:
        raise ValueError("Observed database differs from extraction manifest")
    features = b.OUTPUT / "features.csv.gz"
    splits = [(s["name"], b.epoch(s["start_inclusive"]), b.epoch(s["end_exclusive"])) for s in manifest["splits"]]
    roles = {tuple(str(s[k]) for k in KEYS): s["role"] for s in manifest["series"]}
    destination.mkdir(parents=True)
    # A partial directory is deliberately not reusable if construction fails.
    fields = [*KEYS, "role", "split", "origin_utc", "target_utc", "horizon_minutes",
              *HISTORY, *FLAGS, *CALENDAR, "target_utilization_pct", "target_provenance"]
    counts = defaultdict(Counter)
    missing = defaultdict(Counter)
    writers = {}
    examples = {}
    grid_count = 0
    previous_key = None
    with sqlite3.connect(b.DB.as_uri() + "?mode=ro", uri=True) as connection, ExitStack() as stack:
        source = stack.enter_context(gzip.open(features, "rt", newline="", encoding="utf-8"))
        for row in csv.DictReader(source):
            grid_count += 1
            if grid_count > manifest["grid_limit"]:
                raise ValueError("Saved feature grid exceeds budget")
            key = tuple(row[k] for k in KEYS)
            if key not in roles or row["role"] != roles[key]:
                raise ValueError("Feature series role differs from cohort manifest")
            if key != previous_key:
                values = dict(connection.execute(
                    "SELECT timestamp,utilization_pct FROM observed WHERE technology=? AND band_mhz=? AND station=? AND sector=?", key))
                previous_key = key
            t = b.epoch(row["origin_utc"])
            dt = datetime.fromtimestamp(t, timezone.utc)
            phase = (dt.hour + dt.minute/60) * 2*math.pi/24
            week = dt.weekday() * 2*math.pi/7
            for h in b.HORIZONS:
                split, reason = eligibility(row["role"], t, h, values, splits)
                if reason:
                    counts[str(h)][reason] += 1
                    continue
                label = f"{row['role']}/{split}_{h}m"
                counts[str(h)][label] += 1
                if label not in writers:
                    folder = destination / row["role"]
                    folder.mkdir(exist_ok=True)
                    stream = stack.enter_context(gzip.open(folder / f"{split}_{h}m.csv.gz", "wt", newline="", encoding="utf-8"))
                    writers[label] = csv.DictWriter(stream, fields)
                    writers[label].writeheader()
                result = {k: row[k] for k in (*KEYS, "role", *HISTORY)}
                result.update({k+"_missing": int(row[k] == "") for k in HISTORY})
                result.update(dict(zip(CALENDAR, (math.sin(phase), math.cos(phase), math.sin(week), math.cos(week)))))
                result.update(split=split, origin_utc=b.iso(t), target_utc=b.iso(t+h*60),
                              horizon_minutes=h, target_utilization_pct=values[t+h*60],
                              target_provenance="observed")
                writers[label].writerow(result)
                missing[label].update(k for k in HISTORY if row[k] == "")
                if label.startswith("development/train_") and str(h) not in examples and all(row[k] != "" for k in ("current_pct", "lag_15_pct", "lag_30_pct", "lag_60_pct")):
                    examples[str(h)] = result
    if grid_count != manifest["grid_slots"]:
        raise ValueError("Feature-grid count differs from extraction")
    summary = {
        "source_manifest_sha256": b.digest(b.MANIFEST), "source_database_sha256": b.digest(b.DB),
        "source_features_sha256": b.digest(features), "builder_sha256": b.digest(Path(__file__)),
        "grid_rows_read": grid_count, "counts_by_horizon": dict(counts),
        "missing_inputs_by_file": dict(missing), "examples": examples,
        "input_columns": [*HISTORY, *FLAGS, *CALENDAR],
        "metadata_columns_not_model_inputs": [*KEYS, "role", "split", "origin_utc", "target_utc", "horizon_minutes", "target_provenance"],
        "label_column": "target_utilization_pct",
        "policy": "Observed current reading required (same availability as persistence). Exact future labels, same series only. Missing lags stay blank with flags. No filling, scaling or fitting. Shared original cutoffs, labels at/after split end purged. Holdout has final-test tables only. Prior history may cross a split start; future labels cannot cross its end. Metadata and label must never enter model inputs.",
        "splits": manifest["splits"], "station_holdout": manifest["station_holdout"],
        "time_policy": manifest["time_policy"],
        "files": {str(p.relative_to(destination)): b.digest(p) for p in sorted(destination.rglob("*.csv.gz"))},
    }
    b.dump(destination / "summary.json", summary)
    for h in b.HORIZONS:
        c = counts[str(h)]
        print(f"{h:2}m: train={c['development/train_'+str(h)+'m']:,}, tuning={c['development/tuning_'+str(h)+'m']:,}, calibration={c['development/calibration_'+str(h)+'m']:,}, test={c['development/test_'+str(h)+'m']:,}, holdout test={c['station_holdout/test_'+str(h)+'m']:,}")
    print(f"Saved {destination / 'summary.json'}; no model trained.")


if __name__ == "__main__":
    build()

"""Bounded, standard-library Dataset_02 extraction and historical replay.

Commands are separate so extraction can be inspected before evaluation.
No raw fields are coalesced: only the unique observed target is extracted.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from datetime import datetime, timedelta, timezone
import gzip
import hashlib
import io
import json
import math
from pathlib import Path
import sqlite3
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "data/raw/Dataset_02.zip"
PROCESSED = ROOT / "data/processed"
OUTPUT = ROOT / "outputs/baselines_v1"
DB = PROCESSED / "observed_v1.sqlite"
MANIFEST = PROCESSED / "manifest_v1.json"
STEP = 900
HORIZONS = (15, 30, 60)
MAX_ROWS = 180_000
MAX_GRID = 200_000
SELECTION_START = "2025-02-08T00:00:00+00:00"
SELECTION_END = "2025-02-22T00:00:00+00:00"
SPLITS = [
    ("train", "2025-02-07T19:45:00+00:00", "2025-03-01T00:00:00+00:00"),
    ("tuning", "2025-03-01T00:00:00+00:00", "2025-04-12T00:00:00+00:00"),
    ("calibration", "2025-04-12T00:00:00+00:00", "2025-04-26T00:00:00+00:00"),
    ("test", "2025-04-26T00:00:00+00:00", "2025-05-05T07:30:00+00:00"),
]


def epoch(value):
    parsed = datetime.fromisoformat(value)
    # Publisher documents UTC; the CSV does not carry an offset.
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    result = int(parsed.timestamp())
    if result % STEP or parsed.microsecond:
        raise ValueError(f"Not on the 15-minute clock: {value}")
    return result


def iso(value):
    return datetime.fromtimestamp(value, timezone.utc).isoformat()


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def digest(path, algorithm="sha256"):
    h = hashlib.new(algorithm)
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def observations():
    """Stream target rows; preserve archive member and physical CSV row number."""
    with zipfile.ZipFile(ARCHIVE) as archive:
        for tech, band, prefix in (("NR", 2100, "5G"), ("LTE", 1800, "4G")):
            member = f"Dataset_02/Baseband_02/Dataset_02_{tech}_{band}.csv"
            with archive.open(member) as raw:
                reader = csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8-sig", newline=""))
                for line, row in enumerate(reader, 2):
                    value = row[prefix + " RB utilization"].strip()
                    if not value:
                        continue
                    y = float(value)
                    if not math.isfinite(y) or not 0 <= y <= 100:
                        raise ValueError(f"Invalid percentage: {member}:{line}")
                    key = (tech, band, row["Base station"], row["Sector"])
                    yield key, row["Timestamp"], y, member, line


def extract():
    if DB.exists() or MANIFEST.exists():
        raise SystemExit("Extraction already exists; inspect/reuse it. No automatic overwrite.")
    if digest(ARCHIVE, "md5") != "7d9c1c019e5d18bf318b4e4ad9393d91":
        raise ValueError("Archive differs from saved audited version")
    print("Selecting cohort from 8-21 February observations only...", flush=True)
    early = defaultdict(set)
    start, end = epoch(SELECTION_START), epoch(SELECTION_END)
    # CSV rows are not chronological, so scan without stopping at later dates.
    for key, stamp, *_ in observations():
        if SELECTION_START[:10] <= stamp[:10] < SELECTION_END[:10]:
            t = epoch(stamp)
            if t in early[key]:
                raise ValueError(f"Duplicate observed target: {key}, {stamp}")
            early[key].add(t)
    expected = (end - start) // STEP
    eligible = defaultdict(list)
    for station, sector in sorted({(k[2], k[3]) for k in early}):
        if all(len(early[(tech, band, station, sector)]) >= math.ceil(0.70 * expected)
               for tech, band in (("NR", 2100), ("LTE", 1800))):
            eligible[station].append(sector)
    stations = sorted((s for s, sectors in eligible.items() if len(sectors) >= 2),
                      key=lambda s: (int(s.split()[-1]), s))[:5]
    if len(stations) != 5:
        raise ValueError("Fewer than five eligible stations; inspect early coverage before revising policy")
    selected = {(tech, band, s, sector) for s in stations
                for sector in sorted(eligible[s], key=int)[:2]
                for tech, band in (("NR", 2100), ("LTE", 1800))}
    holdout = stations[-1]
    PROCESSED.mkdir(parents=True, exist_ok=True)
    pending = DB.with_suffix(".partial.sqlite")
    if pending.exists():
        raise SystemExit(f"Inspect interrupted extraction first: {pending}")
    connection = sqlite3.connect(pending)
    connection.execute("PRAGMA cache_size=-16384")
    connection.execute("""CREATE TABLE observed (
        technology TEXT, band_mhz INTEGER, station TEXT, sector TEXT,
        timestamp INTEGER, utilization_pct REAL, source_member TEXT, source_row INTEGER,
        PRIMARY KEY (technology, band_mhz, station, sector, timestamp)) WITHOUT ROWID""")
    count = 0
    with connection:
        for key, stamp, y, member, line in observations():
            if key not in selected:
                continue
            count += 1
            if count > MAX_ROWS:
                raise ValueError("Cohort row budget exceeded")
            # Primary key rejects any repeated nonempty observation, even equal values.
            connection.execute("INSERT INTO observed VALUES (?,?,?,?,?,?,?,?)",
                               (*key, epoch(stamp), y, member, line))
    summary = []
    grid_rows = 0
    for key in sorted(selected):
        times = [r[0] for r in connection.execute(
            "SELECT timestamp FROM observed WHERE technology=? AND band_mhz=? AND station=? AND sector=? ORDER BY timestamp", key)]
        grid = (times[-1] - times[0]) // STEP + 1
        grid_rows += grid
        gaps = Counter((b-a)//STEP for a,b in zip(times, times[1:]) if b-a != STEP)
        longest = run = 1
        for a,b in zip(times, times[1:]):
            run = run + 1 if b-a == STEP else 1
            longest = max(longest, run)
        summary.append(dict(zip(("technology", "band_mhz", "station", "sector"), key)) | {
            "role": "station_holdout" if key[2] == holdout else "development",
            "early_observations": len(early[key]), "early_grid_slots": expected,
            "observed_rows": len(times), "first": iso(times[0]), "last": iso(times[-1]),
            "grid_slots": grid, "unobserved_grid_slots": grid-len(times),
            "longest_contiguous_observed_slots": longest,
            "gap_step_histogram": dict(sorted(gaps.items())),
        })
    if grid_rows > MAX_GRID:
        raise ValueError("Grid row budget exceeded")
    connection.close()
    pending.rename(DB)
    manifest = {
        "schema_version": 1, "python": sys.version, "archive_sha256": digest(ARCHIVE),
        "database_sha256": digest(DB), "extractor_sha256": digest(Path(__file__)),
        "source": "https://doi.org/10.5281/zenodo.17815388",
        "descriptor": "https://doi.org/10.1038/s41597-026-07723-0", "license": "CC BY 4.0",
        "cohort_rule": "First five numeric station IDs with >=2 sectors having >=70% observed slots in BOTH technologies during the early window; first two numeric sectors each. Fifth station reserved.",
        "selection_start": SELECTION_START, "selection_end_exclusive": SELECTION_END,
        "station_holdout": holdout, "row_limit": MAX_ROWS, "grid_limit": MAX_GRID,
        "observed_rows": count, "grid_slots": grid_rows,
        "covariates": "Target history only. No KPI coalescing or energy extraction; uniqueness of other fields is unverified.",
        "time_policy": "UTC publisher timestamps; assume each counter is available at its timestamp. Interval start/end and export delay are not confirmed. This is an idealized replay availability assumption.",
        "missing_policy": "Missing observed target remains unavailable, never inferred zero. Full per-series first-to-last clock grid.",
        "splits": [{"name": n, "start_inclusive": a, "end_exclusive": b} for n,a,b in SPLITS],
        "split_rationale": "Train includes February and cohort window. Tuning includes March 1-11 and April 5-11, spanning the documented recording gap. Calibration uses April 12-25; final test April 26-May 5. Shared calendar cutoffs; no target-value-based selection.",
        "series": summary,
    }
    dump(MANIFEST, manifest)
    print(json.dumps({k: manifest[k] for k in ("observed_rows", "grid_slots", "station_holdout")}, indent=2))
    print(f"Saved {MANIFEST}")


def partition(origin, target, splits):
    for name, start, end in splits:
        if start <= origin < end:
            return name if target < end else None
    return None


def predictions(values, origin, horizon):
    # No carry-forward at missing origins. Persistence is freshness age zero.
    current = values.get(origin)
    return {"persistence": current,
            "daily_seasonal": values.get(origin + horizon * 60 - 86400)}


def evaluate():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if digest(DB) != manifest["database_sha256"]:
        raise ValueError("Extracted database changed")
    if OUTPUT.exists():
        raise SystemExit("Baseline output exists; reuse it. No automatic overwrite.")
    OUTPUT.mkdir(parents=True)
    splits = [(s["name"], epoch(s["start_inclusive"]), epoch(s["end_exclusive"])) for s in manifest["splits"]]
    stats = defaultdict(lambda: [0, 0.0, 0.0])
    coverage = defaultdict(Counter)
    connection = sqlite3.connect(DB)
    with gzip.open(OUTPUT / "forecasts.csv.gz", "wt", newline="", encoding="utf-8") as stream, \
         gzip.open(OUTPUT / "features.csv.gz", "wt", newline="", encoding="utf-8") as features:
        writer = csv.writer(stream)
        writer.writerow(["technology", "band_mhz", "station", "sector", "role", "split", "origin_utc", "target_utc", "horizon_minutes", "actual_pct", "persistence_pct", "daily_seasonal_pct", "comparison_rows"])
        fw = csv.writer(features)
        fw.writerow(["technology", "band_mhz", "station", "sector", "role", "origin_utc", "current_pct", "lag_15_pct", "lag_30_pct", "lag_60_pct", "lag_1440_pct", "lag_10080_pct", "observed_last_hour", "mean_observed_last_hour", "age_minutes"])
        for series in manifest["series"]:
            key = tuple(series[k] for k in ("technology", "band_mhz", "station", "sector"))
            values = dict(connection.execute("SELECT timestamp, utilization_pct FROM observed WHERE technology=? AND band_mhz=? AND station=? AND sector=?", key))
            role = series["role"]
            last_seen = None
            for t in range(min(values), max(values)+STEP, STEP):
                if t in values:
                    last_seen = t
                hour = [values[p] for p in range(t-3*STEP, t+STEP, STEP) if p in values]
                fw.writerow([*key, role, iso(t), values.get(t),
                             *(values.get(t-lag*60) for lag in (15,30,60,1440,10080)),
                             len(hour), sum(hour)/len(hour) if hour else None,
                             (t-last_seen)//60 if last_seen is not None else None])
                for h in HORIZONS:
                    target = t+h*60
                    name = partition(t, target, splits)
                    # Holdout station contributes no train/tuning/calibration labels or scores.
                    if role == "station_holdout" and name != "test":
                        continue
                    if name is None:
                        coverage[(role, "purged", *key, h)]["boundary_or_outside"] += 1
                        continue
                    c = coverage[(role, name, *key, h)]
                    c["grid_origins"] += 1
                    actual = values.get(target)
                    pred = predictions(values, t, h)
                    if actual is None:
                        c["missing_future_target"] += 1
                        continue
                    c["observed_future_target"] += 1
                    for model, p in pred.items():
                        if p is not None:
                            c[model + "_available"] += 1
                    paired = all(p is not None for p in pred.values())
                    if paired:
                        c["paired_available"] += 1
                    writer.writerow([*key, role, name, iso(t), iso(target), h, actual,
                                     pred["persistence"], pred["daily_seasonal"], int(paired)])
                    for model, p in pred.items():
                        if p is None:
                            continue
                        for sample in (["available", "paired"] if paired else ["available"]):
                            group = (role, name, *key, h, model, sample)
                            error = p-actual
                            acc = stats[group]
                            acc[0] += 1
                            acc[1] += abs(error)
                            acc[2] += error*error
    connection.close()
    metrics = []
    pooled = defaultdict(lambda: [0, 0.0, 0.0, [], []])
    for group, (n, absolute, squared) in sorted(stats.items()):
        role, split, tech, band, station, sector, h, model, sample = group
        metrics.append(dict(zip(("role", "split", "technology", "band_mhz", "station", "sector", "horizon_minutes", "model", "sample"), group)) | {"n": n, "mae_pp": absolute/n, "rmse_pp": math.sqrt(squared/n)})
        aggregate = pooled[(role, split, tech, h, model, sample)]
        aggregate[0] += n
        aggregate[1] += absolute
        aggregate[2] += squared
        aggregate[3].append(absolute/n)
        aggregate[4].append(math.sqrt(squared/n))
    aggregates = []
    for group, (n, absolute, squared, maes, rmses) in sorted(pooled.items()):
        aggregates.append(dict(zip(("role", "split", "technology", "horizon_minutes", "model", "sample"), group)) | {"n": n, "series_count": len(maes), "mae_pp": absolute/n, "rmse_pp": math.sqrt(squared/n), "macro_mae_pp": sum(maes)/len(maes), "macro_rmse_pp": sum(rmses)/len(rmses)})
    coverage_rows = [dict(zip(("role", "split", "technology", "band_mhz", "station", "sector", "horizon_minutes"), key)) | dict(value) for key,value in sorted(coverage.items())]
    dump(OUTPUT / "metrics.json", {"per_series": metrics, "aggregates": aggregates})
    dump(OUTPUT / "coverage.json", coverage_rows)
    dump(OUTPUT / "split_manifest.json", manifest | {
        "baseline_script_sha256": digest(Path(__file__)),
        "evaluation_policy": "No fit or tuning. Labels crossing ANY split end purged. Persistence requires observation at origin, no stale carry. Daily seasonal uses exact t+h-24h only, abstaining if absent. Available and paired rows reported separately; paired rows are the fair comparison. Features may read only past/current observations. Holdout early data used solely for eligibility, no learned fit; holdout scores only in final time block. Online prior observations from all roles may be used for history.",
    })
    print(f"Saved forecasts, causal features, metrics and coverage in {OUTPUT}")
    for r in aggregates:
        if r["role"] == "development" and r["split"] == "test" and r["sample"] == "paired":
            print(f"{r['technology']:3} {r['horizon_minutes']:2}m {r['model']:16} n={r['n']:5} MAE={r['mae_pp']:.3f} RMSE={r['rmse_pp']:.3f} pp")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("extract", "evaluate"))
    args = parser.parse_args()
    {"extract": extract, "evaluate": evaluate}[args.stage]()

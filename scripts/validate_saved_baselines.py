"""Validate saved artifacts against observations without rerunning forecasts."""
from collections import Counter, defaultdict
import csv
import gzip
import json
import math
import sqlite3

import forecast_baselines as b


def main():
    original = json.loads((b.ROOT / "manifest_sha256.json").read_text())
    protected = [p for p in original if p.startswith(("audit/", "data/raw/", "docs/", "scripts/audit_")) or p == "AGENTS.md"]
    for path in protected:
        assert b.digest(b.ROOT / path) == original[path], f"Original file changed: {path}"
    manifest = json.loads((b.OUTPUT / "split_manifest.json").read_text())
    assert b.digest(b.DB) == manifest["database_sha256"]
    connection = sqlite3.connect(b.DB)
    values = {tuple(row[:5]): row[5] for row in connection.execute("SELECT technology,band_mhz,station,sector,timestamp,utilization_pct FROM observed")}
    connection.close()
    splits = [(s["name"], b.epoch(s["start_inclusive"]), b.epoch(s["end_exclusive"])) for s in manifest["splits"]]
    metrics = defaultdict(lambda: [0, 0.0, 0.0])
    counts = Counter()
    with gzip.open(b.OUTPUT / "forecasts.csv.gz", "rt", newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            key = (row["technology"], int(row["band_mhz"]), row["station"], row["sector"])
            t, target, h = b.epoch(row["origin_utc"]), b.epoch(row["target_utc"]), int(row["horizon_minutes"])
            assert target == t+h*60
            assert b.partition(t, target, splits) == row["split"]
            actual = float(row["actual_pct"])
            assert values[(*key, target)] == actual
            assert (row["station"] == manifest["station_holdout"]) == (row["role"] == "station_holdout")
            if row["role"] == "station_holdout":
                assert row["split"] == "test"
            paired = bool(row["persistence_pct"] and row["daily_seasonal_pct"])
            assert int(row["comparison_rows"]) == paired
            for model, source in (("persistence", t), ("daily_seasonal", target-86400)):
                stored = row[model+"_pct"]
                expected = values.get((*key, source))
                assert (float(stored) if stored else None) == expected
                assert source <= t
                if not stored:
                    continue
                for sample in (["available", "paired"] if paired else ["available"]):
                    group = (row["role"], row["split"], *key, h, model, sample)
                    err = float(stored)-actual
                    acc = metrics[group]
                    acc[0] += 1
                    acc[1] += abs(err)
                    acc[2] += err*err
            counts["forecast_rows"] += 1
    saved = json.loads((b.OUTPUT / "metrics.json").read_text())["per_series"]
    assert len(saved) == len(metrics)
    for row in saved:
        group = tuple(row[k] for k in ("role","split","technology","band_mhz","station","sector","horizon_minutes","model","sample"))
        n, absolute, squared = metrics[group]
        assert n == row["n"]
        assert math.isclose(absolute/n, row["mae_pp"], abs_tol=1e-12)
        assert math.isclose(math.sqrt(squared/n), row["rmse_pp"], abs_tol=1e-12)
    print(f"Validated {counts['forecast_rows']:,} forecast rows and {len(saved):,} metric groups; {len(protected)} original protected files unchanged.")


if __name__ == "__main__":
    main()

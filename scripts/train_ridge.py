"""Small CPU Ridge comparison. Select on tuning only; freeze before test reads."""
import os

for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[name] = "2"

from collections import defaultdict
import csv
import gzip
import json
from pathlib import Path
import sqlite3
import sys
import time

import joblib
import numpy as np
import scipy
import sklearn
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits

import forecast_baselines as b
from build_supervised import DEST, HISTORY, FLAGS, CALENDAR

OUT = b.ROOT / "outputs/ridge_v1"
INPUTS = [*HISTORY, *FLAGS, *CALENDAR]
ALPHAS = (0.1, 1.0, 10.0)


def pipeline(alpha):
    return make_pipeline(SimpleImputer(strategy="median", keep_empty_features=True),
                         StandardScaler(), Ridge(alpha=alpha, solver="svd"))


def read_table(role, split, horizon, technology, summary):
    path = DEST / role / f"{split}_{horizon}m.csv.gz"
    if b.digest(path) != summary["files"][str(path.relative_to(DEST))]:
        raise ValueError(f"Input table changed: {path}")
    boundaries = next(s for s in summary["splits"] if s["name"] == split)
    start, end = b.epoch(boundaries["start_inclusive"]), b.epoch(boundaries["end_exclusive"])
    rows = []
    seen = set()
    with gzip.open(path, "rt", newline="", encoding="utf-8") as stream:
        for r in csv.DictReader(stream):
            if r["technology"] != technology:
                continue
            origin, target = b.epoch(r["origin_utc"]), b.epoch(r["target_utc"])
            if not (start <= origin < target < end and target == origin + horizon*60):
                raise ValueError("Invalid split boundary or future clock")
            if r["role"] != role or r["split"] != split or int(r["horizon_minutes"]) != horizon:
                raise ValueError("Row role/split/horizon mismatch")
            is_holdout = r["station"] == summary["station_holdout"]
            if is_holdout != (role == "station_holdout") or (is_holdout and split != "test"):
                raise ValueError("Station-holdout leakage")
            key = (r["station"], r["sector"], origin)
            if key in seen:
                raise ValueError("Duplicate forecast origin")
            seen.add(key)
            if r["target_provenance"] != "observed" or not r["current_pct"]:
                raise ValueError("Unobserved target/current")
            rows.append(r)
            if len(rows) > 40_000:
                raise ValueError("Per-table CPU/memory budget exceeded")
    if not rows:
        raise ValueError("Empty cohort table")
    x = np.array([[float(r[k]) if r[k] else np.nan for k in INPUTS] for r in rows], dtype=np.float64)
    y = np.array([float(r["target_utilization_pct"]) for r in rows])
    if not np.isfinite(y).all() or np.isinf(x).any():
        raise ValueError("Invalid numeric values")
    return rows, x, y


def error_metrics(actual, predicted):
    error = np.asarray(predicted) - np.asarray(actual)
    return {"n": len(error), "mae_pp": float(np.abs(error).mean()),
            "rmse_pp": float(np.sqrt(np.square(error).mean()))}


def main():
    if OUT.exists():
        raise SystemExit("Ridge output exists; inspect/reuse it, no automatic overwrite")
    started = time.perf_counter()
    summary = json.loads((DEST / "summary.json").read_text(encoding="utf-8"))
    if summary["input_columns"] != INPUTS:
        raise ValueError("Unexpected feature schema")
    if b.digest(b.DB) != summary["source_database_sha256"]:
        raise ValueError("Observed database changed")
    OUT.mkdir(parents=True)
    selected = {}
    trials = []
    preprocessing = []
    models = {}
    # Only development train and tuning are opened before selection is frozen.
    with threadpool_limits(limits=2):
        for tech in ("LTE", "NR"):
            for h in b.HORIZONS:
                _, train_x, train_y = read_table("development", "train", h, tech, summary)
                _, tune_x, tune_y = read_table("development", "tuning", h, tech, summary)
                candidates = []
                for alpha in ALPHAS:
                    model = pipeline(alpha)
                    tick = time.perf_counter()
                    model.fit(train_x, train_y)
                    prediction = np.clip(model.predict(tune_x), 0, 100)
                    score = error_metrics(tune_y, prediction)
                    trials.append({"technology": tech, "horizon_minutes": h, "alpha": alpha,
                                   "training_rows": len(train_y), "fit_predict_seconds": time.perf_counter()-tick, **score})
                    candidates.append((score["mae_pp"], alpha, model))
                best_mae, best_alpha, best_model = min(candidates, key=lambda c:(c[0], c[1]))
                key = f"{tech}_{h}m"
                selected[key] = {"alpha": best_alpha, "tuning_mae_pp": best_mae}
                models[key] = best_model
                joblib.dump(best_model, OUT / f"{key}.joblib")
                imputer = best_model.named_steps["simpleimputer"]
                scaler = best_model.named_steps["standardscaler"]
                preprocessing.append({"model": key, "input_columns": INPUTS,
                                      "training_medians": imputer.statistics_.tolist(),
                                      "all_missing_train_columns": [INPUTS[i] for i in np.where(np.isnan(train_x).all(axis=0))[0]],
                                      "scaler_mean": scaler.mean_.tolist(), "scaler_scale": scaler.scale_.tolist(),
                                      "fit_rows": int(scaler.n_samples_seen_),
                                      "coefficients_on_scaled_inputs": best_model.named_steps["ridge"].coef_.tolist()})
                print(f"Selected {key}: alpha={best_alpha}, tuning MAE={best_mae:.3f} pp", flush=True)
    protocol = {
        "status": "selection_frozen_before_test_read", "selected": selected,
        "selection": "Lowest pooled development tuning MAE per technology/horizon; tie: smaller alpha",
        "alpha_candidates": ALPHAS, "features": INPUTS, "threads": 2,
        "preprocessing": "Training-only median imputation and standardization. Explicit missing flags. Empty training features retained with constant 0 by sklearn, flags preserved. No refit on tuning/calibration/test.",
        "prediction_policy": "Clip every method prediction to physical 0..100 percentage range; fixed before scoring",
        "evaluation": "All available rows compare Ridge/persistence; paired rows require daily seasonal too. Per-series, pooled and macro errors. Separate holdout station; no station IDs used as inputs.",
        "calibration": "Not read, fitted or scored in this experiment",
        "splits": summary["splits"], "station_holdout": summary["station_holdout"],
        "python": sys.version, "versions": {"numpy":np.__version__, "scipy":scipy.__version__, "scikit-learn":sklearn.__version__, "joblib":joblib.__version__},
        "script_sha256": b.digest(Path(__file__)), "table_summary_sha256": b.digest(DEST / "summary.json"),
    }
    b.dump(OUT / "selection.json", protocol)
    b.dump(OUT / "tuning_trials.json", trials)
    b.dump(OUT / "preprocessing.json", preprocessing)
    with sqlite3.connect(b.DB.as_uri()+"?mode=ro", uri=True) as con:
        observed = {tuple(r[:5]):r[5] for r in con.execute("SELECT technology,band_mhz,station,sector,timestamp,utilization_pct FROM observed")}
    groups = defaultdict(lambda: ([], []))
    coverage = []
    with gzip.open(OUT / "forecasts.csv.gz", "wt", newline="", encoding="utf-8") as stream, threadpool_limits(limits=2):
        writer = csv.writer(stream)
        writer.writerow(["role","split","technology","band_mhz","station","sector","origin_utc","target_utc","horizon_minutes","actual_pct","ridge_pct","persistence_pct","daily_seasonal_pct","paired"])
        for tech in ("LTE", "NR"):
            for h in b.HORIZONS:
                for role, split in (("development","tuning"),("development","test"),("station_holdout","test")):
                    rows,x,y = read_table(role, split, h, tech, summary)
                    pred = np.clip(models[f"{tech}_{h}m"].predict(x),0,100)
                    paired_count = 0
                    for r, actual, p in zip(rows,y,pred):
                        key = (tech,int(r["band_mhz"]),r["station"],r["sector"])
                        seasonal = observed.get((*key,b.epoch(r["target_utc"])-86400))
                        persistence = float(r["current_pct"])
                        paired = seasonal is not None
                        paired_count += paired
                        writer.writerow([role,split,*key,r["origin_utc"],r["target_utc"],h,actual,p,persistence,seasonal,int(paired)])
                        for sample in (["available","paired"] if paired else ["available"]):
                            for model,value in (("ridge",p),("persistence",persistence),("daily_seasonal",seasonal)):
                                if value is None:
                                    continue
                                g=(role,split,tech,h,sample,model,r["station"],r["sector"])
                                groups[g][0].append(actual)
                                groups[g][1].append(value)
                    coverage.append({"role":role,"split":split,"technology":tech,"horizon_minutes":h,"eligible_rows":len(rows),"ridge_scored":len(rows),"persistence_scored":len(rows),"paired_scored":paired_count})
    per_series = []
    pooled = defaultdict(lambda: ([],[],[],[]))
    for key,(actual,predicted) in sorted(groups.items()):
        score=error_metrics(actual,predicted)
        per_series.append(dict(zip(("role","split","technology","horizon_minutes","sample","model","station","sector"),key)) | score)
        acc=pooled[key[:6]]
        acc[0].extend(actual); acc[1].extend(predicted)
        acc[2].append(score["mae_pp"]); acc[3].append(score["rmse_pp"])
    aggregates=[]
    for key,(actual,predicted,maes,rmses) in sorted(pooled.items()):
        aggregates.append(dict(zip(("role","split","technology","horizon_minutes","sample","model"),key)) | error_metrics(actual,predicted) | {"series_count":len(maes),"macro_mae_pp":float(np.mean(maes)),"macro_rmse_pp":float(np.mean(rmses))})
    b.dump(OUT / "metrics.json", {"per_series":per_series,"aggregates":aggregates})
    b.dump(OUT / "coverage.json", coverage)
    protocol.update(status="complete", elapsed_seconds=time.perf_counter()-started,
                    artifacts_sha256={p.name:b.digest(p) for p in sorted(OUT.iterdir()) if p.is_file()})
    b.dump(OUT / "run_manifest.json",protocol)
    write_report(protocol,aggregates,coverage)
    print(f"Completed in {protocol['elapsed_seconds']:.1f}s. See {OUT / 'Results.md'}")


def write_report(protocol, metrics, coverage):
    lines=["# First learned model: Ridge", "", "This is a measured CPU experiment, not a proposed score. Six models (technology × horizon) were fitted on training rows, with three alpha candidates each and selection on tuning only.", "", "Missing inputs were replaced by training medians, then standardized using training statistics. Flags preserve missingness. Calibration was not used. Test and Site 53 were excluded from every fit and parameter choice. Models were frozen before test data were opened. IDs are metadata only.", "", "## Final-period fair comparison", "", "All three methods use the same paired rows in each row below. Errors are percentage points; lower is better.", "", "| Role | Tech | Horizon | Rows | Ridge MAE | Persistence MAE | Daily MAE | Ridge RMSE |", "|---|---|---:|---:|---:|---:|---:|---:|"]
    lookup={(r['role'],r['technology'],r['horizon_minutes'],r['model']):r for r in metrics if r['split']=='test' and r['sample']=='paired'}
    for role in ("development","station_holdout"):
        for tech in ("LTE","NR"):
            for h in b.HORIZONS:
                r=lookup[role,tech,h,'ridge']; p=lookup[role,tech,h,'persistence']; s=lookup[role,tech,h,'daily_seasonal']
                lines.append(f"| {role} | {tech} | {h}m | {r['n']:,} | {r['mae_pp']:.3f} | {p['mae_pp']:.3f} | {s['mae_pp']:.3f} | {r['rmse_pp']:.3f} |")
    lines += ["", "## What files mean", "", "- Six `.joblib` files: fitted train-only imputer/scaler/Ridge pipelines. Load only these locally generated trusted artifacts.", "- `selection.json`: selected parameters and protocol frozen before test access.", "- `tuning_trials.json`: 18 bounded candidate results; selection uses tuning MAE only.", "- `preprocessing.json`: training medians, scales, coefficients and fitted-row counts.", "- `forecasts.csv.gz`: individual predictions and measured answers.", "- `metrics.json`: per-series, pooled and macro MAE/RMSE on available and paired rows.", "- `coverage.json`: eligible and scored-row counts.", "- `run_manifest.json`: versions, runtime, hashes and evaluation rules.", "", f"Total script time: {protocol['elapsed_seconds']:.1f} seconds, with numerical-library threads capped at two. Peak process RAM has not been measured.", "", "Current measurements are required at forecast origins. This does not test missing-current outages. Counters are assumed available at their recorded timestamps; reporting delay remains unverified. The cohort contains 16 familiar series and four holdout series, not all network stations. Historical replay does not establish deployment, congestion detection, energy savings, or statistical significance. A small Ridge comparison does not determine whether boosting or neural methods will win.", "", "The final period has already been scored. Future feature and hyperparameter decisions must use training/tuning only. Calibration remains for later interval work. No extra KPI or energy fields were merged."]
    (OUT / "Results.md").write_text("\n".join(lines)+"\n",encoding="utf-8")


if __name__ == "__main__":
    main()

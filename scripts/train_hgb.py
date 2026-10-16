"""Bounded CPU histogram boosting; preserve Ridge and use identical forecast rows."""
import os
for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[name] = "2"

from collections import defaultdict
import csv
import gzip
from itertools import groupby
import json
from pathlib import Path
import time

import joblib
import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor
from threadpoolctl import threadpool_limits

import train_ridge as r

OUT = r.b.ROOT / "outputs/hgb_v1"
CONFIGS = (15, 31)


def model_for(leaves):
    # No internal random validation split; tuning is the saved later time block.
    return HistGradientBoostingRegressor(
        loss="squared_error", learning_rate=0.05, max_iter=200,
        max_leaf_nodes=leaves, min_samples_leaf=30, l2_regularization=1.0,
        early_stopping=False, random_state=42)


def forecast_key(row):
    return row["technology"], int(row["horizon_minutes"]), row["role"], row["split"]


def main():
    if OUT.exists():
        raise SystemExit("HGB output exists; reuse it. No automatic overwrite.")
    started = time.perf_counter()
    summary = json.loads((r.DEST / "summary.json").read_text(encoding="utf-8"))
    ridge_manifest = json.loads((r.OUT / "run_manifest.json").read_text(encoding="utf-8"))
    for name, digest in ridge_manifest["artifacts_sha256"].items():
        if r.b.digest(r.OUT / name) != digest:
            raise ValueError(f"Ridge artifact changed: {name}")
    if summary["input_columns"] != r.INPUTS or r.b.digest(r.b.DB) != summary["source_database_sha256"]:
        raise ValueError("Input schema/database changed")
    OUT.mkdir(parents=True)
    trials, selected, fit_counts = [], {}, {}
    with threadpool_limits(limits=2):
        for tech in ("LTE", "NR"):
            for h in r.b.HORIZONS:
                _,x,y = r.read_table("development","train",h,tech,summary)
                _,vx,vy = r.read_table("development","tuning",h,tech,summary)
                candidates=[]
                for leaves in CONFIGS:
                    model=model_for(leaves)
                    tick=time.perf_counter()
                    model.fit(x,y)
                    score=r.error_metrics(vy,np.clip(model.predict(vx),0,100))
                    trials.append({"technology":tech,"horizon_minutes":h,"max_leaf_nodes":leaves,
                                   "fit_rows":len(y),"iterations":int(model.n_iter_),
                                   "fit_predict_seconds":time.perf_counter()-tick,**score})
                    candidates.append((score["mae_pp"],leaves,model))
                mae,leaves,model=min(candidates,key=lambda c:(c[0],c[1]))
                key=f"{tech}_{h}m"
                selected[key]={"max_leaf_nodes":leaves,"tuning_mae_pp":mae}
                fit_counts[key]=len(y)
                joblib.dump(model,OUT/f"{key}.joblib")
                print(f"Selected {key}: {leaves} leaves, tuning MAE={mae:.3f} pp",flush=True)
    protocol={
        "status":"frozen_before_test_read","selected":selected,"fit_counts":fit_counts,
        "model_parameters":model_for(15).get_params(),"leaf_candidates":CONFIGS,
        "selection":"Lowest pooled tuning MAE per technology/horizon; tie smaller leaf budget",
        "features":r.INPUTS,"threads":2,"preprocessing":"Native NaN handling; no imputation or scaling. Missing flags retained. Training-only fit/binning.",
        "validation":"early_stopping=False; no internal shuffled split. Fixed 200 iterations, two leaf budgets. No refit on tuning.",
        "calibration":"Not accessed; reserved for uncertainty calibration",
        "test_policy":"Models frozen before test tables opened. Predictions clipped to 0..100, same as Ridge. Same forecast origins/labels/masks; separate station holdout.",
        "splits":summary["splits"],"station_holdout":summary["station_holdout"],
        "versions":ridge_manifest["versions"],"script_sha256":r.b.digest(Path(__file__)),
        "ridge_forecasts_sha256":r.b.digest(r.OUT/"forecasts.csv.gz"),
        "table_summary_sha256":r.b.digest(r.DEST/"summary.json"),
    }
    r.b.dump(OUT/"selection.json",protocol)
    r.b.dump(OUT/"tuning_trials.json",trials)
    stats=defaultdict(lambda:[0,0.,0.])
    coverage=[]
    with gzip.open(r.OUT/"forecasts.csv.gz","rt",newline="",encoding="utf-8") as source, \
         gzip.open(OUT/"forecasts.csv.gz","wt",newline="",encoding="utf-8") as dest, threadpool_limits(limits=2):
        reader=csv.DictReader(source)
        writer=csv.DictWriter(dest,[*reader.fieldnames,"hgb_pct"])
        writer.writeheader()
        for (tech,h,role,split),records in groupby(reader,key=forecast_key):
            rows,x,y=r.read_table(role,split,h,tech,summary)
            model=joblib.load(OUT/f"{tech}_{h}m.joblib")
            predicted=np.clip(model.predict(x),0,100)
            paired_count=0
            for previous,row,actual,p in zip(records,rows,y,predicted,strict=True):
                for field in ("technology","band_mhz","station","sector","origin_utc","target_utc","role","split"):
                    if previous[field]!=row[field]:
                        raise ValueError(f"Forecast row mismatch: {field}")
                if float(previous["actual_pct"])!=actual:
                    raise ValueError("Ground truth mismatch")
                previous["hgb_pct"]=float(p)
                writer.writerow(previous)
                paired=bool(int(previous["paired"]))
                paired_count+=paired
                for sample in (["available","paired"] if paired else ["available"]):
                    for name in ("hgb","ridge","persistence","daily_seasonal"):
                        if previous[name+"_pct"]=="":
                            continue
                        error=float(previous[name+"_pct"])-actual
                        key=(role,split,tech,h,sample,name,row["station"],row["sector"])
                        acc=stats[key]; acc[0]+=1; acc[1]+=abs(error); acc[2]+=error*error
            coverage.append({"role":role,"split":split,"technology":tech,"horizon_minutes":h,
                             "eligible_rows":len(rows),"hgb_scored":len(rows),"paired_scored":paired_count})
    per_series=[]
    pooled=defaultdict(lambda:[0,0.,0.,[],[]])
    for key,(n,absolute,squared) in sorted(stats.items()):
        mae=absolute/n; rmse=(squared/n)**.5
        per_series.append(dict(zip(("role","split","technology","horizon_minutes","sample","model","station","sector"),key))|{"n":n,"mae_pp":mae,"rmse_pp":rmse})
        acc=pooled[key[:6]]; acc[0]+=n; acc[1]+=absolute; acc[2]+=squared; acc[3].append(mae); acc[4].append(rmse)
    aggregates=[]
    for key,(n,absolute,squared,maes,rmses) in sorted(pooled.items()):
        aggregates.append(dict(zip(("role","split","technology","horizon_minutes","sample","model"),key))|{"n":n,"mae_pp":absolute/n,"rmse_pp":(squared/n)**.5,"macro_mae_pp":float(np.mean(maes)),"macro_rmse_pp":float(np.mean(rmses)),"series_count":len(maes)})
    r.b.dump(OUT/"metrics.json",{"per_series":per_series,"aggregates":aggregates})
    r.b.dump(OUT/"coverage.json",coverage)
    protocol.update(status="complete",elapsed_seconds=time.perf_counter()-started)
    report(protocol,aggregates)
    protocol["artifacts_sha256"]={p.name:r.b.digest(p) for p in sorted(OUT.iterdir()) if p.is_file()}
    r.b.dump(OUT/"run_manifest.json",protocol)
    print(f"Completed in {protocol['elapsed_seconds']:.1f}s. Results: {OUT/'Results.md'}")


def report(protocol,metrics):
    lines=["# Tree-model comparison: HistGradientBoosting", "", "Measured CPU experiment. Six selected models, two leaf budgets each (15/31), 200 boosting iterations, two numerical threads. Selection uses development tuning MAE only; no random internal validation or calibration access. Native missing-value handling, same exact-history features and partitions as Ridge.", "", "## Final-period comparison", "", "Same paired rows for all four methods. MAE is in percentage points; lower is better. These are descriptive small-cohort results, not significance tests.", "", "| Role | Technology | Horizon | Rows | Persistence MAE | Daily MAE | Ridge MAE | HGB MAE | HGB RMSE |", "|---|---|---:|---:|---:|---:|---:|---:|---:|"]
    lookup={(r['role'],r['technology'],r['horizon_minutes'],r['model']):r for r in metrics if r['split']=='test' and r['sample']=='paired'}
    for role in ("development","station_holdout"):
        for tech in ("LTE","NR"):
            for h in r.b.HORIZONS:
                scores=[lookup[role,tech,h,m] for m in ("persistence","daily_seasonal","ridge","hgb")]
                lines.append(f"| {role} | {tech} | {h}m | {scores[0]['n']:,} | "+" | ".join(f"{s['mae_pp']:.3f}" for s in scores)+f" | {scores[-1]['rmse_pp']:.3f} |")
    lines += ["", "## Model family choice uses tuning only", "", "The proposed candidate below is the lowest pooled *tuning* MAE among persistence, Ridge and HGB on their common available rows. It is not chosen from test performance. LightGBM remains an untested planned candidate.", "", "| Technology | Horizon | Tuning-selected candidate | Tuning MAE |", "|---|---:|---|---:|"]
    for tech in ("LTE","NR"):
        for h in r.b.HORIZONS:
            candidates=[s for s in metrics if s['role']=='development' and s['split']=='tuning' and s['sample']=='available' and s['technology']==tech and s['horizon_minutes']==h and s['model'] in ('persistence','ridge','hgb')]
            best=min(candidates,key=lambda s:(s['mae_pp'],s['model']))
            lines.append(f"| {tech} | {h}m | {best['model']} | {best['mae_pp']:.3f} |")
    lines += ["", "## Saved files", "", "- `selection.json`: parameter choices and frozen protocol before test reads.", "- `tuning_trials.json`: the 12 candidate fits and timings.", "- Six `.joblib` files: fitted HGB models.", "- `forecasts.csv.gz`: the original Ridge/baseline rows plus HGB predictions.", "- `metrics.json`: available/paired, per-series, pooled and macro errors.", "- `coverage.json`: scored-row counts.", "- `run_manifest.json`: versions, source hashes and output hashes.", "", f"Measured script runtime: {protocol['elapsed_seconds']:.1f} seconds. Peak RAM not benchmarked.", "", "The held-out station is excluded from all learned fitting and selection. Current readings are still required, so outage robustness is not yet demonstrated. Timestamp availability is assumed, not verified. No extra KPI merging, energy modeling or live deployment. No old artifacts were overwritten.", "", "Next stages: a bounded LightGBM comparison; prediction intervals and separate calibration; missing-telemetry stress tests; station/day block uncertainty and compute benchmarks; API and historical replay dashboard. Neural models remain optional. Keep any later feature/hyperparameter decisions on training/tuning, never the already-viewed final test."]
    (OUT/"Results.md").write_text("\n".join(lines)+"\n",encoding="utf-8")


if __name__=="__main__":
    main()

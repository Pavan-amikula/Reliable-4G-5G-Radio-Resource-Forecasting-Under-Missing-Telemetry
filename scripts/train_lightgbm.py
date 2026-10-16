"""Bounded LightGBM comparison; preserve prior models and identical forecast rows."""
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
import lightgbm
from lightgbm import LGBMRegressor
from threadpoolctl import threadpool_limits

import train_ridge as r

PREVIOUS = r.b.ROOT / "outputs/hgb_v1"
OUT = r.b.ROOT / "outputs/lightgbm_v1"
CONFIGS = (15, 31)


def model_for(leaves):
    # Fixed iteration budget: no validation data are passed to model.fit.
    return LGBMRegressor(
        objective="regression", learning_rate=0.05, n_estimators=300,
        num_leaves=leaves, min_child_samples=30, reg_lambda=1.0,
        n_jobs=2, device_type="cpu", deterministic=True, force_col_wise=True,
        use_missing=True, zero_as_missing=False, random_state=42, verbosity=-1)


def forecast_key(row):
    return row["technology"], int(row["horizon_minutes"]), row["role"], row["split"]


def main():
    if OUT.exists():
        raise SystemExit("LightGBM output exists; reuse it. No automatic overwrite.")
    started = time.perf_counter()
    summary = json.loads((r.DEST / "summary.json").read_text(encoding="utf-8"))
    previous_manifest = json.loads((PREVIOUS / "run_manifest.json").read_text(encoding="utf-8"))
    for name, digest in previous_manifest["artifacts_sha256"].items():
        if r.b.digest(PREVIOUS / name) != digest:
            raise ValueError(f"Previous model artifact changed: {name}")
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
                    trials.append({"technology":tech,"horizon_minutes":h,"num_leaves":leaves,
                                   "fit_rows":len(y),"iterations":int(model.n_iter_),
                                   "fit_predict_seconds":time.perf_counter()-tick,**score})
                    candidates.append((score["mae_pp"],leaves,model))
                mae,leaves,model=min(candidates,key=lambda c:(c[0],c[1]))
                key=f"{tech}_{h}m"
                selected[key]={"num_leaves":leaves,"tuning_mae_pp":mae}
                fit_counts[key]=len(y)
                joblib.dump(model,OUT/f"{key}.joblib")
                print(f"Selected {key}: {leaves} leaves, tuning MAE={mae:.3f} pp",flush=True)
    protocol={
        "status":"frozen_before_test_read","selected":selected,"fit_counts":fit_counts,
        "model_parameters":model_for(15).get_params(),"leaf_candidates":CONFIGS,
        "selection":"Lowest pooled tuning MAE per technology/horizon; tie smaller leaf budget",
        "features":r.INPUTS,"threads":2,"preprocessing":"Native NaN handling; no imputation or scaling. Missing flags retained. Training-only fit/binning.",
        "validation":"Fixed 300 iterations, two leaf budgets; fit receives training only. No internal validation or refit on tuning.",
        "calibration":"Not accessed; reserved for uncertainty calibration",
        "test_policy":"Models frozen before test tables opened. Predictions clipped to 0..100, same as Ridge. Same forecast origins/labels/masks; separate station holdout.",
        "splits":summary["splits"],"station_holdout":summary["station_holdout"],
        "versions":previous_manifest["versions"] | {"lightgbm":lightgbm.__version__},"script_sha256":r.b.digest(Path(__file__)),
        "previous_forecasts_sha256":r.b.digest(PREVIOUS/"forecasts.csv.gz"),
        "table_summary_sha256":r.b.digest(r.DEST/"summary.json"),
    }
    r.b.dump(OUT/"selection.json",protocol)
    r.b.dump(OUT/"tuning_trials.json",trials)
    stats=defaultdict(lambda:[0,0.,0.])
    coverage=[]
    with gzip.open(PREVIOUS/"forecasts.csv.gz","rt",newline="",encoding="utf-8") as source, \
         gzip.open(OUT/"forecasts.csv.gz","wt",newline="",encoding="utf-8") as dest, threadpool_limits(limits=2):
        reader=csv.DictReader(source)
        writer=csv.DictWriter(dest,[*reader.fieldnames,"lightgbm_pct"])
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
                previous["lightgbm_pct"]=float(p)
                writer.writerow(previous)
                paired=bool(int(previous["paired"]))
                paired_count+=paired
                for sample in (["available","paired"] if paired else ["available"]):
                    for name in ("lightgbm","hgb","ridge","persistence","daily_seasonal"):
                        if previous[name+"_pct"]=="":
                            continue
                        error=float(previous[name+"_pct"])-actual
                        key=(role,split,tech,h,sample,name,row["station"],row["sector"])
                        acc=stats[key]; acc[0]+=1; acc[1]+=abs(error); acc[2]+=error*error
            coverage.append({"role":role,"split":split,"technology":tech,"horizon_minutes":h,
                             "eligible_rows":len(rows),"lightgbm_scored":len(rows),"paired_scored":paired_count})
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


def report(protocol, metrics):
    lines=["# LightGBM: did another model help?", "",
           "We trained another model using the same past readings, dates and forecast questions. Two small tree sizes were tried; settings were chosen using the tuning period only. The final test answers and reserved calibration period were not used for fitting or selection.", "",
           "## Average distance between prediction and actual reading", "",
           "Lower numbers are better. A distance of 4 percentage points means that predicting 44% when the reading was 40% gives an error of 4 for that example. These tables average that distance across many forecasts; individual errors can be larger. The technical name is MAE.", "",
           "All methods below use the same paired rows. Familiar stations are different from the separate station excluded from training.", "",
           "| Station group | Technology | Forecast ahead | Rows | Latest reading | Yesterday | Ridge | Earlier tree (HGB) | LightGBM |", "|---|---|---:|---:|---:|---:|---:|---:|---:|"]
    lookup={(v['role'],v['technology'],v['horizon_minutes'],v['model']):v for v in metrics if v['split']=='test' and v['sample']=='paired'}
    for role in ('development','station_holdout'):
        for tech in ('LTE','NR'):
            for horizon in r.b.HORIZONS:
                scores=[lookup[role,tech,horizon,name] for name in ('persistence','daily_seasonal','ridge','hgb','lightgbm')]
                lines.append(f"| {'Familiar' if role=='development' else 'Excluded station'} | {'4G' if tech=='LTE' else '5G'} | {horizon} min | {scores[0]['n']:,} | "+' | '.join(f"{v['mae_pp']:.3f}" for v in scores)+' |')
    lines += ["", "## Candidate chosen without looking at final-test performance", "",
              "Below we compare the models using the earlier tuning period. This keeps final answers out of the selection decision. Candidate selection here is for point forecasts; interval models and calibration are a separate pending step.", "",
              "| Technology | Forecast ahead | Lowest average tuning error | Error in percentage points |", "|---|---:|---|---:|"]
    for tech in ('LTE','NR'):
        for horizon in r.b.HORIZONS:
            candidates=[v for v in metrics if v['role']=='development' and v['split']=='tuning' and v['sample']=='available' and v['technology']==tech and v['horizon_minutes']==horizon and v['model'] in ('persistence','ridge','hgb','lightgbm')]
            best=min(candidates,key=lambda v:(v['mae_pp'],v['model']))
            lines.append(f"| {'4G' if tech=='LTE' else '5G'} | {horizon} min | {best['model']} | {best['mae_pp']:.3f} |")
    lines += ["", "## Files: what each one is for", "",
              "- `selection.json`: chosen tree settings and rules saved before test access.",
              "- `tuning_trials.json`: all 12 small training experiments and their earlier-period errors.",
              "- Six `.joblib` files: saved models for 4G/5G and 15/30/60 minutes.",
              "- `forecasts.csv.gz`: each prediction, actual answer and unchanged predictions from earlier models.",
              "- `metrics.json`: average errors, including separate sectors and station groups; RMSE is also saved and gives extra weight to large errors.",
              "- `coverage.json`: number of forecast questions that could be scored.",
              "- `run_manifest.json`: software versions, timing, file fingerprints and evaluation rules.", "",
              f"The full experiment took {protocol['elapsed_seconds']:.1f} seconds. Training used the CPU with two threads, at most 300 rounds and 15/31 leaves. Native missing-input handling preserves observed zeros. Peak memory was not measured.", "",
              "These are small-cohort historical results. They do not establish statistical significance, universal superiority, network congestion detection, energy savings or live deployment. The current setup still requires a current reading. Its reporting-time availability is assumed. Calibration was not accessed. Later choices must continue to use train/tuning, not the already-viewed final test.", "",
              "Next: add and check a likely range around forecasts, using the reserved calibration period only for adjustment. Then test missing readings, finish reliability/compute checks, and build the API and historical replay dashboard."]
    (OUT/'Results.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')


if __name__ == '__main__':
    main()


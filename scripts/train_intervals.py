"""Train quantile bounds, calibrate on later development data, then test once."""
from collections import defaultdict
import csv
import gzip
import json
import math
from pathlib import Path
import time

import train_lightgbm as l
import joblib
import numpy as np
from threadpoolctl import threadpool_limits

r = l.r
OUT = r.b.ROOT / "outputs/intervals_v1"
LEVELS = (.05, .5, .95)
ERROR_RATE = .10


def pinball(y, prediction, level):
    error = np.asarray(y) - np.asarray(prediction)
    return float(np.maximum(level*error, (level-1)*error).mean())


def predict_quantiles(models, x):
    raw = np.column_stack([m.predict(x) for m in models])
    crossings = (raw[:, 0] > raw[:, 1]) | (raw[:, 1] > raw[:, 2])
    # Frozen repair rule, applied identically during calibration and test.
    return np.clip(np.sort(raw, axis=1), 0, 100), crossings


def calibration_amount(y, quantiles):
    scores = np.maximum(quantiles[:, 0]-y, y-quantiles[:, 2])
    n = len(scores)
    rank = math.ceil((n+1)*(1-ERROR_RATE))
    if not 1 <= rank <= n:
        raise ValueError("Insufficient calibration observations")
    # Conservative non-shrinking variant: never narrow the initial bounds.
    return max(0., float(np.partition(scores, rank-1)[rank-1]))


def adjusted(quantiles, amount):
    result = quantiles.copy()
    result[:, 0] = np.maximum(0, result[:, 0]-amount)
    result[:, 2] = np.minimum(100, result[:, 2]+amount)
    return result


def interval_metrics(y, q):
    y = np.asarray(y)
    q = np.asarray(q)
    lower, median, upper = q.T
    width = upper-lower
    below, above = y < lower, y > upper
    score = width + 2/ERROR_RATE*(np.maximum(lower-y, 0)+np.maximum(y-upper, 0))
    return {"n":len(y), "coverage":float(((y >= lower) & (y <= upper)).mean()),
            "mean_width_pp":float(width.mean()), "below_fraction":float(below.mean()),
            "above_fraction":float(above.mean()), "interval_score":float(score.mean()),
            "median_mae_pp":float(np.abs(y-median).mean()),
            "pinball_by_quantile":{str(a):pinball(y,q[:,i],a) for i,a in enumerate(LEVELS)}}


def main():
    if OUT.exists():
        raise SystemExit("Interval output exists; inspect/reuse it, no overwrite")
    started = time.perf_counter()
    summary = json.loads((r.DEST/"summary.json").read_text(encoding="utf-8"))
    previous = json.loads((l.OUT/"run_manifest.json").read_text(encoding="utf-8"))
    for name,digest in previous["artifacts_sha256"].items():
        if r.b.digest(l.OUT/name) != digest:
            raise ValueError(f"Prior artifact changed: {name}")
    if r.b.digest(r.b.DB) != summary["source_database_sha256"]:
        raise ValueError("Observed database changed")
    OUT.mkdir(parents=True)
    point_scores = json.loads((l.OUT/"metrics.json").read_text(encoding="utf-8"))["aggregates"]
    models, selected, trials, point_choices = {}, {}, [], {}
    with threadpool_limits(limits=2):
        for tech in ("LTE","NR"):
            for h in r.b.HORIZONS:
                key=f"{tech}_{h}m"
                _,x,y=r.read_table("development","train",h,tech,summary)
                _,vx,vy=r.read_table("development","tuning",h,tech,summary)
                candidates=[]
                for leaves in (15,31):
                    fitted=[]; losses=[]
                    for level in LEVELS:
                        m=l.model_for(leaves).set_params(objective="quantile",alpha=level)
                        m.fit(x,y)
                        losses.append(pinball(vy,np.clip(m.predict(vx),0,100),level))
                        fitted.append(m)
                    loss=float(np.mean(losses))
                    trials.append({"model":key,"leaves":leaves,"mean_tuning_pinball":loss,
                                   "loss_by_quantile":dict(zip(map(str,LEVELS),losses)),"training_rows":len(y)})
                    candidates.append((loss,leaves,fitted))
                loss,leaves,fitted=min(candidates,key=lambda c:(c[0],c[1]))
                selected[key]={"leaves":leaves,"mean_tuning_pinball":loss}
                models[key]=fitted
                for level,m in zip(LEVELS,fitted):
                    joblib.dump(m,OUT/f"{key}_q{level:.2f}.joblib")
                # Point model choice remains distinct from quantile models.
                choices=[v for v in point_scores if v['role']=='development' and v['split']=='tuning' and v['sample']=='available' and v['technology']==tech and v['horizon_minutes']==h and v['model'] in ('ridge','hgb','lightgbm','persistence')]
                point_choices[key]=min(choices,key=lambda v:(v['mae_pp'],v['model']))['model']
                print(f"Trained bounds for {key}, selected {leaves} leaves using earlier tuning data",flush=True)
    protocol={"status":"models_frozen_before_calibration", "quantiles":LEVELS,"nominal_coverage":.9,
              "selected":selected,"point_choices_from_tuning":point_choices,"features":r.INPUTS,
              "training":"Training rows only, 36 sequential fits: 2 leaf budgets x3 quantiles x6 tech/horizon groups, 300 rounds, two threads. Select leaf budget by mean raw clipped quantile pinball loss on tuning only. No calibration refit or model selection.",
              "crossing_policy":"Sort all three predicted quantiles per row, then clip to 0..100, before calibration and scoring.",
              "calibration_policy":"Separate correction per technology/horizon pooled across development stations. Score=max(lower-y,y-upper); correction=max(0,kth score), k=ceil((n+1)*.9). Widen bounds, clip to 0..100. No online updates or holdout calibration.",
              "limits":"Non-shrinking split-CQR-style adjustment. Temporal dependence and population shift violate usual exchangeability assumptions; no automatic 90% coverage guarantee per station/time/holdout. Calibration coverage is in-sample diagnostic only.",
              "splits":summary['splits'],"station_holdout":summary['station_holdout'],
              "time_policy":json.loads(r.b.MANIFEST.read_text())['time_policy'],
              "versions":previous['versions'],"script_sha256":r.b.digest(Path(__file__)),
              "table_summary_sha256":r.b.digest(r.DEST/'summary.json'),
              "sources":["https://papers.nips.cc/paper_files/paper/2019/hash/5103c3584b063c431bd1268e9b5e76fb-Abstract.html","https://lightgbm.readthedocs.io/en/stable/Parameters.html"]}
    r.b.dump(OUT/'selection.json',protocol)
    r.b.dump(OUT/'tuning_trials.json',trials)
    corrections={}; calibration_cache={}
    with threadpool_limits(limits=2):
        for tech in ('LTE','NR'):
            for h in r.b.HORIZONS:
                key=f'{tech}_{h}m'
                rows,x,y=r.read_table('development','calibration',h,tech,summary)
                q,crossings=predict_quantiles(models[key],x)
                amount=calibration_amount(y,q)
                corrections[key]={'correction_pp':amount,'n':len(y),'rank':math.ceil((len(y)+1)*.9),
                                  'raw_diagnostic':interval_metrics(y,q),'adjusted_diagnostic':interval_metrics(y,adjusted(q,amount))}
                calibration_cache[key]=(rows,x,y,q,crossings)
    r.b.dump(OUT/'calibration.json',{'status':'corrections_frozen_before_test_read','groups':corrections,'station_holdout_used':False})
    groups=defaultdict(lambda:([],[]))
    crossings_report=[]; coverage=[]
    with gzip.open(OUT/'forecasts.csv.gz','wt',newline='',encoding='utf-8') as stream, threadpool_limits(limits=2):
        writer=csv.writer(stream)
        writer.writerow(['role','split','technology','band_mhz','station','sector','origin_utc','target_utc','horizon_minutes','actual_pct','point_model','point_pct','q05_pct','q50_pct','q95_pct','calibrated_lower_pct','calibrated_upper_pct','raw_quantiles_crossed'])
        for tech in ('LTE','NR'):
            for h in r.b.HORIZONS:
                key=f'{tech}_{h}m'
                point_name=point_choices[key]
                point_folder={'hgb':l.PREVIOUS,'lightgbm':l.OUT,'ridge':r.OUT}
                point_model=joblib.load(point_folder[point_name]/f'{key}.joblib') if point_name!='persistence' else None
                for role,split in (('development','calibration'),('development','test'),('station_holdout','test')):
                    if split=='calibration':
                        rows,x,y,q,crossings=calibration_cache[key]
                    else:
                        rows,x,y=r.read_table(role,split,h,tech,summary)
                        q,crossings=predict_quantiles(models[key],x)
                    cq=adjusted(q,corrections[key]['correction_pp'])
                    point=np.clip(point_model.predict(x),0,100) if point_model else x[:,0]
                    crossings_report.append({'role':role,'split':split,'technology':tech,'horizon_minutes':h,'n':len(y),'crossed_rows':int(crossings.sum())})
                    coverage.append({'role':role,'split':split,'technology':tech,'horizon_minutes':h,'eligible_rows':len(rows),'interval_rows':len(rows)})
                    for row,actual,base,cal,p,cross in zip(rows,y,q,cq,point,crossings,strict=True):
                        writer.writerow([role,split,tech,row['band_mhz'],row['station'],row['sector'],row['origin_utc'],row['target_utc'],h,actual,point_name,p,*base,cal[0],cal[2],int(cross)])
                        load='0_to_20' if actual<20 else '20_to_50' if actual<50 else '50_to_80' if actual<80 else '80_to_100'
                        for variant,bounds in (('raw',base),('calibrated',cal)):
                            for scope,a,b in (('pooled','all','all'),('series',row['station'],row['sector']),('load',load,'all')):
                                group=(role,split,tech,h,variant,scope,a,b)
                                groups[group][0].append(actual);groups[group][1].append(bounds)
    metrics=[]
    for key,(y,q) in sorted(groups.items()):
        metrics.append(dict(zip(('role','split','technology','horizon_minutes','variant','scope','station_or_load','sector'),key))|interval_metrics(y,q))
    r.b.dump(OUT/'metrics.json',metrics)
    r.b.dump(OUT/'crossings.json',crossings_report)
    r.b.dump(OUT/'coverage.json',coverage)
    protocol.update(status='complete',elapsed_seconds=time.perf_counter()-started)
    report(protocol,metrics)
    protocol['artifacts_sha256']={p.name:r.b.digest(p) for p in sorted(OUT.iterdir()) if p.is_file()}
    r.b.dump(OUT/'run_manifest.json',protocol)
    print(f"Finished in {protocol['elapsed_seconds']:.1f}s; see {OUT/'Results.md'}")


def report(protocol,metrics):
    lines=['# Forecast ranges: measured results','',
           'The point forecast remains the earlier model chosen using tuning data. Separate LightGBM models estimate a lower value, a middle value and an upper value. The target is a range containing about 90 out of 100 actual readings, while remaining as narrow as practical. This is a target, not a guarantee.','',
           'We trained models using training rows, chose tree size using tuning only, then adjusted the ranges using a separate later calibration period. That adjustment was saved before opening final-test tables. The excluded station supplied no training, tuning or calibration rows.','',
           '## How often did the actual reading fall inside?','',
           'Coverage means the fraction of actual readings inside the range. Width is the average distance between its lower and upper ends, in percentage points. Wider ranges can cover more readings but be less useful. The final rows below are out-of-calibration measurements; calibration scores in the JSON are in-sample diagnostics.','',
           '| Station group | Network | Ahead | Readings | Inside before adjustment | Inside after adjustment | Width before | Width after |',
           '|---|---|---:|---:|---:|---:|---:|---:|']
    lookup={(v['role'],v['technology'],v['horizon_minutes'],v['variant']):v for v in metrics if v['scope']=='pooled' and v['split']=='test'}
    for role in ('development','station_holdout'):
        for tech in ('LTE','NR'):
            for h in r.b.HORIZONS:
                raw=lookup[role,tech,h,'raw'];cal=lookup[role,tech,h,'calibrated']
                lines.append(f"| {'Familiar' if role=='development' else 'Excluded station'} | {'4G' if tech=='LTE' else '5G'} | {h} min | {raw['n']:,} | {raw['coverage']:.1%} | {cal['coverage']:.1%} | {raw['mean_width_pp']:.2f} | {cal['mean_width_pp']:.2f} |")
    lines += ['', '## What this does and does not show','',
              'The adjustment only widens the original range; it never narrows it. Both bounds stay between 0% and 100%. Quantile crossings are repaired by sorting the three quantile predictions before calibration. Crossing counts are saved. No test answers adjust the correction.','',
              'Readings at adjacent times and sectors are related. Because of that dependence and later distribution changes, this procedure does not guarantee 90% coverage for every station, time or future period. We measure coverage and width instead of claiming certainty. Per-sector and fixed load-band metrics, quantile losses, tail misses and interval scores are saved. Sparse high-load groups cannot establish reliable congestion-warning quality.','',
              '## Files and their purposes','',
              '- 18 `.joblib` files: fitted lower/middle/upper models for each technology and forecast period.',
              '- `selection.json` and `tuning_trials.json`: choices fixed before calibration.',
              '- `calibration.json`: the range-widening amounts fixed before test access.',
              '- `forecasts.csv.gz`: actual readings, separate point predictions, raw and adjusted ranges.',
              '- `metrics.json`: inside-range counts/fractions, widths and other error measures, including each sector and load band.',
              '- `crossings.json`: frequency of unordered raw quantile predictions.',
              '- `coverage.json`: number of eligible questions with ranges.',
              '- `run_manifest.json`: versions, hashes, timing and fixed rules.','',
              f"Full script time: {protocol['elapsed_seconds']:.1f} seconds, 36 bounded CPU fits, two threads. Peak process memory has not been measured.",'',
              'Next process: test what happens when inputs disappear, using clearly labeled artificial outages and separate natural-gap checks. API and recorded-data replay dashboard remain later stages. No live network operation or energy savings have been demonstrated.','',
              'Method references: [Conformalized Quantile Regression, Romano et al.](https://papers.nips.cc/paper_files/paper/2019/hash/5103c3584b063c431bd1268e9b5e76fb-Abstract.html); [LightGBM quantile objective](https://lightgbm.readthedocs.io/en/stable/Parameters.html). Our non-shrinking, physically clipped chronological implementation is documented in selection.json; standard exchangeability-based claims are not assumed.']
    (OUT/'Results.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')


if __name__=='__main__':
    main()

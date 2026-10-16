"""Frozen-model input outages. Original observations remain ground truth."""
from bisect import bisect_right
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
import gzip
import hashlib
import json
import math
from pathlib import Path
import sqlite3
import time

import train_intervals as t
import joblib
import numpy as np
from threadpoolctl import threadpool_limits

r=t.r
OUT=r.b.ROOT/'outputs/telemetry_stress_v1'
SCENARIOS=('clean_observed_origins','synthetic_drop10','synthetic_hour','natural_missing_origins')
MAX_STALE_MINUTES=60
SEED=20261017


def stable_int(text):
    return int.from_bytes(hashlib.sha256(text.encode('utf-8')).digest()[:8],'big')


def hidden(station,sector,stamp,scenario):
    """Deterministic schedules independent of measurements, shared across tech."""
    if scenario=='synthetic_drop10':
        return stable_int(f'{SEED}|drop|{station}|{sector}|{stamp}') / 2**64 < .10
    if scenario=='synthetic_hour':
        dt=datetime.fromtimestamp(stamp,timezone.utc)
        hour=6+stable_int(f'{SEED}|hour|{station}|{sector}|{dt.date()}')%15
        return dt.hour==hour
    return False


def features_at(values,times,origin):
    """Recompute every affected history input, not just the current column."""
    pos=bisect_right(times,origin)-1
    last=times[pos] if pos>=0 else None
    hour=[values[v] for v in range(origin-2700,origin+1,900) if v in values]
    history=[values.get(origin),*(values.get(origin-lag*60) for lag in (15,30,60,1440,10080)),
             len(hour),sum(hour)/len(hour) if hour else None,
             (origin-last)/60 if last is not None else None]
    dt=datetime.fromtimestamp(origin,timezone.utc)
    day=(dt.hour+dt.minute/60)*2*math.pi/24
    week=dt.weekday()*2*math.pi/7
    x=[np.nan if v is None else float(v) for v in history]
    x += [int(v is None) for v in history]
    x += [math.sin(day),math.cos(day),math.sin(week),math.cos(week)]
    age=(origin-last)/60 if last is not None else None
    return x,age,values.get(last)


def fallback(current_available,age,last,model_value):
    if current_available:
        return model_value,'fresh_model',True
    if age is not None and age<=MAX_STALE_MINUTES:
        return last,'stale_persistence',False
    return None,'abstain',False


def main():
    if OUT.exists():raise SystemExit('Stress output exists; reuse it. No overwrite.')
    tick=time.perf_counter()
    manifest=json.loads((t.OUT/'run_manifest.json').read_text())
    for name,digest in manifest['artifacts_sha256'].items():
        if r.b.digest(t.OUT/name)!=digest:raise ValueError(f'Interval artifact changed: {name}')
    summary=json.loads((r.DEST/'summary.json').read_text())
    if r.b.digest(r.b.DB)!=summary['source_database_sha256']:raise ValueError('Database changed')
    cohort=json.loads(r.b.MANIFEST.read_text())
    cal=json.loads((t.OUT/'calibration.json').read_text())['groups']
    split=next(s for s in summary['splits'] if s['name']=='test')
    start,end=r.b.epoch(split['start_inclusive']),r.b.epoch(split['end_exclusive'])
    OUT.mkdir(parents=True)
    policy={'status':'policy_frozen_before_test_scoring','seed':SEED,'scenarios':SCENARIOS,
            'masking':'Synthetic masks applied to history copies only, on all original observed timestamps. Recompute exact lags, trailing mean/count, missing flags and age from surviving history. Stable SHA256 schedule independent of values and shared across technologies for each station/sector.',
            'synthetic_drop10':'Independently scheduled approximately 10% of observed time slots hidden; coincident consecutive drops possible.',
            'synthetic_hour':'One deterministic UTC hour (four clock slots) hidden per station/sector/date, scheduled between 06:00 and 20:00 inclusive.',
            'natural_missing_origins':'Original missing-current origins with observed future answer; no injected mask. Separate population, not paired with synthetic/clean rows.',
            'population':'Final-time test only, shared existing boundaries; purge labels reaching end. Synthetic and clean scenarios have identical originally observed-current origins and measured future labels. Natural analysis includes missing-current origins on first-to-last grid with measured future labels. Exclude missing future labels, never fabricate ground truth.',
            'model_policy':'Frozen tuning-selected point model and existing calibrated quantiles, no training, tuning, recalibration or parameter search. Stress coverage is diagnostic under changed inputs, not a guaranteed interval.',
            'fallback':f'Fresh current: model point/range. Missing current: last observed utilization only if age <= {MAX_STALE_MINUTES} min, labeled stale; no interval. Older or absent history: no point or interval. Fixed illustrative operational threshold, not optimized or operationally validated.',
            'max_stale_minutes':MAX_STALE_MINUTES,'features':r.INPUTS,'splits':summary['splits'],
            'station_holdout':summary['station_holdout'],'script_sha256':r.b.digest(Path(__file__)),
            'interval_manifest_sha256':r.b.digest(t.OUT/'run_manifest.json'),
            'source_database_sha256':r.b.digest(r.b.DB),'versions':manifest['versions'],'threads':2}
    r.b.dump(OUT/'policy.json',policy)
    stats=defaultdict(lambda:[0,0,0.,0.,0,0,0.,0,0,0])
    # n / points / abs / sq / ranges / inside / width / fresh / stale / abstain
    populations=defaultdict(Counter)
    masks=[]
    with sqlite3.connect(r.b.DB.as_uri()+'?mode=ro',uri=True) as con, gzip.open(OUT/'forecasts.csv.gz','wt',newline='',encoding='utf-8') as stream,threadpool_limits(limits=2):
        writer=csv.writer(stream)
        writer.writerow(['scenario','role','technology','band_mhz','station','sector','origin_utc','target_utc','horizon_minutes','actual_pct','current_available','age_minutes','unrestricted_point_pct','unrestricted_lower_pct','unrestricted_upper_pct','operational_point_pct','operational_lower_pct','operational_upper_pct','operational_state'])
        for series in cohort['series']:
            tech,band,station,sector=(series[k] for k in ('technology','band_mhz','station','sector'))
            role=series['role']
            original=dict(con.execute('SELECT timestamp,utilization_pct FROM observed WHERE technology=? AND band_mhz=? AND station=? AND sector=?',(tech,band,station,sector)))
            grid=list(range(max(start,min(original)),min(end,max(original)+900),900))
            for scenario in SCENARIOS:
                visible={stamp:v for stamp,v in original.items() if not hidden(station,sector,stamp,scenario)}
                times=sorted(visible)
                masks.append({'scenario':scenario,'technology':tech,'station':station,'sector':sector,'history_observed':len(original),'history_hidden':len(original)-len(visible),
                              'test_observed':sum(start<=p<end for p in original),
                              'test_hidden':sum(start<=p<end and p not in visible for p in original)})
                for h in r.b.HORIZONS:
                    origins=[]
                    count=populations[(role,tech,h,scenario)]
                    for origin in grid:
                        if origin+h*60>=end:
                            count['boundary_purged']+=1;continue
                        count['grid_origins']+=1
                        if origin+h*60 not in original:
                            count['missing_future_label']+=1;continue
                        if (origin not in original)!=(scenario=='natural_missing_origins'):
                            count['outside_origin_population']+=1;continue
                        origins.append(origin)
                    if not origins:continue
                    extracted=[features_at(visible,times,origin) for origin in origins]
                    x=np.array([v[0] for v in extracted],dtype=float)
                    key=f'{tech}_{h}m'
                    point_name=manifest['point_choices_from_tuning'][key]
                    point_folder={'hgb':t.l.PREVIOUS,'lightgbm':t.l.OUT,'ridge':r.OUT}
                    pm=joblib.load(point_folder[point_name]/f'{key}.joblib') if point_name!='persistence' else None
                    point=np.clip(pm.predict(x),0,100) if pm else x[:,0]
                    qm=[joblib.load(t.OUT/f'{key}_q{a:.2f}.joblib') for a in t.LEVELS]
                    q,_=t.predict_quantiles(qm,x)
                    q=t.adjusted(q,cal[key]['correction_pp'])
                    for i,origin in enumerate(origins):
                        actual=original[origin+h*60]
                        age,last=extracted[i][1:]
                        fresh=origin in visible
                        p,state,has_interval=fallback(fresh,age,last,float(point[i]))
                        writer.writerow([scenario,role,tech,band,station,sector,r.b.iso(origin),r.b.iso(origin+h*60),h,actual,int(fresh),age,point[i],q[i,0],q[i,2],p,q[i,0] if has_interval else None,q[i,2] if has_interval else None,state])
                        for strategy,pred,interval in (('unrestricted_model',float(point[i]),True),('bounded_fallback',p,has_interval)):
                            for scope,a,b in (('pooled','all','all'),('series',station,sector)):
                                g=(scenario,role,tech,h,strategy,scope,a,b)
                                z=stats[g];z[0]+=1
                                if pred is not None and np.isfinite(pred):
                                    error=pred-actual;z[1]+=1;z[2]+=abs(error);z[3]+=error*error
                                if interval:
                                    z[4]+=1;z[5]+=q[i,0]<=actual<=q[i,2];z[6]+=q[i,2]-q[i,0]
                                z[7]+=state=='fresh_model';z[8]+=state=='stale_persistence';z[9]+=state=='abstain'
                    count['scorable_future_labels']+=len(origins)
            print(f'Checked missing readings: {tech} {station}, sector {sector}',flush=True)
    metrics=[]
    for key,z in sorted(stats.items()):
        n,npred,absolute,squared,nrange,inside,width,nfresh,nstale,nabstain=z
        metrics.append(dict(zip(('scenario','role','technology','horizon_minutes','strategy','scope','station','sector'),key))|
                       {'eligible_rows':n,'point_rows':npred,'point_availability':npred/n,
                        'mae_pp':absolute/npred if npred else None,'rmse_pp':(squared/npred)**.5 if npred else None,
                        'interval_rows':nrange,'interval_availability':nrange/n,'interval_coverage':inside/nrange if nrange else None,
                        'mean_width_pp':width/nrange if nrange else None,'fresh_rows':nfresh,'stale_rows':nstale,'abstain_rows':nabstain})
    r.b.dump(OUT/'metrics.json',metrics)
    r.b.dump(OUT/'populations.json',[dict(zip(('role','technology','horizon_minutes','scenario'),k))|dict(v) for k,v in sorted(populations.items())])
    r.b.dump(OUT/'masks.json',masks)
    policy.update(status='complete',elapsed_seconds=time.perf_counter()-tick)
    report(policy,metrics)
    policy['artifacts_sha256']={p.name:r.b.digest(p) for p in sorted(OUT.iterdir()) if p.is_file()}
    r.b.dump(OUT/'run_manifest.json',policy)
    print(f"Completed in {policy['elapsed_seconds']:.1f}s; {OUT/'Results.md'}")


def report(policy,metrics):
    lines=['# What happens when readings disappear?','',
           'No model was retrained. No original measurements or future answers were changed. These are historical replay stress tests, not real outage incidents or a validated live operating policy.','',
           '## Three paired input conditions','',
           '- Clean: keep original history and originally observed-current forecast questions.',
           '- Artificial 10% drops: hide roughly one in ten history readings; recompute every dependent feature.',
           '- Artificial one-hour gaps: hide four consecutive clock slots once per UTC date for each series.','',
           'Natural missing-current origins are a separate population below. They cannot be directly ranked against the paired synthetic rows. Missing future answers are never scored; grid and exclusion counts are in populations.json.','',
           '## Average prediction error for familiar stations','',
           'The table deliberately shows the unrestricted frozen model first: it attempts predictions even with missing inputs. Lower error is better. Inside-range rate means how often the actual answer falls inside the previously calibrated range; those ranges were not recalibrated for outages.','',
           '| Network | Ahead | Input condition | Questions | Average error (percentage points) | Actual readings inside range |',
           '|---|---:|---|---:|---:|---:|']
    names={'clean_observed_origins':'Original history','synthetic_drop10':'Artificial 10% drops','synthetic_hour':'Artificial one-hour gaps'}
    for tech in ('LTE','NR'):
        for h in r.b.HORIZONS:
            for scenario in names:
                v=next(v for v in metrics if v['scope']=='pooled' and v['role']=='development' and v['technology']==tech and v['horizon_minutes']==h and v['scenario']==scenario and v['strategy']=='unrestricted_model')
                lines.append(f"| {'4G' if tech=='LTE' else '5G'} | {h} min | {names[scenario]} | {v['eligible_rows']:,} | {v['mae_pp']:.3f} | {v['interval_coverage']:.1%} |")
    lines+=['','## Fixed fallback rule tested','',
            'With a fresh current reading, return the model forecast/range. If it is missing but the last reading is at most 60 minutes old, return that last reading as a clearly labeled stale estimate and withhold the range. If older, return no estimate. This cutoff was declared before test scoring, not optimized from the test results. It is an illustrative policy, not proof of the safest or best action.','',
            'Withholding an interval reduces availability; it does not prove the remaining intervals are calibrated. Missing history can still affect fresh-current forecasts. Do not compare errors of policies on differing row subsets without also reporting availability.','',
            '## Naturally missing-current origins only','',
            '| Station group | Network | Ahead | Observed future answers | Stale estimates returned | No point estimate |',
            '|---|---|---:|---:|---:|---:|']
    for v in metrics:
        if v['scope']=='pooled' and v['scenario']=='natural_missing_origins' and v['strategy']=='bounded_fallback':
            lines.append(f"| {v['role']} | {'4G' if v['technology']=='LTE' else '5G'} | {v['horizon_minutes']} min | {v['eligible_rows']:,} | {v['point_rows']:,} | {v['abstain_rows']:,} |")
    lines+=['','## Files','',
            '- `policy.json`: outage schedules, thresholds and population rules declared before scoring.',
            '- `forecasts.csv.gz`: original future answers, stressed predictions, age, fallback/abstention and optional ranges.',
            '- `metrics.json`: per-series and pooled errors, point/range availability and inclusion rate for both strategies, with station holdout separate.',
            '- `populations.json`: clock origins, missing-answer exclusions and boundary purges.',
            '- `masks.json`: measured hidden-history counts; no raw file mutation.',
            '- `run_manifest.json`: timing, source/output hashes, versions and frozen rules.','',
            f"Measured full script time: {policy['elapsed_seconds']:.1f}s; two numerical threads. Peak process memory not measured.",'',
            'Next: quantify uncertainty across station/day blocks and benchmark memory/latency; then implement the prediction interface and historical replay screen. A degraded range must not be presented as reliably 90% during outages.']
    (OUT/'Results.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')


if __name__=='__main__':main()

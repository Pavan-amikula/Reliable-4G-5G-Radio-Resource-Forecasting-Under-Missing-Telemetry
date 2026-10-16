"""Saved-forecast resampling, rare-load support and isolated inference benchmark."""
import argparse
from collections import defaultdict
import csv
import ctypes
from ctypes import wintypes
import gzip
import json
from pathlib import Path
import platform
import sqlite3
import subprocess
import sys
import time

import stress_telemetry as s
import joblib
import numpy as np
from threadpoolctl import threadpool_limits

r=s.r
OUT=r.b.ROOT/'outputs/reliability_v1'
REPEATS=500
SEED=20261017


def resample_blocks(blocks, repeats=REPEATS, seed=SEED):
    """Crossed station + consecutive two-calendar-day moving-block weights."""
    # Each entry: station, UTC target date -> n, point absolute error,
    # persistence absolute error, included count, width sum.
    stations=sorted({k[0] for k in blocks})
    days=sorted({k[1] for k in blocks})
    array=np.zeros((len(stations),len(days),5))
    for (station,day),values in blocks.items():
        array[stations.index(station),days.index(day)]=values
    rng=np.random.default_rng(seed)
    samples=[]
    for _ in range(repeats):
        station_ids=rng.integers(0,len(stations),size=len(stations))
        day_ids=[]
        while len(day_ids)<len(days):
            start=int(rng.integers(0,max(1,len(days)-1)))
            day_ids.extend(range(start,min(start+2,len(days))))
        day_ids=day_ids[:len(days)]
        totals=array[station_ids][:,day_ids].sum(axis=(0,1))
        n,point,persistence,inside,width=totals
        if n:
            samples.append([(point-persistence)/n,point/n,persistence/n,inside/n,width/n])
    if not samples:raise ValueError('No valid resampling draws')
    total=array.sum(axis=(0,1));n,point,persistence,inside,width=total
    estimates={'error_difference_pp':(point-persistence)/n,'model_mae_pp':point/n,
               'persistence_mae_pp':persistence/n,'interval_coverage':inside/n,'mean_width_pp':width/n}
    samples=np.asarray(samples)
    ranges={name:{'estimate':float(value),'resampling_low':float(np.quantile(samples[:,i],.025)),
                  'resampling_high':float(np.quantile(samples[:,i],.975))}
            for i,(name,value) in enumerate(estimates.items())}
    return {'n':int(n),'stations':stations,'calendar_dates':days,'station_count':len(stations),
            'date_count':len(days),'valid_draws':len(samples),'summaries':ranges}


def memory_stats():
    if sys.platform!='win32':raise RuntimeError('This memory measurement requires Windows')
    class Counters(ctypes.Structure):
        _fields_=[('cb',wintypes.DWORD),('PageFaultCount',wintypes.DWORD)]+[(name,ctypes.c_size_t) for name in
            ('PeakWorkingSetSize','WorkingSetSize','QuotaPeakPagedPoolUsage','QuotaPagedPoolUsage',
             'QuotaPeakNonPagedPoolUsage','QuotaNonPagedPoolUsage','PagefileUsage','PeakPagefileUsage')]
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    psapi=ctypes.WinDLL('psapi',use_last_error=True)
    kernel.GetCurrentProcess.restype=wintypes.HANDLE
    psapi.GetProcessMemoryInfo.argtypes=[wintypes.HANDLE,ctypes.POINTER(Counters),wintypes.DWORD]
    psapi.GetProcessMemoryInfo.restype=wintypes.BOOL
    value=Counters();value.cb=ctypes.sizeof(value)
    if not psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(),ctypes.byref(value),value.cb):
        raise ctypes.WinError(ctypes.get_last_error())
    return {'working_set_mib':value.WorkingSetSize/2**20,'peak_working_set_mib':value.PeakWorkingSetSize/2**20,
            'commit_mib':value.PagefileUsage/2**20,'peak_commit_mib':value.PeakPagefileUsage/2**20}


def timing_summary(samples):
    return {'repetitions':len(samples),'median_ms':float(np.median(samples)),
            'p95_ms':float(np.quantile(samples,.95)),'min_ms':float(min(samples)),
            'max_ms':float(max(samples))}


def benchmark_worker(path):
    # Fresh process keeps reliability/resampling arrays out of the benchmark.
    before=memory_stats()
    selected=json.loads((s.t.OUT/'selection.json').read_text())
    calibration=json.loads((s.t.OUT/'calibration.json').read_text())['groups']
    loaded={}
    tick=time.perf_counter()
    with threadpool_limits(limits=2):
        for tech in ('LTE','NR'):
            for h in r.b.HORIZONS:
                key=f'{tech}_{h}m';name=selected['point_choices_from_tuning'][key]
                folders={'hgb':s.t.l.PREVIOUS,'lightgbm':s.t.l.OUT,'ridge':r.OUT}
                point=joblib.load(folders[name]/f'{key}.joblib') if name!='persistence' else None
                qs=[joblib.load(s.t.OUT/f'{key}_q{a:.2f}.joblib') for a in s.t.LEVELS]
                loaded[key]=(point,qs,calibration[key]['correction_pp'])
    loading=time.perf_counter()-tick
    histories={}
    with sqlite3.connect(r.b.DB.as_uri()+'?mode=ro',uri=True) as con:
        for tech,band in (('LTE',1800),('NR',2100)):
            values=dict(con.execute('SELECT timestamp,utilization_pct FROM observed WHERE technology=? AND band_mhz=? AND station=? AND sector=?',(tech,band,'Site 16','1')))
            times=sorted(values)
            origins=[v for v in times if v>=r.b.epoch('2025-04-26T00:00:00+00:00')][:128]
            if len(origins)!=128:raise ValueError('Need 128 representative histories')
            histories[tech]=(values,times,origins)
    def predict(tech,origins):
        values,times,_=histories[tech]
        x=np.asarray([s.features_at(values,times,origin)[0] for origin in origins])
        answer=[]
        for h in r.b.HORIZONS:
            point,qs,amount=loaded[f'{tech}_{h}m']
            p=np.clip(point.predict(x),0,100) if point else x[:,0]
            q,_=s.t.predict_quantiles(qs,x);q=s.t.adjusted(q,amount)
            if not np.isfinite(p).all() or not np.isfinite(q).all():raise ValueError('Invalid inference')
            answer.append((p,q))
        return answer
    timings={}
    with threadpool_limits(limits=2):
        for tech in ('LTE','NR'):
            origins=histories[tech][2]
            for _ in range(5):predict(tech,origins[:1])
            samples=[]
            for _ in range(50):
                tick=time.perf_counter();predict(tech,origins[:1]);samples.append((time.perf_counter()-tick)*1000)
            batch=[]
            for _ in range(20):
                tick=time.perf_counter();predict(tech,origins);batch.append((time.perf_counter()-tick)*1000)
            timings[tech]={'single_series_all_three_horizons':timing_summary(samples),
                           'batch_128_histories_all_three_horizons':timing_summary(batch),
                           'batch_median_ms_per_history':float(np.median(batch)/128),
                           'single_samples_ms':samples,'batch_samples_ms':batch}
    result={'status':'complete','platform':platform.platform(),'machine':platform.machine(),
            'processor':platform.processor(),'python':sys.version,'threads':2,
            'loaded_point_models':6,'loaded_quantile_models':18,'model_loading_seconds':loading,
            'before_loading_memory':before,'after_benchmark_memory':memory_stats(),'timings':timings,
            'scope':'Fresh Windows worker. Cache all six point and 18 interval models. Time feature rebuilding from in-memory history plus point/quantile prediction, sorting/clipping/calibration for all three horizons. First 128 final-period observed origins for Site16 sector1 per technology. Five warmups; 50 single and20batch repetitions. No model fit, disk reads, model loading, serialization, HTTP server, UI or concurrency inside timed calls. Peak memory includes worker imports, loading, cached histories and inference; not full-training RAM or whole-system RAM.'}
    r.b.dump(path,result)


def main():
    if OUT.exists():raise SystemExit('Reliability output exists; reuse it. No overwrite.')
    started=time.perf_counter()
    manifest=json.loads((s.t.OUT/'run_manifest.json').read_text())
    for name,digest in manifest['artifacts_sha256'].items():
        if r.b.digest(s.t.OUT/name)!=digest:raise ValueError(f'Interval artifact changed: {name}')
    cohort=json.loads(r.b.MANIFEST.read_text())
    if r.b.digest(r.b.DB)!=cohort['database_sha256']:raise ValueError('Observed database changed')
    OUT.mkdir(parents=True)
    protocol={'status':'frozen_before_analysis','seed':SEED,'draws':REPEATS,
              'resampling':'Sample whole stations with replacement, and shared moving blocks of two adjacent UTC target dates with replacement until original number of dates is reached. Cross the station and date weights, preserving both sectors and contemporaneous errors within sampled blocks. Noncircular date blocks; small endpoint-weight effects and partial days retained. Equal calendar-date clusters but pooled row-weighted metrics within a draw.',
              'limits':'Exploratory 2.5/97.5 percentile resampling ranges, not robust proof of significance. Only four familiar stations, one excluded station and ten target dates; two-day block choice does not establish independence or eliminate long-range dependence. The excluded station has no between-station replication. No feature, model, calibration or policy selection from these results.',
              'benchmark':'Fresh child process, two threads, all24 saved models cached; single/batch128 timing for three horizons plus features. Windows peak working set/commit from process counters.',
              'high_load':'Fixed exploratory utilization >=80%; contiguous15min runs within split/series, not independent congestion incidents.',
              'script_sha256':r.b.digest(Path(__file__)),'source_database_sha256':r.b.digest(r.b.DB),
              'interval_manifest_sha256':r.b.digest(s.t.OUT/'run_manifest.json'),'versions':manifest['versions']}
    r.b.dump(OUT/'protocol.json',protocol)
    blocks=defaultdict(lambda:defaultdict(lambda:np.zeros(5)))
    day_stats=defaultdict(lambda:np.zeros(5))
    with sqlite3.connect(r.b.DB.as_uri()+'?mode=ro',uri=True) as con:
        observations={tuple(v[:5]):v[5] for v in con.execute('SELECT technology,band_mhz,station,sector,timestamp,utilization_pct FROM observed')}
    with gzip.open(s.t.OUT/'forecasts.csv.gz','rt',newline='') as f:
        for v in csv.DictReader(f):
            if v['split']!='test':continue
            key=(v['role'],v['technology'],int(v['horizon_minutes']))
            origin=r.b.epoch(v['origin_utc'])
            persistence=observations[(v['technology'],int(v['band_mhz']),v['station'],v['sector'],origin)]
            y=float(v['actual_pct']);p=float(v['point_pct']);lo=float(v['calibrated_lower_pct']);hi=float(v['calibrated_upper_pct'])
            values=np.array([1,abs(p-y),abs(persistence-y),float(lo<=y<=hi),hi-lo])
            day=v['target_utc'][:10]
            blocks[key][v['station'],day]+=values
            day_stats[(*key,v['station'],day)]+=values
    uncertainty=[]
    for key,values in sorted(blocks.items()):
        result=resample_blocks(values)
        uncertainty.append(dict(zip(('role','technology','horizon_minutes'),key))|result)
    r.b.dump(OUT/'resampling.json',uncertainty)
    r.b.dump(OUT/'station_days.json',[dict(zip(('role','technology','horizon_minutes','station','target_date_utc'),key))|
              {'n':int(v[0]),'model_mae_pp':v[1]/v[0],'persistence_mae_pp':v[2]/v[0],
               'coverage':v[3]/v[0],'mean_width_pp':v[4]/v[0]} for key,v in sorted(day_stats.items())])
    # Unique observed timestamps, not tripled horizon-label rows.
    support=defaultdict(lambda:{'observed_rows':0,'high_rows':0,'runs':0,'series':set(),'stations':set()})
    splits=[(v['name'],r.b.epoch(v['start_inclusive']),r.b.epoch(v['end_exclusive'])) for v in manifest['splits']]
    for series in cohort['series']:
        tech,band,station,sector=(series[k] for k in ('technology','band_mhz','station','sector'))
        values=sorted((key[4],value) for key,value in observations.items() if key[:4]==(tech,band,station,sector))
        for name,start,end in splits:
            entry=support[series['role'],tech,name]
            last_high=None
            for stamp,value in values:
                if not start<=stamp<end:continue
                entry['observed_rows']+=1
                if value>=80:
                    entry['high_rows']+=1;entry['series'].add(f'{station}|{sector}');entry['stations'].add(station)
                    if last_high is None or stamp-last_high!=900:entry['runs']+=1
                    last_high=stamp
    support_rows=[]
    for key,value in sorted(support.items()):
        support_rows.append(dict(zip(('role','technology','split'),key))|value|{'series':sorted(value['series']),'stations':sorted(value['stations'])})
    r.b.dump(OUT/'high_load_support.json',support_rows)
    completed=subprocess.run([sys.executable,str(Path(__file__).resolve()),'--benchmark-worker',str(OUT/'benchmark.json')],capture_output=True,text=True,timeout=120)
    if completed.returncode:raise RuntimeError(completed.stderr or completed.stdout)
    benchmark=json.loads((OUT/'benchmark.json').read_text())
    protocol.update(status='complete',elapsed_seconds=time.perf_counter()-started)
    report(protocol,uncertainty,benchmark,support_rows)
    protocol['artifacts_sha256']={p.name:r.b.digest(p) for p in sorted(OUT.iterdir()) if p.is_file()}
    r.b.dump(OUT/'run_manifest.json',protocol)
    print(f"Reliability checks completed in {protocol['elapsed_seconds']:.1f}s; {OUT/'Results.md'}")


def report(protocol,uncertainty,benchmark,support):
    lines=['# Consistency, prediction speed and memory','',
           'No models were trained. We checked saved final-period predictions, resampled whole station/date groups, counted rare high readings, and timed cached-model forecasts in a fresh Windows process.','',
           '## Does the selected point model beat repeating the latest reading?','',
           'Negative error difference means the selected model has lower average error. The exploratory range shows how the difference varies when whole stations and consecutive two-day groups are resampled. It is not a guaranteed future improvement or a formal independence-based significance claim. Same observed-current/observed-future rows are used for both methods.','',
           '| Station group | Network | Ahead | Model minus latest-reading error | Exploratory resampling range |',
           '|---|---|---:|---:|---|']
    for v in uncertainty:
        q=v['summaries']['error_difference_pp']
        lines.append(f"| {v['role']} | {'4G' if v['technology']=='LTE' else '5G'} | {v['horizon_minutes']} min | {q['estimate']:.3f} | {q['resampling_low']:.3f} to {q['resampling_high']:.3f} |")
    lines+=['', 'Only four familiar stations, one excluded station and ten calendar dates are available. Resampling cannot create independent new stations or days. Adjacent-day dependence and partial-day/end-weight effects remain. Coverage resampling and per-station/day metrics are in the JSON files; do not treat pooled ~90% coverage as a per-station guarantee.','',
            '## Speed for one sector: all three horizons and their ranges','',
            'Each call rebuilds features from in-memory history and returns point forecasts plus calibrated ranges at 15/30/60 minutes. Models were already loaded. The timed path excludes HTTP/UI, serialization, disk history retrieval and model loading.','',
            '| Network | Typical single-call time | 95th percentile time | Typical batch of 128 histories |',
            '|---|---:|---:|---:|']
    for tech in ('LTE','NR'):
        q=benchmark['timings'][tech]
        a=q['single_series_all_three_horizons'];b=q['batch_128_histories_all_three_horizons']
        lines.append(f"| {'4G' if tech=='LTE' else '5G'} | {a['median_ms']:.2f} ms | {a['p95_ms']:.2f} ms | {b['median_ms']:.2f} ms |")
    memory=benchmark['after_benchmark_memory']
    lines+=['',f"The fresh benchmark worker cached 6 point and18 quantile models. Its measured peak working set was {memory['peak_working_set_mib']:.1f} MiB; peak commit charge {memory['peak_commit_mib']:.1f} MiB. These are process counters, not whole-laptop memory or training peak RAM. Model loading after imports took {benchmark['model_loading_seconds']:.2f}s. Timings vary with hardware, concurrent laptop activity and caching.",'',
            '## Do we have enough high-load examples?','',
            'The 80% threshold is a fixed experimental load marker, not confirmed congestion. Counts below use unique observed timestamps, not repeated horizon labels. Contiguous15-minute runs need not be independent.','',
            '| Station group | Network | Split | Observed readings | At least80% | Contiguous runs |',
            '|---|---|---|---:|---:|---:|']
    for v in support:
        if v['split'] in ('calibration','test'):
            lines.append(f"| {v['role']} | {'4G' if v['technology']=='LTE' else '5G'} | {v['split']} | {v['observed_rows']:,} | {v['high_rows']} | {v['runs']} |")
    lines+=['','Do not claim validated congestion-warning precision/recall from sparse or absent positive examples. This remains a utilization-forecasting project.','',
            '## Files','',
            '- `protocol.json`: frozen analysis/resampling/benchmark rules.',
            '- `resampling.json`: point differences, errors, range inclusion and width with exploratory ranges.',
            '- `station_days.json`: individual station/day results.',
            '- `high_load_support.json`: unique high-load readings/runs by split.',
            '- `benchmark.json`: raw timings, process-memory counters and benchmark scope.',
            '- `run_manifest.json`: versions, source/output hashes and elapsed time.','',
            f"Overall analysis elapsed time: {protocol['elapsed_seconds']:.1f}s. No raw audits, extraction or training were repeated.",'',
            'Next: implement a local prediction API returning predictions/ranges plus fresh/stale/no-estimate status, with strict historical-input validation. Then add a historical replay screen. The API, HTTP latency, concurrent users and live-network operation have not been measured here.','',
            'Windows counter reference: [GetProcessMemoryInfo](https://learn.microsoft.com/en-us/windows/win32/api/psapi/nf-psapi-getprocessmemoryinfo) and [PROCESS_MEMORY_COUNTERS](https://learn.microsoft.com/en-us/windows/win32/api/psapi/ns-psapi-process_memory_counters).']
    (OUT/'Results.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--benchmark-worker',type=Path)
    args=parser.parse_args()
    if args.benchmark_worker:benchmark_worker(args.benchmark_worker)
    else:main()

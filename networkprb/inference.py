"""Validated causal inference from frozen local artifacts; never fit or tune."""
import os
for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ.setdefault(name,'2')

from bisect import bisect_right
from contextlib import closing
from datetime import datetime,timezone
import hashlib
import json
import math
from pathlib import Path
import sqlite3

import joblib
import numpy as np
from threadpoolctl import threadpool_limits

ROOT=Path(__file__).resolve().parents[1]
MAX_HISTORY=800
HORIZONS=(15,30,60)
HISTORY=('current_pct','lag_15_pct','lag_30_pct','lag_60_pct','lag_1440_pct',
         'lag_10080_pct','observed_last_hour','mean_observed_last_hour','age_minutes')
INPUTS=(*HISTORY,*(v+'_missing' for v in HISTORY),'hour_sin','hour_cos','weekday_sin','weekday_cos')


class InputError(ValueError):
    pass


def utc_seconds(value):
    if not isinstance(value,str) or len(value)>40:
        raise InputError('Timestamp must be an ISO date/time string with a UTC offset.')
    try:
        parsed=datetime.fromisoformat(value.replace('Z','+00:00'))
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise InputError('Include Z or an explicit UTC offset in every timestamp.')
        seconds=parsed.timestamp()
    except (ValueError,OverflowError,OSError) as exc:
        raise InputError('Invalid timestamp; include a valid date/time and UTC offset.') from exc
    if not math.isfinite(seconds) or seconds%900 or parsed.microsecond:
        raise InputError('Timestamps must be on exact 15-minute UTC clock intervals.')
    return int(seconds)


def iso(seconds):
    return datetime.fromtimestamp(seconds,timezone.utc).isoformat()


def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()


def validate_request(payload,cohort_keys,start,end):
    fields={'technology','band_mhz','station','sector','origin_utc','history'}
    if not isinstance(payload,dict) or set(payload)!=fields:
        raise InputError('Provide exactly technology, band_mhz, station, sector, origin_utc and history.')
    tech,band,station,sector=(payload[k] for k in ('technology','band_mhz','station','sector'))
    if tech not in ('LTE','NR') or type(band) is not int or band!={'LTE':1800,'NR':2100}.get(tech):
        raise InputError('Supported combinations are LTE/1800 and NR/2100.')
    if not isinstance(station,str) or not isinstance(sector,str) or (tech,band,station,sector) not in cohort_keys:
        raise InputError('Choose a station/sector in the evaluated cohort returned by /series.')
    origin=utc_seconds(payload['origin_utc'])
    if not start<=origin<end:
        raise InputError(f'This replay version supports origins from {iso(start)} to {iso(end)} exclusive.')
    history=payload['history']
    if not isinstance(history,list) or len(history)>MAX_HISTORY:
        raise InputError(f'History must be a list with at most {MAX_HISTORY} observed readings.')
    values={}
    for entry in history:
        if not isinstance(entry,dict) or set(entry)!={'timestamp_utc','utilization_pct'}:
            raise InputError('Each history entry needs exactly timestamp_utc and utilization_pct.')
        stamp=utc_seconds(entry['timestamp_utc'])
        value=entry['utilization_pct']
        if isinstance(value,bool) or not isinstance(value,(float,int)):
            raise InputError('Utilization must be a finite number from 0 to 100; omit missing readings.')
        try:valid=math.isfinite(value) and 0<=value<=100
        except OverflowError:valid=False
        if not valid:raise InputError('Utilization must be a finite number from 0 to 100.')
        if stamp>origin:raise InputError('Future readings are forbidden: every history timestamp must be at or before the forecast origin.')
        if stamp in values:raise InputError('Duplicate history timestamps are forbidden, even when values match.')
        values[stamp]=float(value)
    return (tech,band,station,sector),origin,values


def features(values,origin):
    # Same exact timestamp and four-clock-slot rules as the evaluated scripts.
    times=sorted(values)
    index=bisect_right(times,origin)-1
    last=times[index] if index>=0 else None
    hour=[values[p] for p in range(origin-2700,origin+1,900) if p in values]
    h=[values.get(origin),*(values.get(origin-v*60) for v in (15,30,60,1440,10080)),
       len(hour),sum(hour)/len(hour) if hour else None,(origin-last)/60 if last is not None else None]
    dt=datetime.fromtimestamp(origin,timezone.utc)
    day=(dt.hour+dt.minute/60)*2*math.pi/24;week=dt.weekday()*2*math.pi/7
    vector=[np.nan if v is None else v for v in h]+[int(v is None) for v in h]
    vector+=[math.sin(day),math.cos(day),math.sin(week),math.cos(week)]
    return np.asarray([vector],dtype=float),last,h[-1],[name for name,v in zip(HISTORY,h) if v is None]


class ForecastEngine:
    def __init__(self,root=ROOT):
        self.root=Path(root)
        self.interval_dir=self.root/'outputs/intervals_v1'
        manifest=json.loads((self.interval_dir/'run_manifest.json').read_text(encoding='utf-8'))
        for name,expected in manifest['artifacts_sha256'].items():
            if digest(self.interval_dir/name)!=expected:raise RuntimeError(f'Interval artifact integrity failure: {name}')
        self.selection=json.loads((self.interval_dir/'selection.json').read_text(encoding='utf-8'))
        self.calibration=json.loads((self.interval_dir/'calibration.json').read_text(encoding='utf-8'))['groups']
        if tuple(self.selection['features'])!=INPUTS:raise RuntimeError('Model input schema mismatch')
        cohort=json.loads((self.root/'data/processed/manifest_v1.json').read_text(encoding='utf-8'))
        self.series=cohort['series']
        self.cohort_keys={(v['technology'],v['band_mhz'],v['station'],v['sector']) for v in self.series}
        self.holdout=cohort['station_holdout']
        test=next(v for v in self.selection['splits'] if v['name']=='test')
        self.start=utc_seconds(test['start_inclusive']);self.end=utc_seconds(test['end_exclusive'])
        self.database=self.root/'data/processed/observed_v1.sqlite'
        if digest(self.database)!=cohort['database_sha256']:raise RuntimeError('Observed database integrity failure')
        self.models={}
        with threadpool_limits(limits=2):
            for tech in ('LTE','NR'):
                for h in HORIZONS:
                    key=f'{tech}_{h}m';name=self.selection['point_choices_from_tuning'][key]
                    point=None
                    if name!='persistence':
                        folder=self.root/'outputs'/({'hgb':'hgb_v1','lightgbm':'lightgbm_v1','ridge':'ridge_v1'}[name])
                        expected=json.loads((folder/'run_manifest.json').read_text(encoding='utf-8'))['artifacts_sha256'][f'{key}.joblib']
                        if digest(folder/f'{key}.joblib')!=expected:raise RuntimeError('Point model integrity failure')
                        point=joblib.load(folder/f'{key}.joblib')
                    qs=[joblib.load(self.interval_dir/f'{key}_q{a:.2f}.joblib') for a in (.05,.5,.95)]
                    self.models[key]=(name,point,qs,self.calibration[key]['correction_pp'])

    def predict(self,payload):
        key,origin,values=validate_request(payload,self.cohort_keys,self.start,self.end)
        tech,band,station,sector=key
        x,last,age,missing=features(values,origin)
        fresh=origin in values
        state='fresh_model' if fresh else 'stale_persistence' if age is not None and age<=60 else 'abstain'
        forecasts=[]
        with threadpool_limits(limits=2):
            for h in HORIZONS:
                name,point,qs,amount=self.models[f'{tech}_{h}m']
                predicted=lower=upper=median=None
                if fresh:
                    predicted=float(np.clip(point.predict(x)[0],0,100)) if point is not None else values[origin]
                    q=np.clip(np.sort([float(m.predict(x)[0]) for m in qs]),0,100)
                    lower=max(0.,float(q[0])-amount);upper=min(100.,float(q[2])+amount);median=float(q[1])
                elif state=='stale_persistence':predicted=values[last]
                forecasts.append({'horizon_minutes':h,'target_utc':iso(origin+h*60),
                                  'target_within_evaluated_period':origin+h*60<self.end,
                                  'predicted_utilization_pct':predicted,
                                  'range_lower_pct':lower,'range_upper_pct':upper,'quantile_median_pct':median,
                                  'method':name if fresh else 'last_observed_value' if state=='stale_persistence' else None})
        return {'schema_version':1,'mode':'historical_replay',
                'series':{'technology':tech,'band_mhz':band,'station':station,'sector':sector},
                'origin_utc':iso(origin),'status':state,'last_observation_utc':iso(last) if last is not None else None,
                'age_minutes':age,'history_readings_provided':len(values),'missing_inputs':missing,
                'range_status':'available_with_history_gaps' if fresh and missing else 'available' if fresh else 'withheld',
                'range_target_fraction':.90,'range_coverage_guaranteed':False,
                'forecasts':forecasts,
                'interpretation':'Recorded-data replay. Fresh means a current reading is supplied; it does not guarantee complete history or reliable ranges during missing telemetry. Stale fallback uses a fixed illustrative 60-minute limit. Counter availability at its timestamp is assumed.'}

    def series_info(self):
        return {'mode':'historical_replay','origin_start_inclusive':iso(self.start),'origin_end_exclusive':iso(self.end),
                'horizons_minutes':list(HORIZONS),'series':[{k:v[k] for k in ('technology','band_mhz','station','sector','role')} for v in self.series]}

    def example(self):
        tech,band,station,sector='LTE',1800,'Site 16','1'
        origin=self.start
        with closing(sqlite3.connect(self.database.as_uri()+'?mode=ro',uri=True)) as con:
            rows=con.execute('SELECT timestamp,utilization_pct FROM observed WHERE technology=? AND band_mhz=? AND station=? AND sector=? AND timestamp>=? AND timestamp<=? ORDER BY timestamp',
                             (tech,band,station,sector,origin-7*86400,origin)).fetchall()
        return {'technology':tech,'band_mhz':band,'station':station,'sector':sector,'origin_utc':iso(origin),
                'history':[{'timestamp_utc':iso(stamp),'utilization_pct':value} for stamp,value in rows]}

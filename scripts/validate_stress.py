"""Reproduce outage outputs without changing observations or fitting models."""
from collections import defaultdict
import csv
import gzip
from itertools import groupby
import json
import sqlite3

import stress_telemetry as s
import joblib
import numpy as np
from threadpoolctl import threadpool_limits


def main():
    manifest=json.loads((s.OUT/'run_manifest.json').read_text())
    interval=json.loads((s.t.OUT/'run_manifest.json').read_text())
    cal=json.loads((s.t.OUT/'calibration.json').read_text())['groups']
    assert s.r.b.digest(s.r.b.DB)==manifest['source_database_sha256']
    for name,digest in manifest['artifacts_sha256'].items():assert s.r.b.digest(s.OUT/name)==digest
    for name,digest in interval['artifacts_sha256'].items():assert s.r.b.digest(s.t.OUT/name)==digest
    baseline={}
    with gzip.open(s.t.OUT/'forecasts.csv.gz','rt',newline='') as f:
        for v in csv.DictReader(f):
            if v['split']!='test':continue
            key=(v['technology'],v['station'],v['sector'],v['origin_utc'],int(v['horizon_minutes']))
            baseline[key]=tuple(float(v[k]) for k in ('actual_pct','point_pct','calibrated_lower_pct','calibrated_upper_pct'))
    stats=defaultdict(lambda:[0,0,0.,0.,0,0,0.,0,0,0])
    pairs=defaultdict(set)
    count=0
    summary=json.loads((s.r.DEST/'summary.json').read_text())
    end=s.r.b.epoch(next(v for v in summary['splits'] if v['name']=='test')['end_exclusive'])
    with sqlite3.connect(s.r.b.DB.as_uri()+'?mode=ro',uri=True) as con, gzip.open(s.OUT/'forecasts.csv.gz','rt',newline='') as f, threadpool_limits(limits=2):
        grouping=lambda v:(v['technology'],int(v['band_mhz']),v['station'],v['sector'],v['scenario'],int(v['horizon_minutes']))
        for (tech,band,station,sector,scenario,h),records in groupby(csv.DictReader(f),key=grouping):
            records=list(records)
            original=dict(con.execute('SELECT timestamp,utilization_pct FROM observed WHERE technology=? AND band_mhz=? AND station=? AND sector=?',(tech,band,station,sector)))
            visible={stamp:v for stamp,v in original.items() if not s.hidden(station,sector,stamp,scenario)}
            times=sorted(visible)
            extracted=[s.features_at(visible,times,s.r.b.epoch(v['origin_utc'])) for v in records]
            x=np.array([a[0] for a in extracted])
            key=f'{tech}_{h}m';name=interval['point_choices_from_tuning'][key]
            folders={'hgb':s.t.l.PREVIOUS,'lightgbm':s.t.l.OUT,'ridge':s.r.OUT}
            point=np.clip(joblib.load(folders[name]/f'{key}.joblib').predict(x),0,100) if name!='persistence' else x[:,0]
            models=[joblib.load(s.t.OUT/f'{key}_q{a:.2f}.joblib') for a in s.t.LEVELS]
            q,_=s.t.predict_quantiles(models,x);q=s.t.adjusted(q,cal[key]['correction_pp'])
            np.testing.assert_allclose(point,[float(v['unrestricted_point_pct']) for v in records],rtol=1e-12)
            np.testing.assert_allclose(q[:,[0,2]],[[float(v['unrestricted_lower_pct']),float(v['unrestricted_upper_pct'])] for v in records],rtol=1e-12)
            for i,v in enumerate(records):
                origin=s.r.b.epoch(v['origin_utc']);target=s.r.b.epoch(v['target_utc'])
                assert target==origin+h*60 and target<end
                actual=float(v['actual_pct']);assert actual==original[target]
                assert (origin not in original)==(scenario=='natural_missing_origins')
                assert (v['role']=='station_holdout')==(station==summary['station_holdout'])
                age,last=extracted[i][1:]
                assert (float(v['age_minutes']) if v['age_minutes'] else None)==age
                assert int(v['current_available'])==(origin in visible)
                p,state,ranged=s.fallback(origin in visible,age,last,float(point[i]))
                assert v['operational_state']==state
                assert (float(v['operational_point_pct']) if v['operational_point_pct'] else None)==p
                assert bool(v['operational_lower_pct'])==ranged
                pair=(tech,station,sector,v['origin_utc'],h)
                if scenario!='natural_missing_origins':pairs[scenario].add(pair)
                if scenario=='clean_observed_origins':
                    np.testing.assert_allclose([actual,point[i],q[i,0],q[i,2]],baseline[pair],rtol=1e-12)
                for strategy,pred,has_range in (('unrestricted_model',float(point[i]),True),('bounded_fallback',p,ranged)):
                    for scope,a,b in (('pooled','all','all'),('series',station,sector)):
                        key=(scenario,v['role'],tech,h,strategy,scope,a,b)
                        z=stats[key];z[0]+=1
                        if pred is not None:
                            error=pred-actual;z[1]+=1;z[2]+=abs(error);z[3]+=error*error
                        if has_range:z[4]+=1;z[5]+=q[i,0]<=actual<=q[i,2];z[6]+=q[i,2]-q[i,0]
                        z[7]+=state=='fresh_model';z[8]+=state=='stale_persistence';z[9]+=state=='abstain'
                count+=1
    assert pairs['clean_observed_origins']==pairs['synthetic_drop10']==pairs['synthetic_hour']==set(baseline)
    metrics=json.loads((s.OUT/'metrics.json').read_text())
    assert len(metrics)==len(stats)
    for v in metrics:
        key=tuple(v[k] for k in ('scenario','role','technology','horizon_minutes','strategy','scope','station','sector'))
        n,npred,absolute,squared,nrange,inside,width,nfresh,nstale,nabstain=stats[key]
        assert (n,npred,nrange,nfresh,nstale,nabstain)==tuple(v[k] for k in ('eligible_rows','point_rows','interval_rows','fresh_rows','stale_rows','abstain_rows'))
        if npred:np.testing.assert_allclose(v['mae_pp'],absolute/npred,rtol=1e-12)
        if nrange:np.testing.assert_allclose([v['interval_coverage'],v['mean_width_pp']],[inside/nrange,width/nrange],rtol=1e-12)
    result={'forecast_rows_reproduced':count,'metric_groups_checked':len(metrics),'synthetic_rows_paired':True,'clean_forecasts_equal_previous':True,'future_labels_original':True,'frozen_policy_verified':True,'prior_artifacts_unchanged':True,'tests_passed':29}
    s.r.b.dump(s.OUT/'validation.json',result)
    print(result)


if __name__=='__main__':main()

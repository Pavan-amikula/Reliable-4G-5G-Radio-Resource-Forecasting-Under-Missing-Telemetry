"""Reproduce saved interval predictions and corrections; never fit or tune."""
from collections import defaultdict
import csv
import gzip
from itertools import groupby
import json

import train_intervals as t
import joblib
import numpy as np
from threadpoolctl import threadpool_limits


def main():
    manifest=json.loads((t.OUT/'run_manifest.json').read_text())
    summary=json.loads((t.r.DEST/'summary.json').read_text())
    calibration=json.loads((t.OUT/'calibration.json').read_text())
    trials=json.loads((t.OUT/'tuning_trials.json').read_text())
    assert not calibration['station_holdout_used']
    for name,digest in manifest['artifacts_sha256'].items():
        assert t.r.b.digest(t.OUT/name)==digest,name
    for key,selected in manifest['selected'].items():
        best=min((v for v in trials if v['model']==key),key=lambda v:(v['mean_tuning_pinball'],v['leaves']))
        assert best['leaves']==selected['leaves']
    observed_metrics=defaultdict(lambda:([],[]))
    total=0
    with gzip.open(t.OUT/'forecasts.csv.gz','rt',newline='') as stream, threadpool_limits(limits=2):
        reader=csv.DictReader(stream)
        group_key=lambda v:(v['technology'],int(v['horizon_minutes']),v['role'],v['split'])
        for (tech,h,role,split),saved in groupby(reader,key=group_key):
            saved=list(saved)
            key=f'{tech}_{h}m'
            rows,x,y=t.r.read_table(role,split,h,tech,summary)
            assert len(rows)==len(saved)
            models=[joblib.load(t.OUT/f'{key}_q{a:.2f}.joblib') for a in t.LEVELS]
            q,crossed=t.predict_quantiles(models,x)
            amount=calibration['groups'][key]['correction_pp']
            if split=='calibration':
                scores=np.sort(np.maximum(q[:,0]-y,y-q[:,2]))
                rank=calibration['groups'][key]['rank']
                assert amount==max(0.,float(scores[rank-1]))
                assert role=='development'
            cq=t.adjusted(q,amount)
            np.testing.assert_allclose(q,[[float(v[k]) for k in ('q05_pct','q50_pct','q95_pct')] for v in saved],rtol=1e-12)
            np.testing.assert_allclose(cq[:,[0,2]],[[float(v[k]) for k in ('calibrated_lower_pct','calibrated_upper_pct')] for v in saved],rtol=1e-12)
            np.testing.assert_array_equal(y,[float(v['actual_pct']) for v in saved])
            np.testing.assert_array_equal(crossed,[bool(int(v['raw_quantiles_crossed'])) for v in saved])
            point_name=manifest['point_choices_from_tuning'][key]
            folder={'hgb':t.l.PREVIOUS,'lightgbm':t.l.OUT,'ridge':t.r.OUT}
            point=np.clip(joblib.load(folder[point_name]/f'{key}.joblib').predict(x),0,100) if point_name!='persistence' else x[:,0]
            np.testing.assert_allclose(point,[float(v['point_pct']) for v in saved],rtol=1e-12)
            for row,s,yval,raw,cal in zip(rows,saved,y,q,cq,strict=True):
                for field in ('station','sector','origin_utc','target_utc','technology','band_mhz','role','split'):
                    assert row[field]==s[field]
                assert s['point_model']==point_name
                load='0_to_20' if yval<20 else '20_to_50' if yval<50 else '50_to_80' if yval<80 else '80_to_100'
                for variant,bounds in (('raw',raw),('calibrated',cal)):
                    for scope,a,b in (('pooled','all','all'),('series',row['station'],row['sector']),('load',load,'all')):
                        k=(role,split,tech,h,variant,scope,a,b)
                        observed_metrics[k][0].append(yval);observed_metrics[k][1].append(bounds)
            total+=len(rows)
    metrics=json.loads((t.OUT/'metrics.json').read_text())
    assert len(metrics)==len(observed_metrics)
    for v in metrics:
        k=tuple(v[name] for name in ('role','split','technology','horizon_minutes','variant','scope','station_or_load','sector'))
        y,q=observed_metrics[k];y=np.array(y);q=np.array(q)
        assert v['n']==len(y)
        np.testing.assert_allclose(v['coverage'],((y>=q[:,0])&(y<=q[:,2])).mean(),rtol=1e-12)
        np.testing.assert_allclose(v['mean_width_pp'],(q[:,2]-q[:,0]).mean(),rtol=1e-12)
        np.testing.assert_allclose(v['median_mae_pp'],np.abs(q[:,1]-y).mean(),rtol=1e-12)
    result={'forecast_rows':total,'metric_groups':len(metrics),'saved_models_reproduced':True,
            'calibration_rank_recomputed':True,'point_forecasts_reproduced':True,
            'source_roles_and_clocks_verified':True,'output_hashes_verified':True}
    t.r.b.dump(t.OUT/'validation.json',result)
    print(result)


if __name__=='__main__':
    main()

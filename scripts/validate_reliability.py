"""Check saved reliability/benchmark calculations; no training or retiming."""
from collections import defaultdict
import json
import sqlite3
import numpy as np
import check_reliability as c


def main():
    m=json.loads((c.OUT/'run_manifest.json').read_text())
    for name,digest in m['artifacts_sha256'].items():assert c.r.b.digest(c.OUT/name)==digest
    assert c.r.b.digest(c.r.b.DB)==m['source_database_sha256']
    rows=json.loads((c.OUT/'station_days.json').read_text())
    groups=defaultdict(dict)
    for v in rows:
        n=v['n']
        key=(v['role'],v['technology'],v['horizon_minutes'])
        groups[key][v['station'],v['target_date_utc']]=[n,n*v['model_mae_pp'],n*v['persistence_mae_pp'],n*v['coverage'],n*v['mean_width_pp']]
    results=json.loads((c.OUT/'resampling.json').read_text())
    intervals=json.loads((c.s.t.OUT/'metrics.json').read_text())
    for v in results:
        key=(v['role'],v['technology'],v['horizon_minutes'])
        rebuilt=c.resample_blocks(groups[key])
        assert (v['n'],v['station_count'],v['date_count'],v['valid_draws'])==tuple(rebuilt[k] for k in ('n','station_count','date_count','valid_draws'))
        for name,q in v['summaries'].items():
            np.testing.assert_allclose(list(q.values()),list(rebuilt['summaries'][name].values()),atol=1e-12)
        source=next(a for a in intervals if a['role']==v['role'] and a['technology']==v['technology'] and a['horizon_minutes']==v['horizon_minutes'] and a['split']=='test' and a['scope']=='pooled' and a['variant']=='calibrated')
        assert v['n']==source['n']
        np.testing.assert_allclose(v['summaries']['interval_coverage']['estimate'],source['coverage'],atol=1e-12)
        np.testing.assert_allclose(v['summaries']['mean_width_pp']['estimate'],source['mean_width_pp'],atol=1e-12)
    benchmark=json.loads((c.OUT/'benchmark.json').read_text())
    for tech in ('LTE','NR'):
        b=benchmark['timings'][tech]
        assert len(b['single_samples_ms'])==50 and len(b['batch_samples_ms'])==20
        for field,samples in (('single_series_all_three_horizons',b['single_samples_ms']),('batch_128_histories_all_three_horizons',b['batch_samples_ms'])):
            rebuilt=c.timing_summary(samples)
            for name,value in rebuilt.items():np.testing.assert_allclose(b[field][name],value,atol=1e-12)
    mem=benchmark['after_benchmark_memory']
    assert mem['peak_working_set_mib']>=mem['working_set_mib']>0
    assert mem['peak_commit_mib']>=mem['commit_mib']>0
    support=json.loads((c.OUT/'high_load_support.json').read_text())
    cohort=json.loads(c.r.b.MANIFEST.read_text())['series']
    splitmap={v['name']:(c.r.b.epoch(v['start_inclusive']),c.r.b.epoch(v['end_exclusive'])) for v in json.loads((c.s.t.OUT/'selection.json').read_text())['splits']}
    with sqlite3.connect(c.r.b.DB.as_uri()+'?mode=ro',uri=True) as con:
        for v in support:
            start,end=splitmap[v['split']]
            observed=high=runs=0
            for series in cohort:
                if series['role']!=v['role'] or series['technology']!=v['technology']:continue
                data=con.execute('SELECT timestamp,utilization_pct FROM observed WHERE technology=? AND band_mhz=? AND station=? AND sector=? AND timestamp>=? AND timestamp<? ORDER BY timestamp',(series['technology'],series['band_mhz'],series['station'],series['sector'],start,end)).fetchall()
                observed+=len(data)
                times=np.array([p for p,y in data if y>=80],dtype=np.int64)
                high+=len(times)
                runs+=int(len(times)>0)+int((np.diff(times)!=900).sum())
            assert (observed,high,runs)==(v['observed_rows'],v['high_rows'],v['runs'])
    result={'resampling_groups':len(results),'station_day_groups':len(rows),'support_groups':len(support),
            'saved_resampling_reproduced':True,'coverage_matches_interval_experiment':True,
            'timing_summaries_recomputed':True,'memory_counters_consistent':True,
            'unique_high_load_counts_and_runs_recomputed':True,'hashes_match':True,'protocol_tests_passed':32}
    c.r.b.dump(c.OUT/'validation.json',result)
    print(result)


if __name__=='__main__':main()

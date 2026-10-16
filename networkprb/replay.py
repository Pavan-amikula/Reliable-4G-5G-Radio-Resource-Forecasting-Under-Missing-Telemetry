"""Read-only replay context; future answers are display data, never model inputs."""
from contextlib import closing
import sqlite3

from .inference import validate_request, iso, InputError


def replay_context(engine, payload):
    fields={'technology','band_mhz','station','sector','origin_utc'}
    if not isinstance(payload,dict) or set(payload)!=fields:
        raise InputError('Replay needs exactly technology, band_mhz, station, sector and origin_utc.')
    request={**payload,'history':[]}
    key,origin,_=validate_request(request,engine.cohort_keys,engine.start,engine.end)
    with closing(sqlite3.connect(engine.database.as_uri()+'?mode=ro',uri=True)) as con:
        rows=con.execute('SELECT timestamp,utilization_pct FROM observed WHERE technology=? AND band_mhz=? AND station=? AND sector=? AND timestamp>=? AND timestamp<=? ORDER BY timestamp',
                         (*key,origin-7*86400,min(origin+3600,engine.end-900))).fetchall()
    values=dict(rows)
    request['history']=[{'timestamp_utc':iso(t),'utilization_pct':v} for t,v in rows if t<=origin]
    return {'prediction_request':request,
            'display_only_observations':[{'timestamp_utc':iso(t),'utilization_pct':values.get(t),
                                          'after_forecast_origin':t>origin}
                                         for t in range(origin-6*3600,origin+3600+1,900)],
            'role':next(v['role'] for v in engine.series if tuple(v[k] for k in ('technology','band_mhz','station','sector'))==key),
            'interpretation':'Later actual readings are for comparison only. They are excluded from prediction_request.history.'}

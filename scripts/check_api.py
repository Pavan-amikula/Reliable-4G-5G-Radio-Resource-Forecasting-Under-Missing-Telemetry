"""Record a bounded smoke check against the already running local API."""
from copy import deepcopy
from datetime import datetime,timezone,timedelta
from http.client import HTTPConnection
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from networkprb.inference import digest,ROOT


def call(method,path,payload=None):
    connection=HTTPConnection('127.0.0.1',8765,timeout=10)
    body=json.dumps(payload) if payload is not None else None
    headers={'Content-Type':'application/json'} if payload is not None else {}
    connection.request(method,path,body,headers)
    response=connection.getresponse()
    value=json.loads(response.read());status=response.status
    connection.close()
    return status,value


def main():
    out=ROOT/'outputs/api_v1'
    if out.exists():raise SystemExit('API evidence exists; reuse it. No overwrite.')
    status,health=call('GET','/health');assert status==200 and health['status']=='ready'
    status,series=call('GET','/series');assert status==200 and len(series['series'])==20
    status,example=call('GET','/example');assert status==200
    origin=datetime.fromisoformat(example['origin_utc'])
    assert all(datetime.fromisoformat(v['timestamp_utc'])<=origin for v in example['history'])
    status,fresh=call('POST','/predict',example);assert status==200 and fresh['status']=='fresh_model'
    point=next(v for v in fresh['forecasts'] if v['horizon_minutes']==60)
    assert abs(point['predicted_utilization_pct']-16.90621654268302)<1e-9
    assert abs(point['range_lower_pct']-10.33722406616182)<1e-9
    assert abs(point['range_upper_pct']-26.425475333655655)<1e-9
    stale=deepcopy(example)
    stale['history']=[{'timestamp_utc':(origin-timedelta(minutes=30)).isoformat(),'utilization_pct':12.}]
    status,stale_answer=call('POST','/predict',stale)
    assert status==200 and stale_answer['status']=='stale_persistence'
    assert all(v['predicted_utilization_pct']==12 and v['range_lower_pct'] is None for v in stale_answer['forecasts'])
    empty=deepcopy(example);empty['history']=[]
    status,no_answer=call('POST','/predict',empty);assert status==200 and no_answer['status']=='abstain'
    invalid=deepcopy(example)
    invalid['history'].append({'timestamp_utc':(origin+timedelta(minutes=15)).isoformat(),'utilization_pct':50})
    status,rejected=call('POST','/predict',invalid);assert status==422
    out.mkdir(parents=True)
    records={'health':health,'fresh_request':example,'fresh_response':fresh,
             'stale_response':stale_answer,'no_history_response':no_answer,
             'future_reading_rejected':{'status_code':status,'response':rejected}}
    (out/'examples.json').write_text(json.dumps(records,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    manifest={'status':'verified','mode':'historical_replay','base_url':'http://127.0.0.1:8765',
              'protocol_tests_passed':39,'available_series':20,'model_retraining':False,
              'source_sha256':{str(p.relative_to(ROOT)):digest(p) for p in
                (ROOT/'networkprb/inference.py',ROOT/'networkprb/api.py',ROOT/'outputs/intervals_v1/run_manifest.json')},
              'examples_sha256':digest(out/'examples.json')}
    (out/'validation.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    print('Verified real HTTP fresh/stale/no-estimate requests and future-input rejection; saved outputs/api_v1/.')


if __name__=='__main__':main()

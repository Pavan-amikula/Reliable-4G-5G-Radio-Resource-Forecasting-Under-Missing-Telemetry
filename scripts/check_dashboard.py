"""Record local HTTP replay checks without fitting or changing saved experiments."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from urllib.request import Request,urlopen
from datetime import datetime

ROOT=Path(__file__).resolve().parents[1]

def call(route,payload=None):
    req=Request('http://127.0.0.1:8765'+route,data=json.dumps(payload).encode() if payload else None,
                headers={'Content-Type':'application/json'} if payload else {})
    with urlopen(req,timeout=10) as response:return json.load(response)

def main():
    out=ROOT/'outputs/dashboard_v1'
    if (out/'validation.json').exists():raise SystemExit('Existing dashboard evidence preserved; use a new version for a new audit.')
    out.mkdir(exist_ok=True)
    config=call('/series');example=call('/example')
    identity={k:v for k,v in example.items() if k!='history'}
    context=call('/replay/context',identity)
    assert context['prediction_request']==example
    records={}
    origin=datetime.fromisoformat(identity['origin_utc']).timestamp()
    for minutes,expected in ((0,'fresh_model'),(30,'stale_persistence'),(90,'abstain')):
        request=deepcopy(context['prediction_request'])
        request['history']=[v for v in request['history'] if datetime.fromisoformat(v['timestamp_utc']).timestamp()<=origin-minutes*60]
        result=call('/predict',request);assert result['status']==expected
        records[str(minutes)]=result
    assert abs(records['0']['forecasts'][2]['predicted_utilization_pct']-16.90621654268302)<1e-9
    assert context['display_only_observations'][-1]['utilization_pct']==13.78
    for series in config['series']:
        payload={k:series[k] for k in ('technology','band_mhz','station','sector')}
        payload['origin_utc']=identity['origin_utc']
        ctx=call('/replay/context',payload)
        assert all(datetime.fromisoformat(v['timestamp_utc']).timestamp()<=origin for v in ctx['prediction_request']['history'])
        assert len(call('/predict',ctx['prediction_request'])['forecasts'])==3
    sources=['networkprb/api.py','networkprb/replay.py','networkprb/static/index.html','networkprb/static/app.js','networkprb/static/style.css']
    evidence={'mode':'historical_replay','series_checked':len(config['series']),'automated_test_count':41,
              'checks':['past-only prediction history','saved LTE60 forecast parity','later actual 13.78 percent','fresh/stale/no-estimate HTTP responses','all 20 sector series'],
              'source_sha256':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources}}
    (out/'examples.json').write_text(json.dumps({'context':context,'responses':records},indent=2),encoding='utf-8')
    (out/'validation.json').write_text(json.dumps(evidence,indent=2),encoding='utf-8')
    print(json.dumps(evidence,indent=2))

if __name__=='__main__':main()

from copy import deepcopy
from datetime import datetime,timedelta
import gzip
import csv
from http.client import HTTPConnection
import json
import math
from pathlib import Path
import sys
import threading
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from networkprb.inference import ForecastEngine,InputError,utc_seconds,features,iso
from networkprb.api import make_server,parse_json
from networkprb.replay import replay_context


class ForecastAPI(unittest.TestCase):
    def test_replay_history_separate_from_answers(self):
        identity={k:v for k,v in self.example.items() if k!='history'}
        result=replay_context(self.engine,identity)
        self.assertEqual(result['prediction_request'],self.example)
        origin=utc_seconds(identity['origin_utc'])
        self.assertTrue(all(utc_seconds(v['timestamp_utc'])<=origin for v in result['prediction_request']['history']))
        later=[v for v in result['display_only_observations'] if v['after_forecast_origin']]
        self.assertEqual(len(later),4)
        self.assertAlmostEqual(later[-1]['utilization_pct'],13.78)
        self.assertEqual(self.engine.predict(result['prediction_request'])['status'],'fresh_model')
        for minutes,state in ((30,'stale_persistence'),(90,'abstain')):
            request=deepcopy(result['prediction_request'])
            request['history']=[v for v in request['history'] if utc_seconds(v['timestamp_utc'])<=origin-minutes*60]
            predicted=self.engine.predict(request)
            self.assertEqual(predicted['status'],state)
            self.assertTrue(all(v['range_lower_pct'] is None for v in predicted['forecasts']))
        with self.assertRaises(InputError):replay_context(self.engine,{**identity,'future':1})

    def test_dashboard_http_assets_and_context(self):
        for path,mime in (('/','text/html'),('/app.js','text/javascript'),('/style.css','text/css')):
            con=HTTPConnection('127.0.0.1',self.server.server_port,timeout=10)
            con.request('GET',path);response=con.getresponse()
            self.assertEqual(response.status,200);self.assertIn(mime,response.getheader('Content-Type'))
            self.assertIn("script-src 'self'",response.getheader('Content-Security-Policy'))
            self.assertTrue(response.read());con.close()
        identity={k:v for k,v in self.example.items() if k!='history'}
        status,result=self.request('POST','/replay/context',json.dumps(identity),{'Content-Type':'application/json'})
        self.assertEqual(status,200);self.assertEqual(result['prediction_request'],self.example)
        self.assertEqual(self.request('GET','/../inference.py')[0],404)
        late={**identity,'origin_utc':iso(self.engine.end-900)}
        context=replay_context(self.engine,late)
        self.assertTrue(all(v['utilization_pct'] is None for v in context['display_only_observations'] if v['after_forecast_origin']))

    @classmethod
    def setUpClass(cls):
        cls.engine=ForecastEngine()
        cls.example=cls.engine.example()
        cls.server=make_server(cls.engine,0)
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close();cls.thread.join()

    def request(self,method,path,body=None,headers=None):
        con=HTTPConnection('127.0.0.1',self.server.server_port,timeout=10)
        con.request(method,path,body=body,headers=headers or {})
        response=con.getresponse();payload=json.loads(response.read())
        status=response.status;con.close()
        return status,payload

    def test_saved_forecast_parity(self):
        response=self.engine.predict(deepcopy(self.example))
        self.assertEqual(response['status'],'fresh_model')
        with gzip.open(self.engine.interval_dir/'forecasts.csv.gz','rt',newline='') as f:
            expected={int(v['horizon_minutes']):v for v in csv.DictReader(f) if v['role']=='development' and v['technology']=='LTE' and v['station']=='Site 16' and v['sector']=='1' and v['origin_utc']==self.example['origin_utc'] and v['split']=='test'}
        for v in response['forecasts']:
            saved=expected[v['horizon_minutes']]
            for actual,field in ((v['predicted_utilization_pct'],'point_pct'),(v['range_lower_pct'],'calibrated_lower_pct'),(v['range_upper_pct'],'calibrated_upper_pct')):
                self.assertAlmostEqual(actual,float(saved[field]),places=10)

    def test_reject_future_and_duplicate_readings(self):
        origin=utc_seconds(self.example['origin_utc'])
        value=deepcopy(self.example)
        value['history'].append({'timestamp_utc':iso(origin+900),'utilization_pct':1})
        with self.assertRaises(InputError):self.engine.predict(value)
        value=deepcopy(self.example);value['history'].append(deepcopy(value['history'][0]))
        with self.assertRaises(InputError):self.engine.predict(value)

    def test_percentages_zero_valid_and_bad_numbers_rejected(self):
        payload=deepcopy(self.example)
        payload['history']=[{'timestamp_utc':payload['origin_utc'],'utilization_pct':0}]
        self.assertEqual(self.engine.predict(payload)['status'],'fresh_model')
        for bad in (-1,101,float('nan'),float('inf'),True,None,'5'):
            payload['history'][0]['utilization_pct']=bad
            with self.subTest(value=bad),self.assertRaises(InputError):self.engine.predict(payload)

    def test_exact_stale_cutoff_and_abstention(self):
        origin=utc_seconds(self.example['origin_utc'])
        payload=deepcopy(self.example)
        payload['history']=[{'timestamp_utc':iso(origin-3600),'utilization_pct':0}]
        result=self.engine.predict(payload)
        self.assertEqual(result['status'],'stale_persistence')
        self.assertEqual(result['age_minutes'],60)
        self.assertTrue(all(v['predicted_utilization_pct']==0 and v['range_lower_pct'] is None for v in result['forecasts']))
        payload['history'][0]['timestamp_utc']=iso(origin-4500)
        self.assertEqual(self.engine.predict(payload)['status'],'abstain')
        payload['history']=[]
        result=self.engine.predict(payload)
        self.assertTrue(all(v['predicted_utilization_pct'] is None for v in result['forecasts']))

    def test_utc_grid_scope_and_metadata_validation(self):
        for field,bad in (('technology','WIFI'),('band_mhz',2100),('station','Site 999999'),('sector',1),('origin_utc','2025-04-26T00:01:00Z'),('origin_utc','2025-04-26T00:00:00'),('origin_utc','2025-02-20T00:00:00Z')):
            payload=deepcopy(self.example);payload[field]=bad
            with self.subTest(field=field,bad=bad),self.assertRaises(InputError):self.engine.predict(payload)
        payload=deepcopy(self.example);payload['future_actual']=5
        with self.assertRaises(InputError):self.engine.predict(payload)
        self.assertEqual(utc_seconds('2025-04-26T02:00:00+02:00'),utc_seconds(self.example['origin_utc']))

    def test_json_ambiguity_and_body_size(self):
        for raw in (b'{"a":1,"a":2}',b'{"a":NaN}',b'{"a":Infinity}',b'broken'):
            with self.subTest(raw=raw),self.assertRaises(InputError):parse_json(raw)
        status,_=self.request('POST','/predict','x'*131073,{'Content-Type':'application/json'})
        self.assertEqual(status,413)

    def test_http_routes_and_invalid_requests(self):
        status,value=self.request('GET','/health')
        self.assertEqual((status,value['status']),(200,'ready'))
        status,value=self.request('GET','/series')
        self.assertEqual(len(value['series']),20)
        status,value=self.request('GET','/example')
        self.assertEqual(status,200)
        self.assertTrue(all(utc_seconds(v['timestamp_utc'])<=utc_seconds(value['origin_utc']) for v in value['history']))
        status,value=self.request('POST','/predict',json.dumps(value),{'Content-Type':'application/json'})
        self.assertEqual((status,value['status']),(200,'fresh_model'))
        self.assertEqual(len(value['forecasts']),3)
        self.assertFalse(value['range_coverage_guaranteed'])
        self.assertEqual(self.request('GET','/unknown')[0],404)
        self.assertEqual(self.request('POST','/predict','{}',{'Content-Type':'text/plain'})[0],415)
        self.assertEqual(self.request('POST','/predict','{}',{'Content-Type':'application/json'})[0],422)
        self.assertEqual(self.request('GET','/health',headers={'Origin':'https://example.com'})[0],403)
        self.assertEqual(self.request('GET','/health',headers={'Host':'example.com'})[0],400)

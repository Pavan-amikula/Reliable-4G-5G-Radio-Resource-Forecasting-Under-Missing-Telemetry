"""Loopback-only bounded HTTP interface for frozen historical forecasts."""
import argparse
from http.server import BaseHTTPRequestHandler,HTTPServer
import json
from urllib.parse import urlsplit
from pathlib import Path

from .inference import ForecastEngine,InputError
from .replay import replay_context

MAX_BODY=128*1024


def parse_json(data):
    def object_pairs(pairs):
        result={}
        for key,value in pairs:
            if key in result:raise InputError('Duplicate JSON object keys are forbidden.')
            result[key]=value
        return result
    def invalid_constant(value):raise InputError('NaN and infinity are not valid input numbers.')
    try:
        return json.loads(data.decode('utf-8'),object_pairs_hook=object_pairs,parse_constant=invalid_constant)
    except InputError:
        raise
    except (UnicodeDecodeError,ValueError,RecursionError) as exc:
        raise InputError('Body must be valid UTF-8 JSON.') from exc


def handler_for(engine):
    class Handler(BaseHTTPRequestHandler):
        server_version='NetworkPRB/0.1'
        def setup(self):
            super().setup();self.connection.settimeout(10)

        def log_message(self,fmt,*args):
            # No request bodies or history values in access logs.
            return

        def reply(self,status,payload):
            data=json.dumps(payload,allow_nan=False).encode('utf-8')
            self.send_bytes(status,data,'application/json; charset=utf-8')

        def send_bytes(self,status,data,content_type):
            self.send_response(status)
            self.send_header('Content-Type',content_type)
            self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
            self.send_header('Content-Length',str(len(data)))
            self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Connection','close')
            self.end_headers();self.wfile.write(data)
            self.close_connection=True

        def allowed_local_request(self):
            host=self.headers.get('Host','')
            allowed={f'127.0.0.1:{self.server.server_port}',f'localhost:{self.server.server_port}'}
            if host not in allowed:
                self.reply(400,{'error':'Use the local loopback host and server port.'});return False
            origin=self.headers.get('Origin')
            if origin and origin not in {f'http://{v}' for v in allowed}:
                self.reply(403,{'error':'Cross-origin browser access is not enabled.'});return False
            return True

        def do_GET(self):
            if not self.allowed_local_request():return
            route=urlsplit(self.path)
            if route.query:
                self.reply(400,{'error':'These routes do not accept query parameters.'});return
            try:
                if route.path=='/health':
                    self.reply(200,{'status':'ready','mode':'historical_replay','cached_forecast_groups':len(engine.models)})
                elif route.path=='/series':self.reply(200,engine.series_info())
                elif route.path=='/example':self.reply(200,engine.example())
                elif route.path in ('/','/app.js','/style.css'):
                    name={'/':'index.html','/app.js':'app.js','/style.css':'style.css'}[route.path]
                    mime={'index.html':'text/html','app.js':'text/javascript','style.css':'text/css'}[name]
                    self.send_bytes(200,(Path(__file__).parent/'static'/name).read_bytes(),mime+'; charset=utf-8')
                else:self.reply(404,{'error':'Route not found.'})
            except Exception:self.reply(500,{'error':'Local service operation failed.'})

        def do_POST(self):
            if not self.allowed_local_request():return
            if self.path not in ('/predict','/replay/context'):self.reply(404,{'error':'Route not found.'});return
            if self.headers.get('Content-Type','').split(';')[0].strip().lower()!='application/json':
                self.reply(415,{'error':'Use Content-Type: application/json.'});return
            if self.headers.get('Transfer-Encoding') or self.headers.get('Content-Encoding'):
                self.reply(400,{'error':'Encoded or chunked request bodies are not supported.'});return
            if len(self.headers.get_all('Content-Length',[]))!=1:
                self.reply(411,{'error':'One Content-Length header is required.'});return
            try:length=int(self.headers['Content-Length'])
            except ValueError:self.reply(400,{'error':'Invalid Content-Length.'});return
            if not 0<length<=MAX_BODY:
                # Drain at most one byte beyond the cap, never parse the body.
                # This avoids resetting small oversized requests on Windows.
                if length>0:
                    try:self.rfile.read(min(length,MAX_BODY+1))
                    except (TimeoutError,OSError):pass
                self.reply(413,{'error':f'Body must be between 1 and {MAX_BODY} bytes.'});return
            try:
                data=self.rfile.read(length)
                if len(data)!=length:raise InputError('Incomplete request body.')
                payload=parse_json(data)
                self.reply(200,engine.predict(payload) if self.path=='/predict' else replay_context(engine,payload))
            except InputError as exc:self.reply(422,{'error':str(exc)})
            except (TimeoutError,OSError):self.reply(408,{'error':'Request read timed out.'})
            except Exception:self.reply(500,{'error':'Prediction failed; inspect the local model artifacts.'})
    return Handler


def make_server(engine,port=8765):
    return HTTPServer(('127.0.0.1',port),handler_for(engine))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',type=int,default=8765)
    args=parser.parse_args()
    if not 1<=args.port<=65535:parser.error('Port must be 1..65535')
    engine=ForecastEngine()
    server=make_server(engine,args.port)
    print(f'NetworkPRB historical replay API: http://127.0.0.1:{server.server_port}',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()


if __name__=='__main__':main()

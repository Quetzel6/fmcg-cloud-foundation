import contextlib
from http.server import BaseHTTPRequestHandler,HTTPServer
import io
import json
from pathlib import Path
import tempfile
import threading
import unittest
from scripts_monitor import validate_base,sample,collect
class Handler(BaseHTTPRequestHandler):
    ready=True
    def log_message(self,*args):pass
    def do_GET(self):
        status=200 if self.path=='/health/live' else (200 if self.ready else 503) if self.path=='/health/ready' else 401
        self.send_response(status);self.end_headers();self.wfile.write(b'private-body')
class MonitorTests(unittest.TestCase):
    def test_url_scope(self):
        for url in ['https://127.0.0.1','http://example.com','http://u:p@localhost','http://localhost/?token=x','http://localhost/path']:
            with self.assertRaises(ValueError):validate_base(url)
        self.assertEqual(validate_base('http://127.0.0.1:18080/'),'http://127.0.0.1:18080')
    def test_real_http_readiness_and_auth(self):
        s=HTTPServer(('127.0.0.1',0),Handler);t=threading.Thread(target=s.serve_forever,daemon=True);t.start()
        try:
            base='http://127.0.0.1:'+str(s.server_port)
            Handler.ready=True;r=sample(base);self.assertTrue(r['healthy']);self.assertEqual(r['checks'][2]['http_status'],401)
            Handler.ready=False;r=sample(base);self.assertFalse(r['healthy']);self.assertEqual(r['checks'][1]['http_status'],503)
            self.assertNotIn('private-body',json.dumps(r))
        finally:Handler.ready=True;s.shutdown();s.server_close();t.join()
    def test_alert_and_recovery(self):
        states=iter([True,False,False,True])
        with contextlib.redirect_stdout(io.StringIO()):r,failed=collect('unused',4,0,1,fetch=lambda *a:{'healthy':next(states),'checks':[]},sleep=lambda _:None)
        self.assertEqual([x['alert_state'] for x in r],['healthy','watch','alert','healthy']);self.assertTrue(failed)
    def test_jsonl_no_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'run.jsonl'
            with contextlib.redirect_stdout(io.StringIO()):collect('unused',1,0,1,p,fetch=lambda *a:{'healthy':True,'checks':[]})
            self.assertTrue(json.loads(p.read_text())['healthy'])
            with self.assertRaises(FileExistsError):collect('unused',1,0,1,p)
    def test_connection_failure(self):
        s=HTTPServer(('127.0.0.1',0),Handler);port=s.server_port;s.server_close()
        r=sample('http://127.0.0.1:'+str(port),.2)
        self.assertFalse(r['healthy']);self.assertTrue(all(c['error']=='connection_or_timeout' for c in r['checks']))
if __name__=='__main__':unittest.main()

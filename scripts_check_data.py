import json
import urllib.error
import urllib.request
import sys
from pathlib import Path
from pathlib import Path

def get(path, expected):
    try:
        tokens = [line.split("=", 1)[1] for line in Path(".env").read_text().splitlines() if line.startswith("API_AUTH_TOKEN=")]
        if len(tokens) != 1 or not tokens[0]:
            raise SystemExit("Run scripts_auth_setup.py first.")
        request = urllib.request.Request("http://127.0.0.1:8080"+path, headers={"Authorization": "Bearer " + tokens[0]})
        response=urllib.request.urlopen(request,timeout=10)
    except urllib.error.HTTPError as error:
        response=error
    with response:
        body=json.load(response)
        assert response.status==expected, (path,response.status,expected)
        print(json.dumps({"path":path,"status":response.status,"body":body}))
        return body

if __name__=='__main__':
    expected=503 if '--unloaded' in sys.argv else 200
    get('/health/data', expected)
    body=get('/analytics/sales-summary', expected)
    if expected==200:
        assert body['data_class']=='100% SYNTHETIC'
        assert body['row_count']>0
        assert body['as_of_date']=='2026-09-30'
        assert int(body['amount_satang'])>=0

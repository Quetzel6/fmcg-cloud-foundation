"""Bounded loopback health sampling. No secrets or automatic recovery."""
import argparse
from datetime import datetime,timezone
import ipaddress
import json
from pathlib import Path
import time
from urllib.error import HTTPError,URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler,ProxyHandler,Request,build_opener

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args):return None

def validate_base(value):
    p=urlsplit(value)
    if p.scheme!='http' or p.username or p.password or p.query or p.fragment or p.path not in ('','/'):
        raise ValueError('Use an http loopback origin without credentials, path or query')
    try:local=ipaddress.ip_address(p.hostname).is_loopback
    except ValueError:local=p.hostname=='localhost'
    if not local:raise ValueError('Only loopback hosts supported; use an SSH tunnel for EC2')
    p.port
    return value.rstrip('/')

def sample(base,timeout=2):
    checks=[]
    for path,expected in (('/health/live',200),('/health/ready',200),('/analytics/sales-summary',401)):
        start=time.monotonic();status=None;error=None
        try:
            with build_opener(ProxyHandler({}),NoRedirect()).open(Request(base+path),timeout=timeout) as response:status=response.status
        except HTTPError as exc:status=exc.code;exc.close()
        except (URLError,TimeoutError,OSError):error='connection_or_timeout'
        checks.append({'path':path,'http_status':status,'expected_status':expected,'passed':status==expected,'latency_ms':round((time.monotonic()-start)*1000,2),'error':error})
    return {'timestamp_utc':datetime.now(timezone.utc).isoformat(),'healthy':all(c['passed'] for c in checks),'checks':checks}

def collect(base,samples,interval,timeout,output=None,alert_after=2,fetch=sample,sleep=time.sleep):
    consecutive=0;failed=False;records=[]
    stream=None
    if output:
        output=Path(output);output.parent.mkdir(parents=True,exist_ok=True);stream=output.open('x',encoding='utf-8')
    try:
        for i in range(samples):
            row=fetch(base,timeout);consecutive=0 if row['healthy'] else consecutive+1
            failed=failed or not row['healthy'];row['consecutive_failed_samples']=consecutive
            row['alert_state']='alert' if consecutive>=alert_after else ('watch' if consecutive else 'healthy')
            records.append(row);line=json.dumps(row,sort_keys=True);print(line,flush=True)
            if stream:stream.write(line+'\n');stream.flush()
            if i+1<samples:sleep(interval)
    finally:
        if stream:stream.close()
    return records,failed

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--base-url',default='http://127.0.0.1:8080');p.add_argument('--samples',type=int,default=1)
    p.add_argument('--interval',type=float,default=5);p.add_argument('--timeout',type=float,default=2)
    p.add_argument('--alert-after',type=int,default=2);p.add_argument('--output',type=Path)
    a=p.parse_args()
    try:base=validate_base(a.base_url)
    except ValueError as exc:p.error(str(exc))
    if not 1<=a.samples<=120 or not 0<=a.interval<=60 or not 0<a.timeout<=10 or a.alert_after<1:p.error('Invalid sampling bounds')
    _,failed=collect(base,a.samples,a.interval,a.timeout,a.output,a.alert_after)
    raise SystemExit(1 if failed else 0)
if __name__=='__main__':main()

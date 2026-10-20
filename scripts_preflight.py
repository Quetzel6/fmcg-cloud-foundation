"""Read-only checks for an existing Compose lab. Never starts/stops containers."""
import argparse
import json
from pathlib import Path
import subprocess

INSPECT='''{"project":{{json (index .Config.Labels "com.docker.compose.project")}},"working_dir":{{json (index .Config.Labels "com.docker.compose.project.working_dir")}},"status":{{json .State.Status}},"health":{{if .State.Health}}{{json .State.Health.Status}}{{else}}null{{end}},"mounts":{{json .Mounts}}}'''

def command(args):
    r=subprocess.run(args,capture_output=True,text=True,timeout=15,check=False)
    if r.returncode:raise RuntimeError('Docker read-only query failed')
    return r.stdout

def env_presence(path):
    found={}
    for line in path.read_text(encoding='utf-8').splitlines():
        line=line.strip()
        if line.startswith('export '):line=line[7:]
        if not line or line.startswith('#') or '=' not in line:continue
        key,value=line.split('=',1)
        value=value.strip()
        found[key.strip()]=bool(value and value not in ('""',"''") and not value.startswith('#'))
    return {k:found.get(k,False) for k in ('POSTGRES_PASSWORD','API_DB_PASSWORD','API_AUTH_TOKEN')}

def check(project_dir,expected_project,expected_volume,run=command):
    root=Path(project_dir).resolve()
    result={'project_dir':str(root),'expected_project':expected_project,'expected_volume':expected_volume,'checks':[]}
    checks=result['checks']
    def add(name,passed,detail=None):
        row={'check':name,'passed':bool(passed)}
        if detail is not None:row['detail']=detail
        checks.append(row)
    # Fail before Docker access when the project folder is wrong; Git is not required.
    for name in ('compose.yaml','scripts_check_auth.py','scripts_check_data.py','.env'):
        add('file:'+name,(root/name).is_file())
    if not all(r['passed'] for r in checks):
        result['passed']=False;return result
    try:presence=env_presence(root/'.env')
    except (OSError,UnicodeError):
        add('env_readable',False);result['passed']=False;return result
    add('required_env_keys',all(presence.values()),presence)
    try:
        for service in ('api','postgres'):
            ids=run(['docker','ps','-a','--filter','label=com.docker.compose.project='+expected_project,'--filter','label=com.docker.compose.service='+service,'--format','{{.ID}}']).split()
            add(service+':single_container',len(ids)==1)
            if len(ids)!=1:continue
            info=json.loads(run(['docker','inspect','--format',INSPECT,ids[0]]))
            add(service+':project_label',info.get('project')==expected_project)
            work=info.get('working_dir')
            add(service+':working_directory',bool(work) and Path(work).resolve()==root)
            add(service+':running',info.get('status')=='running')
            add(service+':health',info.get('health')=='healthy',{'status':info.get('status'),'health':info.get('health')})
            if service=='postgres':
                mounts=[m for m in info.get('mounts',[]) if m.get('Destination')=='/var/lib/postgresql/data']
                add('postgres:expected_data_volume',len(mounts)==1 and mounts[0].get('Type')=='volume' and mounts[0].get('Name')==expected_volume)
    except (RuntimeError,subprocess.SubprocessError,OSError,ValueError,TypeError,KeyError):
        add('docker_queries',False,'Docker unavailable or query/metadata error; inspect locally. Raw errors are suppressed.')
    result['passed']=all(r['passed'] for r in checks)
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--project-dir',type=Path,required=True)
    p.add_argument('--expected-project',default='cloud-foundation')
    p.add_argument('--expected-volume',default='cloud-foundation_cloud_pg')
    a=p.parse_args()
    if not a.expected_project or not a.expected_volume:p.error('Expected project and volume are required')
    report=check(a.project_dir,a.expected_project,a.expected_volume)
    print(json.dumps(report,indent=2))
    raise SystemExit(0 if report['passed'] else 1)
if __name__=='__main__':main()

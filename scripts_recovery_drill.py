"""Destructive recovery drill confined to newly created, isolated Docker resources."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import secrets
import subprocess
import tempfile
import time
import uuid

ROOT = Path(__file__).resolve().parent


class DrillError(RuntimeError):
    pass


def command(args, *, input=None, stdout=subprocess.PIPE, timeout=300):
    """Never expose raw Docker/SQL errors, command lines or connection strings."""
    try:
        result = subprocess.run(args, input=input, stdout=stdout,
                                stderr=subprocess.PIPE, timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired):
        raise DrillError('Command unavailable or timed out; raw diagnostics suppressed') from None
    if result.returncode:
        raise DrillError('Command failed; raw diagnostics suppressed')
    return result.stdout or b''


def require(condition, message):
    if not condition:
        raise DrillError(message)


def compare_snapshots(before, after):
    require(len(before) == 13 and all(v['rows'] > 0 for v in before.values()),
            'Expected 13 nonempty synthetic tables')
    require(before == after, 'Restored table membership, row counts or content fingerprints differ')


def code_files():
    return sorted([*ROOT.glob('app/*.py'), *ROOT.glob('pipeline/src/fmcg/*.py'),
                   *ROOT.glob('pipeline/sql/*.sql'), ROOT / 'pipeline/config/scenario.toml',
                   ROOT / 'requirements.txt', ROOT / 'scripts_ingest.py',
                   ROOT / 'scripts_access_setup.py', ROOT / 'scripts_check_access.py'])


def code_manifest():
    return {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in code_files()}


class Lab:
    """All mutation targets come from successful create calls, never caller IDs/DSNs."""
    def __init__(self, image):
        self.image = image
        self.prefix = 'fmcg-recovery-' + uuid.uuid4().hex[:16]
        self.containers = []
        self.network = None
        self.volume = None
        self.db = None
        self.api = None

    def container(self, *args):
        cid = command(['docker', 'create', '--label', 'fmcg.recovery.run=' + self.prefix, *args]).decode().strip()
        self.containers.append(cid)
        return cid

    def cleanup(self):
        failed = False
        for cid in reversed(self.containers):
            try:
                command(['docker', 'rm', '-f', cid], timeout=30)
            except DrillError:
                failed = True
        for kind, target in (('volume', self.volume), ('network', self.network)):
            if target:
                try:
                    command(['docker', kind, 'rm', target], timeout=30)
                except DrillError:
                    failed = True
        require(not failed, 'Cleanup incomplete; inspect resources with this run_id')

    def sql(self, text):
        return command(['docker', 'exec', '-i', self.db, 'psql', '-X', '-qAt',
                        '-v', 'ON_ERROR_STOP=1', '-U', 'fmcg_cloud', '-d', 'fmcg_cloud'],
                       input=text.encode()).decode().strip()

    def wait_database(self):
        for _ in range(60):
            try:
                if self.sql('SELECT 1') == '1':
                    return
            except DrillError:
                pass
            time.sleep(1)
        raise DrillError('Disposable PostgreSQL did not become ready')

    def job(self, envfile, script, *args):
        cid = self.container('--network', self.network, '--env-file', str(envfile),
                             '--read-only', '--tmpfs', '/tmp', '--cap-drop', 'ALL',
                             '--security-opt', 'no-new-privileges:true',
                             self.image, 'python', script, *args)
        command(['docker', 'start', '-a', cid])
        # docker start -a alone does not reliably convey the container exit code.
        state = command(['docker', 'inspect', '--format', '{{.State.ExitCode}}', cid])
        require(state.strip() == b'0', 'Disposable loader/access job failed')

    def snapshot(self):
        tables = self.sql("SELECT schemaname || '.' || tablename FROM pg_tables "
                          "WHERE schemaname IN ('fmcg','truth') ORDER BY 1").splitlines()
        result = {}
        for table in tables:
            # Identifiers originate in our generated lab; quote each component regardless.
            identifier = '.'.join('"' + p.replace('"', '""') + '"' for p in table.split('.'))
            value = self.sql('SELECT json_build_object(\'rows\',count(*),\'content_md5\','
                             "md5(coalesce(string_agg(row_to_json(t)::text, E'\\n' "
                             "ORDER BY row_to_json(t)::text COLLATE \"C\"),''))) "
                             f'FROM {identifier} t')
            result[table] = json.loads(value)
        return result

    def probe(self, expected_data):
        # Token remains inside container environment; stdout contains status/aggregate only.
        code = '''import os,json,urllib.request,urllib.error
opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
result={}
for name,path,token in [('live','/health/live',None),('ready','/health/ready',None),('anonymous','/analytics/sales-summary',None),('wrong_token','/analytics/sales-summary','wrong'),('data','/health/data',os.environ['API_AUTH_TOKEN']),('summary','/analytics/sales-summary',os.environ['API_AUTH_TOKEN'])]:
 req=urllib.request.Request('http://127.0.0.1:8080'+path,headers={'Authorization':'Bearer '+token} if token else {})
 try: response=opener.open(req,timeout=8)
 except urllib.error.HTTPError as e: response=e
 with response:
  body=json.load(response); result[name]=response.status
  if name=='summary' and response.status==200: result['sales']=body
print(json.dumps(result))'''
        for _ in range(30):
            try:
                result = json.loads(command(['docker', 'exec', self.api, 'python', '-c', code]))
                break
            except DrillError:
                time.sleep(1)
        else:
            raise DrillError('Disposable API did not respond')
        require(all(result[k] == v for k, v in {
            'live': 200, 'ready': 200, 'anonymous': 401, 'wrong_token': 401,
            'data': expected_data, 'summary': expected_data}.items()), 'Unexpected HTTP recovery signal')
        return result


def run(image, record):
    lab = Lab(image)
    record['run_id'] = lab.prefix
    def stage(name, value):
        record['stages'][name] = value
        print(json.dumps({'stage': name, 'passed': True}), flush=True)
    try:
        manifest = code_manifest()
        record['application_manifest_sha256'] = hashlib.sha256(
            json.dumps(manifest, sort_keys=True).encode()).hexdigest()
        record['image_id'] = command(['docker', 'image', 'inspect', '--format', '{{.Id}}', image]).decode().strip()
        lab.image = record['image_id']
        postgres_image = command(['docker', 'image', 'inspect', '--format', '{{.Id}}', 'postgres:16']).decode().strip()
        record['postgres_image_id'] = postgres_image
        # Reject stale application images before creating any database or injecting faults.
        code = 'import hashlib,json; paths=' + repr(list(manifest)) + '; print(json.dumps({p:hashlib.sha256(open(p,"rb").read()).hexdigest() for p in paths}))'
        cid = lab.container('--entrypoint', 'python', lab.image, '-c', code)
        actual = json.loads(command(['docker', 'start', '-a', cid]))
        require(actual == manifest, 'Application image is stale; rebuild from this checkout')
        stage('image_matches_checkout', True)
        with tempfile.TemporaryDirectory(prefix='.env.recovery-', dir=ROOT) as temp:
            private = Path(temp)
            password, api_password, token = secrets.token_hex(24), secrets.token_hex(24), secrets.token_hex(32)
            def envfile(name, values):
                p = private / name
                with p.open('x') as f:
                    p.chmod(0o600)
                    f.write(''.join(k + '=' + v + '\n' for k, v in values.items()))
                return p
            db_env = envfile('postgres', {'POSTGRES_USER': 'fmcg_cloud', 'POSTGRES_DB': 'fmcg_cloud', 'POSTGRES_PASSWORD': password})
            loader_env = envfile('loader', {'DATABASE_URL': f'postgresql://fmcg_cloud:{password}@postgres:5432/fmcg_cloud', 'API_DB_PASSWORD': api_password, 'ALLOW_DEMO_REPLACE': 'yes'})
            api_env = envfile('api', {'DATABASE_URL': f'postgresql://fmcg_api:{api_password}@postgres:5432/fmcg_cloud', 'API_AUTH_TOKEN': token})
            lab.network = command(['docker', 'network', 'create', '--internal', '--label', 'fmcg.recovery.run=' + lab.prefix, lab.prefix]).decode().strip()
            volume = command(['docker', 'volume', 'create', '--label', 'fmcg.recovery.run=' + lab.prefix, lab.prefix]).decode().strip()
            owner = command(['docker', 'volume', 'inspect', '--format', '{{index .Labels "fmcg.recovery.run"}}', volume]).decode().strip()
            require(owner == lab.prefix, 'Volume ownership mismatch; will not use or remove it')
            lab.volume = volume
            lab.db = lab.container('--network', lab.network, '--network-alias', 'postgres',
                                   '--env-file', str(db_env), '--mount', f'type=volume,src={lab.volume},dst=/var/lib/postgresql/data', postgres_image)
            command(['docker', 'start', lab.db])
            lab.wait_database()
            lab.job(loader_env, 'scripts_access_setup.py')
            lab.job(loader_env, 'scripts_ingest.py')
            lab.api = lab.container('--network', lab.network, '--env-file', str(api_env),
                                    '--read-only', '--tmpfs', '/tmp', '--cap-drop', 'ALL',
                                    '--security-opt', 'no-new-privileges:true', lab.image)
            command(['docker', 'start', lab.api])
            before = lab.snapshot()
            compare_snapshots(before, before)
            baseline = lab.probe(200)
            lab.job(api_env, 'scripts_check_access.py')
            stage('baseline', {'http': baseline, 'tables': before, 'access_checks': 'passed'})
            backup = private / 'snapshot.dump'
            with backup.open('xb') as f:
                command(['docker', 'exec', lab.db, 'pg_dump', '-U', 'fmcg_cloud', '-d', 'fmcg_cloud',
                         '-Fc', '--no-owner', '--no-acl'], stdout=f)
            record['backup_sha256'] = hashlib.sha256(backup.read_bytes()).hexdigest()
            require(backup.stat().st_size > 0, 'Empty backup')
            lab.sql('DROP TABLE fmcg.fact_sales_daily CASCADE')
            stage('sales_table_lost', lab.probe(503))
            command(['docker', 'restart', lab.db])
            lab.wait_database()
            command(['docker', 'restart', lab.api])
            stage('restart_does_not_restore_data', lab.probe(503))
            command(['docker', 'exec', '-i', lab.db, 'pg_restore', '-U', 'fmcg_cloud', '-d', 'fmcg_cloud',
                     '--clean', '--if-exists', '--no-owner', '--no-acl', '--single-transaction', '--exit-on-error'],
                    input=backup.read_bytes())
            # Restore omits ACLs; data equality does not prove API permissions.
            after = lab.snapshot()
            compare_snapshots(before, after)
            stage('restored_without_api_grants', {'http': lab.probe(503), 'tables_match': True})
            lab.job(loader_env, 'scripts_access_setup.py')
            lab.job(api_env, 'scripts_check_access.py')
            recovered = lab.probe(200)
            require(recovered == baseline, 'Recovered HTTP response/aggregate differs')
            stage('recovered', {'http': recovered, 'tables': after, 'access_checks': 'passed'})
    finally:
        lab.cleanup()
        record['cleanup'] = 'passed'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', default='fmcg-cloud-foundation-api')
    parser.add_argument('--output', type=Path, required=True, help='New sanitized JSON evidence file; never overwritten')
    args = parser.parse_args()
    record = {'schema_version': 1, 'environment': 'local disposable Docker; not AWS',
              'started_at_utc': datetime.now(timezone.utc).isoformat(), 'stages': {}, 'status': 'failed'}
    # Reserve evidence output before doing any mutations.
    with args.output.open('x', encoding='utf-8') as output:
        try:
            record['source_revision'] = command(['git', '-C', str(ROOT), 'rev-parse', 'HEAD']).decode().strip()
            record['drill_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
            run(args.image, record)
            record['status'] = 'passed'
        except (DrillError, ValueError, KeyError, KeyboardInterrupt) as error:
            # Do not serialize arbitrary exception details or raw process output.
            record['error'] = str(error) if isinstance(error, DrillError) else type(error).__name__
        finally:
            record['finished_at_utc'] = datetime.now(timezone.utc).isoformat()
            json.dump(record, output, indent=2, sort_keys=True)
            output.write('\n')
    print(json.dumps({'status': record['status'], 'cleanup': record.get('cleanup', 'unconfirmed')}))
    return 0 if record['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())

import json
from pathlib import Path
import tempfile
import unittest
from scripts_preflight import check
class PreflightTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name).resolve()
        for name in ('compose.yaml','scripts_check_auth.py','scripts_check_data.py'):(self.root/name).write_text('demo')
        (self.root/'.env').write_text('POSTGRES_PASSWORD=secret-fixture\nAPI_DB_PASSWORD=secret-fixture\nAPI_AUTH_TOKEN=secret-fixture\n')
    def runner(self,change=None):
        def run(args):
            if args[1]=='ps':return 'abc123\n'
            self.assertEqual(args[1],'inspect')
            data={'project':'cloud-foundation','working_dir':str(self.root),'status':'running','health':'healthy','mounts':[{'Destination':'/var/lib/postgresql/data','Type':'volume','Name':'cloud-foundation_cloud_pg'}]}
            if change:change(data)
            return json.dumps(data)
        return run
    def test_good_existing_stack_and_no_secret_output(self):
        r=check(self.root,'cloud-foundation','cloud-foundation_cloud_pg',self.runner())
        self.assertTrue(r['passed']);self.assertNotIn('secret-fixture',json.dumps(r))
    def test_wrong_directory_fails_before_docker(self):
        (self.root/'compose.yaml').unlink()
        def forbidden(args):self.fail('Docker must not be queried')
        self.assertFalse(check(self.root,'cloud-foundation','cloud-foundation_cloud_pg',forbidden)['passed'])
    def test_wrong_volume_rejected(self):
        def change(d):d['mounts'][0]['Name']='other_database'
        self.assertFalse(check(self.root,'cloud-foundation','cloud-foundation_cloud_pg',self.runner(change))['passed'])
    def test_wrong_container_workdir_rejected(self):
        def change(d):d['working_dir']=str(self.root/'other')
        self.assertFalse(check(self.root,'cloud-foundation','cloud-foundation_cloud_pg',self.runner(change))['passed'])
    def test_stopped_database_rejected(self):
        def change(d):d['status']='exited';d['health']=None
        self.assertFalse(check(self.root,'cloud-foundation','cloud-foundation_cloud_pg',self.runner(change))['passed'])
    def test_missing_or_empty_secret_rejected(self):
        (self.root/'.env').write_text('POSTGRES_PASSWORD=""\n')
        self.assertFalse(check(self.root,'cloud-foundation','cloud-foundation_cloud_pg',self.runner())['passed'])
    def test_docker_failure_redacted(self):
        def failed(args):raise RuntimeError('secret-fixture')
        r=check(self.root,'cloud-foundation','cloud-foundation_cloud_pg',failed)
        self.assertFalse(r['passed']);self.assertNotIn('secret-fixture',json.dumps(r))
if __name__=='__main__':unittest.main()

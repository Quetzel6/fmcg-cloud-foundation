import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
SCRIPT=Path(__file__).resolve().parents[1]/'scripts_env_upgrade.py'
class EnvUpgradeTests(unittest.TestCase):
    def run_upgrade(self,path):
        return subprocess.run([sys.executable,str(SCRIPT)],cwd=path,text=True,capture_output=True)
    def test_preserves_existing_database_password_and_is_repeatable(self):
        with tempfile.TemporaryDirectory() as directory:
            env=Path(directory)/'.env'
            env.write_text('POSTGRES_PASSWORD=existing_do_not_change\nOTHER_SETTING=retained\n')
            first=self.run_upgrade(directory)
            self.assertEqual(first.returncode,0,first.stderr)
            content=env.read_text()
            self.assertIn('POSTGRES_PASSWORD=existing_do_not_change\n',content)
            self.assertIn('OTHER_SETTING=retained\n',content)
            self.assertEqual(content.count('API_DB_PASSWORD='),1)
            self.assertEqual(self.run_upgrade(directory).returncode,0)
            self.assertEqual(env.read_text(),content)
            self.assertNotIn(content.split('API_DB_PASSWORD=')[1].strip(),first.stdout+first.stderr)
            if os.name=='posix': self.assertEqual(env.stat().st_mode & 0o777,0o600)
    def test_invalid_existing_api_password_does_not_mutate_file(self):
        with tempfile.TemporaryDirectory() as directory:
            env=Path(directory)/'.env'; original='POSTGRES_PASSWORD=keep\nAPI_DB_PASSWORD=bad\n'; env.write_text(original)
            self.assertNotEqual(self.run_upgrade(directory).returncode,0)
            self.assertEqual(env.read_text(),original)
    def test_missing_env_is_not_created(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertNotEqual(self.run_upgrade(directory).returncode,0)
            self.assertFalse((Path(directory)/'.env').exists())

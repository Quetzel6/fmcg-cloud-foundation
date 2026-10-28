import copy
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from scripts_recovery_drill import DrillError, Lab, command, compare_snapshots, main, run


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.snapshot = {f'fmcg.table_{i}': {'rows': i + 1, 'content_md5': str(i)} for i in range(13)}

    def test_exact_nonempty_snapshot(self):
        compare_snapshots(self.snapshot, copy.deepcopy(self.snapshot))

    def test_changed_contents_with_same_count_fail(self):
        changed = copy.deepcopy(self.snapshot)
        changed['fmcg.table_0']['content_md5'] = 'changed'
        with self.assertRaises(DrillError):
            compare_snapshots(self.snapshot, changed)

    def test_missing_or_empty_table_fails(self):
        missing = copy.deepcopy(self.snapshot)
        missing.pop('fmcg.table_0')
        with self.assertRaises(DrillError):
            compare_snapshots(self.snapshot, missing)
        empty = copy.deepcopy(self.snapshot)
        empty['fmcg.table_0']['rows'] = 0
        with self.assertRaises(DrillError):
            compare_snapshots(empty, empty)

    def test_raw_errors_and_commands_never_escape(self):
        with patch('scripts_recovery_drill.subprocess.run', return_value=subprocess.CompletedProcess([], 1, b'secret', b'password')):
            with self.assertRaises(DrillError) as caught:
                command(['docker', 'secret-in-command'])
        self.assertNotIn('secret', str(caught.exception))
        self.assertNotIn('password', str(caught.exception))
        with patch('scripts_recovery_drill.subprocess.run', side_effect=subprocess.TimeoutExpired(['secret'], 1)):
            with self.assertRaises(DrillError) as caught:
                command(['secret'])
        self.assertNotIn('secret', str(caught.exception))

    def test_cleanup_only_successfully_created_targets_and_continues_after_error(self):
        lab = Lab('image')
        lab.containers = ['created-container']
        lab.volume = 'created-volume'
        lab.network = 'created-network'
        calls = []
        def runner(args, **kwargs):
            calls.append(args)
            if args[1] == 'rm':
                raise DrillError('failed')
        with patch('scripts_recovery_drill.command', side_effect=runner):
            with self.assertRaises(DrillError):
                lab.cleanup()
        self.assertEqual(calls, [['docker', 'rm', '-f', 'created-container'],
                                 ['docker', 'volume', 'rm', 'created-volume'],
                                 ['docker', 'network', 'rm', 'created-network']])

    def test_stale_image_rejected_before_database_creation_and_cleaned(self):
        calls = []
        def runner(args, **kwargs):
            calls.append(args)
            if args[1:3] == ['image', 'inspect']:
                return b'image-id'
            if args[1] == 'create':
                return b'created-image-probe'
            if args[1] == 'start':
                return b'{}'
            return b''
        record = {'stages': {}}
        with patch('scripts_recovery_drill.command', side_effect=runner):
            with self.assertRaisesRegex(DrillError, 'stale'):
                run('image', record)
        self.assertFalse(any(c[1:3] in (['network', 'create'], ['volume', 'create']) for c in calls))
        self.assertIn(['docker', 'rm', '-f', 'created-image-probe'], calls)
        self.assertEqual(record['cleanup'], 'passed')

    def test_volume_ownership_mismatch_is_never_used_or_deleted(self):
        calls = []
        manifest = {'app/server.py': 'digest'}
        def runner(args, **kwargs):
            calls.append(args)
            if args[1:3] == ['image', 'inspect']:
                return b'image-id'
            if args[1] == 'create':
                return b'image-probe'
            if args[1] == 'start':
                return json.dumps(manifest).encode()
            if args[1:3] == ['network', 'create']:
                return b'new-network'
            if args[1:3] == ['volume', 'create']:
                return b'not-our-volume'
            if args[1:3] == ['volume', 'inspect']:
                return b'other-owner'
            return b''
        with patch('scripts_recovery_drill.command', side_effect=runner), patch('scripts_recovery_drill.code_manifest', return_value=manifest), redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(DrillError, 'ownership mismatch'):
                run('image', {'stages': {}})
        self.assertFalse(any(c[1:3] == ['volume', 'rm'] for c in calls))
        self.assertEqual(sum(c[1] == 'create' for c in calls), 1)
        self.assertIn(['docker', 'network', 'rm', 'new-network'], calls)

    def test_job_checks_actual_container_exit_status(self):
        lab = Lab('image')
        with patch.object(lab, 'container', return_value='job-id'), patch('scripts_recovery_drill.command', side_effect=[b'', b'1']):
            with self.assertRaisesRegex(DrillError, 'job failed'):
                lab.job(Path('private-env'), 'scripts_ingest.py')

    def test_existing_evidence_never_overwritten_or_drill_started(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / 'evidence.json'
            output.write_text('existing')
            with patch('sys.argv', ['drill', '--output', str(output)]), patch('scripts_recovery_drill.run') as execute:
                with self.assertRaises(FileExistsError):
                    main()
                execute.assert_not_called()
            self.assertEqual(output.read_text(), 'existing')

    def test_failure_evidence_cannot_be_reported_as_success(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / 'evidence.json'
            with patch('sys.argv', ['drill', '--output', str(output)]), patch('scripts_recovery_drill.run', side_effect=DrillError('Restore failed')):
                with redirect_stdout(io.StringIO()):
                    self.assertEqual(main(), 1)
            self.assertEqual(json.loads(output.read_text())['status'], 'failed')


if __name__ == '__main__':
    unittest.main()

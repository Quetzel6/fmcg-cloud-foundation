import json
import os
import threading
import unittest
import urllib.error
import urllib.request
from unittest.mock import patch
from http.server import ThreadingHTTPServer
from app.server import Handler, database_ready

class ServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = 'http://127.0.0.1:' + str(cls.server.server_port)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def request(self, path, headers=None):
        try:
            response = urllib.request.urlopen(urllib.request.Request(self.url + path, headers=headers or {}), timeout=3)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            return response.status, json.load(response)

    def test_live_does_not_depend_on_database(self):
        with patch('app.server.database_ready', side_effect=AssertionError('must not query')):
            self.assertEqual(self.request('/health/live'), (200, {'status': 'alive'}))

    def test_ready_when_database_available(self):
        with patch('app.server.database_ready', return_value=True):
            self.assertEqual(self.request('/health/ready'), (200, {'status': 'ready'}))

    def test_database_failure_is_not_leaked(self):
        with patch('app.server.database_ready', return_value=False):
            self.assertEqual(self.request('/health/ready'), (503, {'status': 'not_ready'}))

    def test_unknown_route_and_query_string(self):
        self.assertEqual(self.request('/missing')[0], 404)
        self.assertEqual(self.request('/health/live?secret=do-not-log')[0], 200)

    def test_missing_schema_is_not_data_ready(self):
        with patch('app.server.sales_summary', side_effect=RuntimeError('secret')):
            self.assertEqual(self.request('/health/data'), (503, {'status':'data_not_ready'}))
            self.assertEqual(self.request('/analytics/sales-summary'), (503, {'status':'data_not_ready'}))

    def test_data_health_and_summary(self):
        summary = {'data_class':'100% SYNTHETIC', 'amount_satang':'12345', 'as_of_date':'2026-09-30'}
        with patch('app.server.sales_summary', return_value=summary):
            self.assertEqual(self.request('/analytics/sales-summary'), (200, summary))
            self.assertEqual(self.request('/health/data'), (200, {'status':'data_ready','as_of_date':'2026-09-30'}))

    def test_auth_denies_before_database_query(self):
        with patch.dict(os.environ, {'API_AUTH_TOKEN': 'test-secret'}), patch('app.server.sales_summary', side_effect=AssertionError('must not query')):
            for headers in ({}, {'Authorization': 'Bearer wrong'}, {'Authorization': 'Basic test-secret'}):
                self.assertEqual(self.request('/analytics/sales-summary', headers), (401, {'error': 'unauthorized'}))
            self.assertEqual(self.request('/health/data')[0], 401)
            self.assertEqual(self.request('/health/live')[0], 200)

    def test_auth_allows_valid_token_without_logging_it(self):
        summary = {'as_of_date': '2026-09-30', 'data_class': '100% SYNTHETIC'}
        with patch.dict(os.environ, {'API_AUTH_TOKEN': 'test-secret'}), patch('app.server.sales_summary', return_value=summary), self.assertLogs('cloud-foundation', level='INFO') as captured:
            self.assertEqual(self.request('/analytics/sales-summary', {'Authorization': 'Bearer test-secret'}), (200, summary))
            self.assertEqual(self.request('/health/data', {'Authorization': 'Bearer test-secret'})[0], 200)
        self.assertNotIn('test-secret', '\n'.join(captured.output))

    def test_missing_dsn_is_not_ready(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(database_ready())

    def test_driver_exception_is_not_exposed(self):
        import sys
        from types import SimpleNamespace
        def fail(*args, **kwargs):
            raise RuntimeError('secret connection information')
        with patch.dict(os.environ, {'DATABASE_URL':'postgresql://secret'}), patch.dict(sys.modules, {'psycopg': SimpleNamespace(connect=fail)}):
            self.assertFalse(database_ready())

    def test_logs_do_not_contain_user_query(self):
        with self.assertLogs('cloud-foundation', level='INFO') as captured:
            self.request('/health/live?password=private-value')
        self.assertNotIn('private-value', '\n'.join(captured.output))

if __name__ == '__main__':
    unittest.main()

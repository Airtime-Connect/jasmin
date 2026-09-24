"""Synthetic sovereign startup tests; no vault, broker, or socket is used."""

import base64
import os
import unittest
from unittest.mock import Mock, patch

from jasmin.managers.testhub_c2 import C2Denied, TestHubC2Runtime
from jasmin.managers.testhub_c2_pg import PostgresC2Authority
from jasmin.managers.testhub_c2_bootstrap import load_testhub_c2_guard
from jasmin.managers.testhub_c2_sovereign import (
    C2SovereignError, DB_SECRET, KEY_SECRET, ROLE_PREFLIGHT, VAULT_HELPER,
    _build, _read_secret,
)


DOMAIN = 'testhub.example'
DSN = b'postgresql://reader@db.example/testhub?sslmode=verify-full'
KEY = base64.b64encode(b'k' * 32)


class FakeCursor:
    def __init__(self, row=(True,), fail_execute=False, fail_close=False):
        self.row = row
        self.fail_execute = fail_execute
        self.fail_close = fail_close
        self.queries = []

    def execute(self, query, args=None):
        self.queries.append((query, args))
        if self.fail_execute:
            raise RuntimeError('sensitive SQL detail')

    def fetchone(self):
        return self.row

    def close(self):
        if self.fail_close:
            raise RuntimeError('sensitive cursor close detail')


class FakeConnection:
    def __init__(self, cursor=None, fail_close=False):
        self.fake_cursor = cursor or FakeCursor()
        self.fail_close = fail_close
        self.closed = False

    def cursor(self):
        return self.fake_cursor

    def close(self):
        self.closed = True
        if self.fail_close:
            raise RuntimeError('sensitive connection close detail')


class SovereignFactoryTests(unittest.TestCase):
    def setUp(self):
        self.values = {DB_SECRET: DSN, KEY_SECRET: KEY}
        self.read_secret = Mock(side_effect=lambda domain, name: self.values[name])
        self.connection = FakeConnection()
        self.connect = Mock(return_value=self.connection)
        self.environ = {'JASMIN_TESTHUB_C2_VAULT_DOMAIN': DOMAIN}

    def build(self):
        return _build(self.environ, self.read_secret, self.connect)

    def test_missing_and_invalid_domain_fail_before_helper_or_database(self):
        for domain in ('', '.', '..', 'a..b', '../other', 'a/b', 'a b', 'a\nother'):
            with self.subTest(domain=domain), self.assertRaises(C2SovereignError):
                self.environ['JASMIN_TESTHUB_C2_VAULT_DOMAIN'] = domain
                self.build()
        self.read_secret.assert_not_called()
        self.connect.assert_not_called()

    def test_connection_and_reader_role_failure_deny_startup(self):
        self.connect.side_effect = RuntimeError('sensitive DSN detail')
        with self.assertRaisesRegex(C2SovereignError, '^C2 database role preflight failed$') as raised:
            self.build()
        self.assertNotIn('sensitive', str(raised.exception))
        self.connect.side_effect = None
        for row in ((False,), None, (1,)):
            self.connection = FakeConnection(FakeCursor(row=row))
            self.connect.return_value = self.connection
            with self.subTest(row=row), self.assertRaises(C2SovereignError):
                self.build()
            self.assertTrue(self.connection.closed)

    def test_query_or_cleanup_failure_preserves_fixed_denial(self):
        for cursor in (FakeCursor(fail_execute=True), FakeCursor(fail_close=True)):
            self.connection = FakeConnection(cursor, fail_close=True)
            self.connect.return_value = self.connection
            with self.subTest(cursor=cursor), self.assertRaisesRegex(
                    C2SovereignError, '^C2 database role preflight failed$') as raised:
                self.build()
            self.assertNotIn('sensitive', str(raised.exception))
            self.assertTrue(self.connection.closed)

    def test_success_uses_dedicated_reader_and_material(self):
        guard = self.build()
        self.assertIsInstance(guard, TestHubC2Runtime)
        self.assertEqual(guard.key, b'k' * 32)
        self.assertIsInstance(guard.get_scope.__self__, PostgresC2Authority)
        self.assertEqual(self.read_secret.call_count, 2)
        self.read_secret.assert_any_call(DOMAIN, DB_SECRET)
        self.read_secret.assert_any_call(DOMAIN, KEY_SECRET)
        self.connect.assert_called_once_with(DSN.decode())
        self.assertEqual(self.connection.fake_cursor.queries, [(ROLE_PREFLIGHT, None)])
        self.assertTrue(self.connection.closed)

    def test_required_bootstrap_loads_exact_sovereign_factory(self):
        config = {**self.environ, 'JASMIN_TESTHUB_C2_REQUIRED': '1',
                  'JASMIN_TESTHUB_C2_FACTORY':
                  'jasmin.managers.testhub_c2_sovereign:build'}
        with patch.dict(os.environ, config, clear=True), \
                patch('jasmin.managers.testhub_c2_sovereign._read_secret',
                      self.read_secret), \
                patch('jasmin.managers.testhub_c2_sovereign._connect', self.connect):
            guard = load_testhub_c2_guard()
        self.assertIsInstance(guard, TestHubC2Runtime)
        self.assertEqual(guard.key, b'k' * 32)

    def test_reader_preflight_requires_cross_tenant_select_without_mutation(self):
        for fragment in ('testhub.c2_principals', 'testhub.c2_leases',
                         'testhub.airtime_connectors', 'NOT has_schema_privilege',
                         'NOT has_function_privilege', 'c.relrowsecurity',
                         "NOT has_table_privilege(current_user, 'testhub.routes', 'SELECT')"):
            self.assertIn(fragment, ROLE_PREFLIGHT)

    def test_missing_helper_and_vault_failure_have_fixed_error(self):
        with patch('jasmin.managers.testhub_c2_sovereign.subprocess.run',
                   side_effect=FileNotFoundError('secret path')) as run:
            with self.assertRaisesRegex(C2SovereignError, '^C2 vault read unavailable$'):
                _read_secret(DOMAIN, DB_SECRET)
        self.assertEqual(run.call_args.args[0], [VAULT_HELPER, DOMAIN, DB_SECRET])
        self.assertEqual(run.call_args.kwargs['timeout'], 10)

    def test_connection_sets_connect_and_query_deadlines(self):
        from jasmin.managers.testhub_c2_sovereign import _connect
        driver = Mock()
        with patch('jasmin.managers.testhub_c2_sovereign.importlib.import_module',
                   return_value=driver):
            _connect(DSN.decode())
        driver.connect.assert_called_once_with(
            DSN.decode(), connect_timeout=3, autocommit=True,
            options='-c statement_timeout=3000 -c default_transaction_read_only=on')

    def test_invalid_dsn_and_key_fail_before_database(self):
        for dsn in (b'', b'not-a-dsn', b'postgresql://reader@db:bad/testhub?sslmode=verify-full',
                    b'postgresql://db.example/testhub', b'postgresql://reader@db.example/',
                    b'postgresql://reader@db.example/testhub',
                    b'postgresql://reader@db.example/testhub\nsecret'):
            with self.subTest(dsn=dsn), self.assertRaises(C2SovereignError):
                self.values[DB_SECRET] = dsn
                self.build()
        self.values[DB_SECRET] = DSN
        for key in (b'', b'not-base64', base64.b64encode(b'short')):
            with self.subTest(key=key), self.assertRaises(C2SovereignError):
                self.values[KEY_SECRET] = key
                self.build()
        self.connect.assert_not_called()

import json
import unittest
from dataclasses import asdict
from types import SimpleNamespace

from jasmin.managers.testhub_c2 import C2Denied, TestHubC2Runtime
from jasmin.managers.testhub_c2_pg import PostgresC2Authority


class FakeStore:
    def __init__(self):
        self.uid = ('test-uid', '11111111-1111-1111-1111-111111111111',
                    'test-cid', True)
        self.lease = ('22222222-2222-2222-2222-222222222222',
                      self.uid[1], '33333333-3333-3333-3333-333333333333',
                      'test-uid', 'test-cid', 1, 1, 4102444800, 'nonce', False)
        self.down = False
        self.commercial = False
        self.fail_close = False
        self.calls = []

    def connect(self):
        if self.down:
            raise ConnectionError('store unavailable')
        return FakeConnection(self)


class FakeConnection:
    def __init__(self, store):
        self.store = store
        self.closed = False

    def cursor(self):
        return FakeCursor(self.store)

    def close(self):
        self.closed = True
        if self.store.fail_close:
            raise RuntimeError('sensitive connection close detail')


class FakeCursor:
    def __init__(self, store):
        self.store = store
        self.row = None

    def execute(self, sql, args):
        self.store.calls.append((sql, args))
        assert len(args) == 1 and '%s' in sql
        if 'FROM testhub.c2_leases' in sql:
            self.row = self.store.lease if args[0] == 'test-uid' else None
        elif 'JOIN testhub.airtime_connectors' in sql:
            self.row = self.store.uid if args[0] == 'test-uid' else None
            if self.row and self.store.commercial and 'c.is_airtime' in sql:
                self.row = (*self.row[:-1], False)
        elif 'WHERE uid' in sql:
            self.row = (1,) if args[0] == 'test-uid' else None
        else:
            self.row = (1,) if args[0] == 'test-cid' else None

    def fetchone(self):
        return self.row

    def close(self):
        if self.store.fail_close:
            raise RuntimeError('sensitive cursor close detail')


class PostgresC2AuthorityTests(unittest.TestCase):
    def setUp(self):
        self.store = FakeStore()
        self.authority = PostgresC2Authority(self.store.connect)
        self.guard = TestHubC2Runtime(
            self.authority.is_test_uid, self.authority.is_test_cid,
            self.authority.get_scope, self.authority.get_lease, b'k' * 32)

    def content(self):
        return SimpleNamespace(properties={'message-id': 'mid', 'headers': {}}, body=b'payload')

    def test_fresh_registry_and_lease_allow_dedicated_path(self):
        content = self.content()
        token = self.guard.enqueue('test-uid', 'test-cid', content)
        content.properties['headers']['testhub-c2'] = token
        self.assertTrue(self.guard.egress('test-cid', SimpleNamespace(content=content)))
        self.assertEqual(json.loads(token)['tenant_id'], self.store.uid[1])
        self.assertGreaterEqual(len(self.store.calls), 7)

    def test_revocation_between_enqueue_and_egress_denies(self):
        content = self.content()
        content.properties['headers']['testhub-c2'] = self.guard.enqueue('test-uid', 'test-cid', content)
        self.store.lease = (*self.store.lease[:-1], True)
        with self.assertRaises(C2Denied):
            self.guard.egress('test-cid', SimpleNamespace(content=content))

    def test_store_outage_denies_without_cached_lease(self):
        content = self.content()
        content.properties['headers']['testhub-c2'] = self.guard.enqueue('test-uid', 'test-cid', content)
        self.store.down = True
        with self.assertRaises(C2Denied):
            self.guard.egress('test-cid', SimpleNamespace(content=content))

    def test_disabled_connector_and_mismatched_tenant_deny(self):
        self.store.uid = (*self.store.uid[:-1], False)
        with self.assertRaises(C2Denied):
            self.guard.enqueue('test-uid', 'test-cid', self.content())
        self.store.uid = ('test-uid', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 'test-cid', True)
        with self.assertRaises(C2Denied):
            self.guard.enqueue('test-uid', 'test-cid', self.content())

    def test_commercial_connector_is_airtime_false_denies(self):
        self.store.commercial = True
        with self.assertRaises(C2Denied):
            self.guard.enqueue('test-uid', 'test-cid', self.content())
        self.assertTrue(any('c.is_airtime' in sql for sql, _ in self.store.calls))

    def test_registry_reserves_disabled_ids_for_pb_denial(self):
        self.store.uid = (*self.store.uid[:-1], False)
        self.assertFalse(self.guard.remote_pb_submit_allowed('test-uid', 'commercial-cid'))
        self.assertFalse(self.guard.remote_pb_submit_allowed('commercial-uid', 'test-cid'))

    def test_queries_bind_values_instead_of_interpolating(self):
        suspicious = "test-uid' OR TRUE --"
        self.assertFalse(self.authority.is_test_uid(suspicious))
        sql, args = self.store.calls[-1]
        self.assertNotIn(suspicious, sql)
        self.assertEqual(args, (suspicious,))

    def test_invalid_rows_fail_closed(self):
        self.store.uid = (*self.store.uid[:-1], 'true')
        with self.assertRaises(C2Denied):
            self.authority.get_scope('test-uid')
        self.store.lease = self.store.lease[:-1]
        with self.assertRaises(C2Denied):
            self.authority.get_lease('test-uid')

    def test_cleanup_errors_do_not_escape_or_leak(self):
        self.store.fail_close = True
        with self.assertRaisesRegex(C2Denied, '^C2 registry or lease store unavailable$'):
            self.authority.is_test_uid('test-uid')
        self.store.down = True
        with self.assertRaisesRegex(C2Denied, '^C2 registry or lease store unavailable$') as raised:
            self.authority.is_test_uid('test-uid')
        self.assertNotIn('sensitive', str(raised.exception))


if __name__ == '__main__':
    unittest.main()

"""Adversarial tests of the Test Hub C2 boundary contract (no SMS sent)."""

from dataclasses import replace
from types import SimpleNamespace
import time
import unittest

from jasmin.managers.testhub_c2 import (
    C2Denied, PrincipalScope, RouteLease, TestHubC2Runtime,
    authorize_egress, authorize_enqueue,
)


KEY = b'local-test-key-only-not-a-runtime-secret!'
BODY = b'pickled-pdu-placeholder'
SCOPE = PrincipalScope('test-uid-a', 'tenant-a', 'airtime-cid-a', True)
LEASE = RouteLease('route-a', 'tenant-a', 'test-a', 'test-uid-a',
                   'airtime-cid-a', 3, 100, 160, 'nonce-a')


class TestHubC2ContractTests(unittest.TestCase):
    def enqueue(self, scope=SCOPE, lease=LEASE, **kwargs):
        params = dict(message_id='msg-a', authenticated_uid='test-uid-a',
                      routed_cid='airtime-cid-a', body=BODY, scope=scope,
                      lease=lease, key=KEY, now=120)
        params.update(kwargs)
        return authorize_enqueue(**params)

    def egress(self, provenance=None, scope=SCOPE, lease=LEASE, **kwargs):
        params = dict(provenance=self.enqueue() if provenance is None else provenance,
                      message_id='msg-a', consumer_cid='airtime-cid-a', body=BODY,
                      scope=scope, lease=lease, key=KEY, now=121)
        params.update(kwargs)
        return authorize_egress(**params)

    def test_valid_dedicated_route(self):
        self.assertTrue(self.egress())

    def test_http_or_smpp_metadata_cannot_override_authenticated_uid(self):
        with self.assertRaises(C2Denied):
            self.enqueue(authenticated_uid='commercial-uid')

    def test_failover_to_commercial_connector_is_denied(self):
        with self.assertRaises(C2Denied):
            self.enqueue(routed_cid='commercial-cid')
        with self.assertRaises(C2Denied):
            self.egress(consumer_cid='commercial-cid')

    def test_wrong_tenant_and_disabled_principal_are_denied(self):
        for scope in (replace(SCOPE, tenant_id='tenant-b'), replace(SCOPE, enabled=False)):
            with self.subTest(scope=scope), self.assertRaises(C2Denied):
                self.enqueue(scope=scope)

    def test_missing_revoked_expired_or_not_yet_valid_lease_is_denied(self):
        for lease, now in ((None, 120), (replace(LEASE, revoked=True), 120),
                           (LEASE, 160), (LEASE, 99)):
            with self.subTest(lease=lease, now=now), self.assertRaises(C2Denied):
                self.enqueue(lease=lease, now=now)

    def test_queue_delay_and_revocation_are_checked_at_egress(self):
        token = self.enqueue()
        with self.assertRaises(C2Denied):
            self.egress(provenance=token, now=160)
        with self.assertRaises(C2Denied):
            self.egress(provenance=token, lease=replace(LEASE, revoked=True))

    def test_lease_rotation_invalidates_queued_provenance(self):
        with self.assertRaises(C2Denied):
            self.egress(lease=replace(LEASE, generation=4, nonce='nonce-b'))

    def test_direct_broker_injection_and_tampering_are_denied(self):
        token = self.enqueue()
        for provenance in (object(), replace(token, uid='commercial-uid'),
                           replace(token, mac='0' * 64)):
            with self.subTest(provenance=provenance), self.assertRaises(C2Denied):
                self.egress(provenance=provenance)
        with self.assertRaises(C2Denied):
            self.egress(provenance=token, body=b'changed-pdu')

    def test_missing_or_short_key_is_denied_at_both_boundaries(self):
        for key in (None, b'short'):
            with self.subTest(key=key), self.assertRaises(C2Denied):
                self.enqueue(key=key)
            with self.subTest(key=key), self.assertRaises(C2Denied):
                self.egress(key=key)

    def test_lease_checks_do_not_extend_expiration(self):
        token = self.enqueue()
        self.assertEqual(LEASE.expires_at, 160)
        self.assertTrue(self.egress(provenance=token, now=159))
        with self.assertRaises(C2Denied):
            self.egress(provenance=token, now=160)


class TestHubC2RuntimeTests(unittest.TestCase):
    def setUp(self):
        now = int(time.time())
        self.lease = replace(LEASE, not_before=now - 5, expires_at=now + 30)
        self.guard = TestHubC2Runtime(
            lambda uid: uid == SCOPE.uid,
            lambda cid: cid == SCOPE.cid,
            lambda uid: SCOPE if uid == SCOPE.uid else None,
            lambda uid: self.lease if uid == SCOPE.uid else None,
            KEY,
        )
        self.content = SimpleNamespace(properties={'message-id': 'msg-a', 'headers': {}}, body=BODY)
        self.message = SimpleNamespace(content=self.content)

    def test_protected_message_passes_both_boundaries(self):
        token = self.guard.enqueue(SCOPE.uid, SCOPE.cid, self.content)
        self.content.properties['headers']['testhub-c2'] = token
        self.assertTrue(self.guard.egress(SCOPE.cid, self.message))

    def test_reserved_connector_rejects_missing_provenance(self):
        with self.assertRaises(C2Denied):
            self.guard.egress(SCOPE.cid, self.message)

    def test_test_principal_cannot_failover_to_commercial_connector(self):
        with self.assertRaises(C2Denied):
            self.guard.enqueue(SCOPE.uid, 'commercial-cid', self.content)

    def test_missing_scope_and_store_outage_deny(self):
        with self.assertRaises(C2Denied):
            self.guard.enqueue('commercial-uid', SCOPE.cid, self.content)
        self.guard.get_lease = lambda uid: (_ for _ in ()).throw(ConnectionError('store down'))
        with self.assertRaises(C2Denied):
            self.guard.enqueue(SCOPE.uid, SCOPE.cid, self.content)
        self.content.properties['headers']['testhub-c2'] = 'forged'
        with self.assertRaises(C2Denied):
            self.guard.egress(SCOPE.cid, self.message)

    def test_commercial_path_remains_unchanged(self):
        self.assertIsNone(self.guard.enqueue('commercial-uid', 'commercial-cid', self.content))
        self.assertTrue(self.guard.egress('commercial-cid', self.message))

    def test_revocation_after_enqueue_denies_egress(self):
        self.content.properties['headers']['testhub-c2'] = self.guard.enqueue(SCOPE.uid, SCOPE.cid, self.content)
        self.lease = replace(self.lease, revoked=True)
        with self.assertRaises(C2Denied):
            self.guard.egress(SCOPE.cid, self.message)


if __name__ == '__main__':
    unittest.main()

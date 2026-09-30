"""Synthetic C2 peer-boundary tests; no external SMPP or network calls."""

import time
import unittest
from types import SimpleNamespace

from jasmin.managers.testhub_c2 import C2Denied, PrincipalScope, RouteLease, TestHubC2Runtime


class PeerBoundaryTests(unittest.TestCase):
    def setUp(self):
        now = int(time.time())
        self.scope = PrincipalScope('test-uid', 'tenant-a', 'test-cid', True)
        self.lease = RouteLease('route-a', 'tenant-a', 'test-a', 'test-uid',
                                'test-cid', 1, now - 5, now + 30, 'nonce-a')
        self.content = SimpleNamespace(properties={'message-id': 'mid', 'headers': {}}, body=b'pdu')
        self.message = SimpleNamespace(content=self.content)
        self.config = SimpleNamespace(id='test-cid', host='approved.example', port=2775)
        self.transport = SimpleNamespace(connected=True,
                                         getPeer=lambda: SimpleNamespace(host='192.0.2.10', port=2775))
        self.protocol = SimpleNamespace(transport=self.transport)

    def guard(self, verifier=None):
        return TestHubC2Runtime(
            lambda uid: uid == self.scope.uid, lambda cid: cid == self.scope.cid,
            lambda uid: self.scope, lambda uid: self.lease, b'k' * 32,
            verify_peer=verifier)

    def signed(self, guard):
        self.content.properties['headers']['testhub-c2'] = guard.enqueue(
            self.scope.uid, self.scope.cid, self.content)

    def test_missing_authority_or_live_transport_denies_protected_egress(self):
        guard = self.guard()
        self.signed(guard)
        with self.assertRaises(C2Denied):
            guard.egress('test-cid', self.message, self.config, self.protocol)
        guard.verify_peer = lambda *_: True
        for protocol in (None, SimpleNamespace(transport=None),
                         SimpleNamespace(transport=SimpleNamespace(getPeer=lambda: None))):
            with self.subTest(protocol=protocol), self.assertRaises(C2Denied):
                guard.egress('test-cid', self.message, self.config, protocol)

    def test_same_cid_upstream_swap_and_peer_swap_are_denied(self):
        seen = []

        def approved(cid, config, transport, peer):
            seen.append((cid, config.host, peer.host, transport))
            return (cid, config.host, peer.host) == ('test-cid', 'approved.example', '192.0.2.10')

        guard = self.guard(approved)
        self.signed(guard)
        self.assertTrue(guard.egress('test-cid', self.message, self.config, self.protocol))
        changed_config = SimpleNamespace(id='test-cid', host='other.example', port=2775)
        with self.assertRaises(C2Denied):
            guard.egress('test-cid', self.message, changed_config, self.protocol)
        changed_protocol = SimpleNamespace(transport=SimpleNamespace(connected=True,
            getPeer=lambda: SimpleNamespace(host='192.0.2.11', port=2775)))
        with self.assertRaises(C2Denied):
            guard.egress('test-cid', self.message, self.config, changed_protocol)
        self.assertEqual(len(seen), 3)

    def test_truthy_non_boolean_and_verifier_failure_deny(self):
        guard = self.guard(lambda *_: 'true')
        self.signed(guard)
        with self.assertRaises(C2Denied):
            guard.egress('test-cid', self.message, self.config, self.protocol)
        guard.verify_peer = lambda *_: (_ for _ in ()).throw(RuntimeError('secret detail'))
        with self.assertRaises(C2Denied) as raised:
            guard.egress('test-cid', self.message, self.config, self.protocol)
        self.assertNotIn('secret detail', str(raised.exception))


if __name__ == '__main__':
    unittest.main()

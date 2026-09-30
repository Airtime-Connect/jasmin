"""Real loopback PB dispatch test; fake manager, no broker or SMSC."""

import logging
from types import SimpleNamespace

from twisted.cred import portal
from twisted.cred.checkers import AllowAnonymousAccess
from twisted.internet import defer, reactor
from twisted.spread import pb
from twisted.trial.unittest import TestCase

from jasmin.managers.testhub_c2 import C2Denied
from jasmin.tools.cred.portal import SMPPClientManagerPBRealm
from jasmin.tools.spread.pb import JasminPBPortalRoot


class FakeManager:
    def __init__(self):
        self.log = logging.getLogger('c2-pb-portal-test')
        self.testhub_c2_guard = SimpleNamespace(
            remote_pb_submit_allowed=lambda uid, cid: False,
            remote_pb_connector_mutation_allowed=lambda cid: cid != 'test-cid',
        )
        self.submit_calls = 0
        self.mutations = []

    def setAvatar(self, avatar):
        self.avatar = avatar

    def perspective_submit_sm(self, *args, **kwargs):
        self.submit_calls += 1
        return 'unsafe'

    def perspective_version(self):
        return 'test-version'

    def perspective_connector_remove(self, cid):
        self.mutations.append(('remove', cid))
        return 'removed'

    def perspective_connector_start(self, cid):
        self.mutations.append(('start', cid))
        return 'started'

    def perspective_connector_stop(self, cid):
        self.mutations.append(('stop', cid))
        return 'stopped'

    def perspective_connector_add(self, config):
        self.mutations.append(('add', config))
        return 'added'

    def perspective_load(self, profile='jcli-prod'):
        self.mutations.append(('load', profile))
        return 'loaded'

    def perspective_connector_stopall(self):
        self.mutations.append(('stopall', None))
        return 'stopped-all'


class TestHubPBPortalTests(TestCase):
    def setUp(self):
        self.manager = FakeManager()
        access = portal.Portal(SMPPClientManagerPBRealm(self.manager))
        access.registerChecker(AllowAnonymousAccess())
        self.port = reactor.listenTCP(0, pb.PBServerFactory(JasminPBPortalRoot(access)), interface='127.0.0.1')
        self.client = pb.PBClientFactory()
        self.connector = reactor.connectTCP('127.0.0.1', self.port.getHost().port, self.client)

    @defer.inlineCallbacks
    def tearDown(self):
        self.connector.disconnect()
        yield self.port.stopListening()

    @defer.inlineCallbacks
    def test_remote_submit_denied_and_other_operation_delegated(self):
        root = yield self.client.getRootObject()
        avatar = yield root.callRemote('loginAnonymous', None)
        denied = yield avatar.callRemote('submit_sm', 'test-uid', 'test-cid', b'pdu', None)
        version = yield avatar.callRemote('version')
        self.assertIs(denied, False)
        self.assertEqual(self.manager.submit_calls, 0)
        self.assertEqual(version, 'test-version')

    @defer.inlineCallbacks
    def test_protected_and_unbounded_connector_mutations_denied_before_dispatch(self):
        root = yield self.client.getRootObject()
        avatar = yield root.callRemote('loginAnonymous', None)
        for method in ('connector_remove', 'connector_start', 'connector_stop'):
            self.assertIs((yield avatar.callRemote(method, 'test-cid')), False)
        self.assertIs((yield avatar.callRemote('connector_add', b'untrusted-pickle')), False)
        self.assertIs((yield avatar.callRemote('load', 'jcli-prod')), False)
        self.assertIs((yield avatar.callRemote('connector_stopall')), False)
        self.assertEqual(self.manager.mutations, [])

    @defer.inlineCallbacks
    def test_commercial_cid_mutations_and_legacy_mode_still_delegate(self):
        root = yield self.client.getRootObject()
        avatar = yield root.callRemote('loginAnonymous', None)
        self.assertEqual((yield avatar.callRemote('connector_remove', 'commercial-cid')), 'removed')
        self.assertEqual((yield avatar.callRemote('connector_start', 'commercial-cid')), 'started')
        self.assertEqual((yield avatar.callRemote('connector_stop', 'commercial-cid')), 'stopped')
        self.manager.testhub_c2_guard = None
        self.assertEqual((yield avatar.callRemote('connector_add', b'legacy-config')), 'added')
        self.assertEqual((yield avatar.callRemote('load', 'jcli-prod')), 'loaded')
        self.assertEqual((yield avatar.callRemote('connector_stopall')), 'stopped-all')
        self.assertEqual(self.manager.mutations, [
            ('remove', 'commercial-cid'), ('start', 'commercial-cid'),
            ('stop', 'commercial-cid'), ('add', b'legacy-config'),
            ('load', 'jcli-prod'), ('stopall', None),
        ])

    @defer.inlineCallbacks
    def test_classification_outage_denies_remote_connector_mutation(self):
        self.manager.testhub_c2_guard.remote_pb_connector_mutation_allowed = (
            lambda cid: (_ for _ in ()).throw(C2Denied('registry unavailable'))
        )
        root = yield self.client.getRootObject()
        avatar = yield root.callRemote('loginAnonymous', None)
        self.assertIs((yield avatar.callRemote('connector_remove', 'commercial-cid')), False)
        self.assertEqual(self.manager.mutations, [])

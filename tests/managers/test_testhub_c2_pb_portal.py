"""Real loopback PB dispatch test; fake manager, no broker or SMSC."""

import logging
from types import SimpleNamespace

from twisted.cred import portal
from twisted.cred.checkers import AllowAnonymousAccess
from twisted.internet import defer, reactor
from twisted.spread import pb
from twisted.trial.unittest import TestCase

from jasmin.tools.cred.portal import SMPPClientManagerPBRealm
from jasmin.tools.spread.pb import JasminPBPortalRoot


class FakeManager:
    def __init__(self):
        self.log = logging.getLogger('c2-pb-portal-test')
        self.testhub_c2_guard = SimpleNamespace(remote_pb_submit_allowed=lambda uid, cid: False)
        self.submit_calls = 0

    def setAvatar(self, avatar):
        self.avatar = avatar

    def perspective_submit_sm(self, *args, **kwargs):
        self.submit_calls += 1
        return 'unsafe'

    def perspective_version(self):
        return 'test-version'


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

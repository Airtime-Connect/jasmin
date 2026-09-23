"""Shared Jasmin enqueue hook tests using a fake broker, without SMS traffic."""

import logging
import pickle
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from twisted.internet import defer
from twisted.spread import pb

from jasmin.managers.clients import SMPPClientManagerPB
from jasmin.managers.testhub_c2 import C2Denied
from jasmin.tools.cred.portal import SMPPClientManagerPBRealm


class EnqueueHookTests(unittest.TestCase):
    def setUp(self):
        config = SimpleNamespace(log_level=logging.ERROR, log_file='stdout',
                                 log_format='%(message)s', log_date_format='',
                                 pickle_protocol=pickle.HIGHEST_PROTOCOL)
        self.manager = SMPPClientManagerPB(config)
        self.manager.connectors = [{'id': 'airtime-cid-a', 'sm_listener': SimpleNamespace()}]
        self.manager.amqpBroker = SimpleNamespace(connected=True, publish=Mock(return_value=defer.succeed(None)))

    def submit(self, uid='test-uid-a', cid='airtime-cid-a'):
        return self.manager.perspective_submit_sm(uid, cid, b'pdu', None, pickled=False).result

    def test_guard_deny_prevents_amqp_publish(self):
        guard = SimpleNamespace(enqueue=Mock(side_effect=C2Denied('lease expired')))
        self.manager.setTestHubC2Guard(guard)
        self.assertFalse(self.submit())
        self.manager.amqpBroker.publish.assert_not_called()
        guard.enqueue.assert_called_once()

    def test_signed_provenance_reaches_amqp_content(self):
        guard = SimpleNamespace(enqueue=Mock(return_value='signed-token'))
        self.manager.setTestHubC2Guard(guard)
        self.assertIsInstance(self.submit(), str)
        self.manager.amqpBroker.publish.assert_called_once()
        content = self.manager.amqpBroker.publish.call_args.kwargs['content']
        self.assertEqual(content.properties['headers']['testhub-c2'], 'signed-token')


class RemotePBIdentityBoundaryTests(unittest.TestCase):
    setUp = EnqueueHookTests.setUp

    def avatar(self):
        interface, avatar, _logout = SMPPClientManagerPBRealm(self.manager).requestAvatar(
            'cmadmin', None, pb.IPerspective)
        self.assertIs(interface, pb.IPerspective)
        return avatar

    def test_each_pb_login_receives_distinct_facade(self):
        first, second = self.avatar(), self.avatar()
        self.assertIsNot(first, second)
        self.assertIs(first.manager, self.manager)
        self.assertIs(second.manager, self.manager)

    def test_remote_pb_cannot_submit_test_uid_or_cid(self):
        guard = SimpleNamespace(
            remote_pb_submit_allowed=Mock(return_value=False),
            enqueue=Mock(return_value=None))
        self.manager.setTestHubC2Guard(guard)
        self.manager.perspective_submit_sm = Mock(return_value='should-not-send')
        self.assertFalse(self.avatar().perspective_submit_sm('test-uid-a', 'commercial-cid', b'pdu', None))
        self.assertFalse(self.avatar().perspective_submit_sm('commercial-uid', 'airtime-cid-a', b'pdu', None))
        self.manager.perspective_submit_sm.assert_not_called()
        self.manager.amqpBroker.publish.assert_not_called()

    def test_remote_pb_registry_failure_denies_without_delegate(self):
        guard = SimpleNamespace(remote_pb_submit_allowed=Mock(side_effect=C2Denied('store down')))
        self.manager.setTestHubC2Guard(guard)
        self.manager.perspective_submit_sm = Mock(return_value='should-not-send')
        self.assertFalse(self.avatar().perspective_submit_sm('test-uid-a', 'airtime-cid-a', b'pdu', None))
        self.manager.perspective_submit_sm.assert_not_called()

    def test_twisted_pb_dispatch_uses_restricted_facade(self):
        guard = SimpleNamespace(remote_pb_submit_allowed=Mock(return_value=False))
        self.manager.setTestHubC2Guard(guard)
        self.manager.perspective_submit_sm = Mock(return_value='should-not-send')
        broker = SimpleNamespace(
            unserialize=lambda value, avatar: value,
            serialize=lambda result, avatar, method, args, kwargs: result,
        )
        result = self.avatar().perspectiveMessageReceived(
            broker, 'submit_sm', ('test-uid-a', 'airtime-cid-a', b'pdu', None), {})
        self.assertFalse(result)
        self.manager.perspective_submit_sm.assert_not_called()

    def test_commercial_pb_submit_still_delegates(self):
        guard = SimpleNamespace(remote_pb_submit_allowed=Mock(return_value=True))
        self.manager.setTestHubC2Guard(guard)
        self.manager.perspective_submit_sm = Mock(return_value='commercial-ok')
        self.assertEqual(self.avatar().perspective_submit_sm('commercial-uid', 'commercial-cid', b'pdu', None),
                         'commercial-ok')
        self.manager.perspective_submit_sm.assert_called_once()

    def test_other_manager_operations_still_delegate(self):
        self.manager.perspective_version = Mock(return_value='0.12')
        self.assertEqual(self.avatar().perspective_version(), '0.12')


if __name__ == '__main__':
    unittest.main()

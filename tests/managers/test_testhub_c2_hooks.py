"""Shared Jasmin enqueue hook tests using a fake broker, without SMS traffic."""

import logging
import pickle
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from twisted.internet import defer

from jasmin.managers.clients import SMPPClientManagerPB
from jasmin.managers.testhub_c2 import C2Denied


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


if __name__ == '__main__':
    unittest.main()

"""Protected AMQP payloads are authenticated before pickle.loads is reached."""

import logging
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from twisted.internet import defer

from jasmin.managers.listeners import SMPPClientSMListener
from jasmin.managers.testhub_c2 import C2Denied


class PreDeserializeBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.listener = object.__new__(SMPPClientSMListener)
        self.listener.log = logging.getLogger(__name__)
        self.listener.SMPPClientFactory = SimpleNamespace(config=SimpleNamespace(id='airtime-cid-a'))
        self.listener.submit_sm_q = SimpleNamespace(get=Mock(return_value=defer.Deferred()))
        self.listener.submit_sm_errback = Mock()
        self.listener.rejectMessage = Mock(return_value=defer.succeed(None))
        self.message = SimpleNamespace(content=SimpleNamespace(
            properties={'message-id': 'msg-a', 'headers': {}},
            body=b'potentially unsafe pickle bytes'))

    def test_missing_provenance_is_rejected_before_pickle(self):
        guard = Mock()
        guard.egress.side_effect = C2Denied('missing signed provenance')
        self.listener.testhub_c2_guard = guard
        with patch('jasmin.managers.listeners.pickle.loads') as load:
            result = self.listener.submit_sm_callback(self.message)
            self.assertTrue(result.called)
            self.assertFalse(result.result)
            load.assert_not_called()
        guard.egress.assert_called_once_with('airtime-cid-a', self.message)
        self.listener.rejectMessage.assert_called_once_with(self.message)
        self.listener.submit_sm_q.get.assert_called_once()

    def test_store_failure_is_rejected_before_pickle(self):
        guard = Mock()
        guard.egress.side_effect = C2Denied('authority unavailable')
        self.listener.testhub_c2_guard = guard
        with patch('jasmin.managers.listeners.pickle.loads') as load:
            result = self.listener.submit_sm_callback(self.message)
            self.assertTrue(result.called)
            self.assertFalse(result.result)
            load.assert_not_called()
        self.listener.rejectMessage.assert_called_once_with(self.message)


if __name__ == '__main__':
    unittest.main()

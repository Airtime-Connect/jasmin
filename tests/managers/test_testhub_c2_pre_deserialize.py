"""Protected AMQP payloads are authenticated before pickle.loads is reached."""

import logging
from datetime import datetime
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from twisted.internet import defer
from smpp.pdu.operations import SubmitSM

from jasmin.managers.listeners import SMPPClientSMListener
from jasmin.managers.testhub_c2 import C2Denied


class PreDeserializeBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.listener = object.__new__(SMPPClientSMListener)
        self.listener.log = logging.getLogger(__name__)
        self.listener.SMPPClientFactory = SimpleNamespace(
            config=SimpleNamespace(id='airtime-cid-a'), smpp=SimpleNamespace())
        self.listener.submit_sm_q = SimpleNamespace(get=Mock(return_value=defer.Deferred()))
        self.listener.submit_sm_errback = Mock()
        self.listener.rejectMessage = Mock(return_value=defer.succeed(None))
        self.message = SimpleNamespace(content=SimpleNamespace(
            properties={'message-id': 'msg-a', 'headers': {}},
            body=b'potentially unsafe pickle bytes'))

    def test_missing_provenance_is_rejected_before_pickle(self):
        guard = Mock()
        guard.authenticate_message.side_effect = C2Denied('missing signed provenance')
        self.listener.testhub_c2_guard = guard
        with patch('jasmin.managers.listeners.pickle.loads') as load:
            result = self.listener.submit_sm_callback(self.message)
            self.assertTrue(result.called)
            self.assertFalse(result.result)
            load.assert_not_called()
        guard.authenticate_message.assert_called_once_with('airtime-cid-a', self.message)
        self.listener.rejectMessage.assert_called_once_with(self.message)
        self.listener.submit_sm_q.get.assert_called_once()

    def test_store_failure_is_rejected_before_pickle(self):
        guard = Mock()
        guard.authenticate_message.side_effect = C2Denied('authority unavailable')
        self.listener.testhub_c2_guard = guard
        with patch('jasmin.managers.listeners.pickle.loads') as load:
            result = self.listener.submit_sm_callback(self.message)
            self.assertTrue(result.called)
            self.assertFalse(result.result)
            load.assert_not_called()
        self.listener.rejectMessage.assert_called_once_with(self.message)

    def test_current_protocol_is_checked_after_deserialization_before_send(self):
        guard = Mock()
        guard.egress.side_effect = C2Denied('peer changed')
        self.listener.testhub_c2_guard = guard
        self.listener.submit_retrials = {}
        self.listener.qos_last_submit_sm_at = None
        self.listener.SMPPClientFactory.config.submit_sm_throughput = 0
        new_protocol = SimpleNamespace(isBound=Mock(return_value=True),
                                       sendDataRequest=Mock())

        def deserialize(_):
            self.listener.SMPPClientFactory.smpp = new_protocol
            return SubmitSM()

        with patch('jasmin.managers.listeners.pickle.loads', side_effect=deserialize):
            result = self.listener.submit_sm_callback(self.message)
        self.assertTrue(result.called)
        self.assertFalse(result.result)
        guard.authenticate_message.assert_called_once_with('airtime-cid-a', self.message)
        guard.egress.assert_called_once_with(
            'airtime-cid-a', self.message,
            self.listener.SMPPClientFactory.config, new_protocol)
        new_protocol.sendDataRequest.assert_not_called()
        self.listener.rejectMessage.assert_called_once_with(self.message)

    def test_disconnected_protected_queue_item_retains_retry_path(self):
        guard = Mock()
        self.listener.testhub_c2_guard = guard
        self.listener.SMPPClientFactory.smpp = None
        self.listener.SMPPClientFactory.config.submit_sm_throughput = 0
        self.listener.submit_retrials = {}
        self.listener.qos_last_submit_sm_at = None
        self.listener.config = SimpleNamespace(submit_max_age_smppc_not_ready=100,
                                               submit_retrial_delay_smppc_not_ready=0)
        self.listener.rejectAndRequeueMessage = Mock(return_value=defer.succeed(None))
        self.message.content.properties['headers']['created_at'] = datetime.now().isoformat()
        with patch('jasmin.managers.listeners.pickle.loads', return_value=SubmitSM()):
            result = self.listener.submit_sm_callback(self.message)
        self.assertTrue(result.called)
        self.assertFalse(result.result)
        guard.authenticate_message.assert_called_once_with('airtime-cid-a', self.message)
        guard.egress.assert_not_called()
        self.listener.rejectAndRequeueMessage.assert_called_once_with(self.message, delay=0)
        self.listener.rejectMessage.assert_not_called()


if __name__ == '__main__':
    unittest.main()

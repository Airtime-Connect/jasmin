"""C2 startup gate tests; no broker, vault, or network service is contacted."""

import os
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from jasmin.bin.jasmind import JasminDaemon
from jasmin.managers.clients import SMPPClientManagerPBAvatar
from jasmin.managers.testhub_c2 import TestHubC2Runtime
from jasmin.managers.testhub_c2_bootstrap import C2BootstrapError, load_testhub_c2_guard


class C2BootstrapTests(unittest.TestCase):
    def setUp(self):
        self.guard = TestHubC2Runtime(
            lambda uid: uid == 'protected-uid',
            lambda cid: cid == 'protected-cid',
            lambda uid: None, lambda uid: None, b'x' * 32)
        module = ModuleType('testhub_c2_test_adapter')
        module.build = Mock(return_value=self.guard)
        self.factory = module.build
        self.module = patch.dict(sys.modules, {'testhub_c2_test_adapter': module})
        self.module.start()

    def tearDown(self):
        self.module.stop()

    def config(self, **values):
        return {'JASMIN_TESTHUB_C2_REQUIRED': '1',
                'JASMIN_TESTHUB_C2_FACTORY': 'testhub_c2_test_adapter:build', **values}

    def test_guard_loads_only_when_required(self):
        self.assertIsNone(load_testhub_c2_guard({}))
        self.factory.assert_not_called()
        self.assertIs(load_testhub_c2_guard(self.config()), self.guard)

    def test_factory_without_required_flag_is_configuration_error(self):
        with self.assertRaises(C2BootstrapError):
            load_testhub_c2_guard({'JASMIN_TESTHUB_C2_FACTORY': 'testhub_c2_test_adapter:build'})
        self.factory.assert_not_called()

    def test_missing_factory_and_init_failure_are_fail_closed(self):
        with self.assertRaises(C2BootstrapError):
            load_testhub_c2_guard({'JASMIN_TESTHUB_C2_REQUIRED': '1'})
        self.factory.side_effect = RuntimeError('sensitive adapter detail')
        with self.assertRaisesRegex(C2BootstrapError, 'initialization failed') as raised:
            load_testhub_c2_guard(self.config())
        self.assertNotIn('sensitive', str(raised.exception))

    def test_wrong_runtime_or_key_is_rejected(self):
        for value in (object(), TestHubC2Runtime(None, None, None, None, b'short')):
            self.factory.return_value = value
            with self.assertRaises(C2BootstrapError):
                load_testhub_c2_guard(self.config())

    def test_booted_guard_denies_remote_protected_uid_and_cid(self):
        guard = load_testhub_c2_guard(self.config())
        manager = SimpleNamespace(testhub_c2_guard=guard, perspective_submit_sm=Mock(), log=Mock())
        avatar = SMPPClientManagerPBAvatar(manager)
        self.assertFalse(avatar.perspective_submit_sm('protected-uid', 'commercial-cid', b'pdu', None))
        self.assertFalse(avatar.perspective_submit_sm('commercial-uid', 'protected-cid', b'pdu', None))
        manager.perspective_submit_sm.assert_not_called()

    def test_daemon_installs_guard_before_pb_listen_and_keeps_one_instance(self):
        manager = Mock()
        manager.testhub_c2_guard = self.guard
        events = []
        manager.setTestHubC2Guard.side_effect = lambda guard: events.append('guard')
        with patch('jasmin.bin.os.makedirs'):
            daemon = JasminDaemon({'config': 'unused'})
        daemon.components['amqp-broker-factory'] = Mock()
        daemon.components['rc'] = Mock()
        daemon.components['router-pb-factory'] = Mock()
        fake_config = SimpleNamespace(authentication=False, port=14001, bind='127.0.0.1')
        with patch.dict(os.environ, self.config(), clear=True), \
                patch('jasmin.bin.jasmind.SMPPClientPBConfig', return_value=fake_config), \
                patch('jasmin.bin.jasmind.SMPPClientManagerPB', return_value=manager), \
                patch('jasmin.bin.jasmind.reactor.listenTCP',
                      side_effect=lambda *args, **kwargs: events.append('listen')) as listen:
            daemon.startSMPPClientManagerPBService()
            self.assertIs(daemon.configureTestHubC2(), self.guard)
        manager.setTestHubC2Guard.assert_called_once_with(self.guard)
        self.factory.assert_called_once_with()
        self.assertEqual(listen.call_count, 1)
        self.assertEqual(events, ['guard', 'listen'])

    def test_daemon_never_opens_pb_port_when_authority_init_fails(self):
        with patch('jasmin.bin.os.makedirs'):
            daemon = JasminDaemon({'config': 'unused'})
        self.factory.side_effect = RuntimeError('unavailable')
        with patch.dict(os.environ, self.config(), clear=True), \
                patch('jasmin.bin.jasmind.reactor.listenTCP') as listen:
            with self.assertRaises(C2BootstrapError):
                daemon.startSMPPClientManagerPBService()
        listen.assert_not_called()
        self.assertNotIn('smppcm-pb-factory', daemon.components)

    def test_required_authority_failure_stops_daemon_before_any_service(self):
        with patch('jasmin.bin.os.makedirs'):
            daemon = JasminDaemon({'config': 'unused'})
        self.factory.side_effect = RuntimeError('unavailable')
        failures = []
        with patch.dict(os.environ, self.config(), clear=True), \
                patch.object(daemon, 'startRedisClient') as redis, \
                patch.object(daemon, 'startAMQPBrokerService') as amqp, \
                patch.object(daemon, 'startRouterPBService') as router:
            daemon.start().addErrback(lambda failure: failures.append(failure))
        self.assertEqual(len(failures), 1)
        failures[0].trap(C2BootstrapError)
        redis.assert_not_called()
        amqp.assert_not_called()
        router.assert_not_called()


if __name__ == '__main__':
    unittest.main()

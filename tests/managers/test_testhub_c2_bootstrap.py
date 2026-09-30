"""C2 startup gate tests; no broker, vault, or network service is contacted."""

import os
import sys
from contextlib import ExitStack
from hashlib import md5
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from jasmin.bin.jasmind import JasminDaemon
from jasmin.bin.interceptord import InterceptorDaemon
from jasmin.managers.clients import SMPPClientManagerPBAvatar
from jasmin.managers.testhub_c2 import TestHubC2Runtime
from jasmin.managers.testhub_c2_bootstrap import (
    C2BootstrapError, load_testhub_c2_guard, require_nondefault_jcli_auth,
    require_nondefault_interceptor_auth, require_nondefault_router_auth,
    require_nondefault_smppcm_auth, require_nondefault_smpps_auth)


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

    def safe_management_patches(self, client_config=None):
        safe = SimpleNamespace(authentication=True, admin_username='operator',
                               admin_password=md5(b'unique-test-password').digest())
        stack = ExitStack()
        stack.enter_context(patch('jasmin.bin.jasmind.RouterPBConfig', return_value=safe))
        stack.enter_context(patch('jasmin.bin.jasmind.SMPPServerPBConfig', return_value=safe))
        stack.enter_context(patch('jasmin.bin.jasmind.SMPPClientPBConfig',
                                  side_effect=[safe, client_config] if client_config else None,
                                  return_value=safe))
        return stack

    def test_guard_loads_only_when_required(self):
        self.assertIsNone(load_testhub_c2_guard({}))
        self.factory.assert_not_called()
        self.assertIs(load_testhub_c2_guard(self.config()), self.guard)

    def test_factory_without_required_flag_is_configuration_error(self):
        with self.assertRaises(C2BootstrapError):
            load_testhub_c2_guard({'JASMIN_TESTHUB_C2_FACTORY': 'testhub_c2_test_adapter:build'})
        self.factory.assert_not_called()

    def test_c2_jcli_auth_rejects_disabled_and_default_credentials(self):
        custom = SimpleNamespace(authentication=True, admin_username='operator',
                                 admin_password=md5(b'unique-test-password').digest())
        require_nondefault_jcli_auth(custom)
        for unsafe in (
                SimpleNamespace(authentication=False, admin_username='operator',
                                admin_password=custom.admin_password),
                SimpleNamespace(authentication=True, admin_username='jcliadmin',
                                admin_password=custom.admin_password),
                SimpleNamespace(authentication=True, admin_username='operator',
                                admin_password=md5(b'jclipwd').digest())):
            with self.assertRaisesRegex(C2BootstrapError, 'jCLI management'):
                require_nondefault_jcli_auth(unsafe)

    def test_c2_jcli_auth_fails_before_authority_or_listener(self):
        with patch('jasmin.bin.os.makedirs'):
            daemon = JasminDaemon({'config': 'unused'})
        defaults = SimpleNamespace(authentication=True, admin_username='jcliadmin',
                                   admin_password=md5(b'jclipwd').digest())
        with patch.dict(os.environ, self.config(), clear=True), \
                self.safe_management_patches(), \
                patch('jasmin.bin.jasmind.JCliConfig', return_value=defaults), \
                patch('jasmin.bin.jasmind.reactor.listenTCP') as listen:
            with self.assertRaises(C2BootstrapError):
                daemon.startSMPPClientManagerPBService()
        self.factory.assert_not_called()
        listen.assert_not_called()

    def test_disabled_jcli_does_not_require_console_credentials(self):
        with patch('jasmin.bin.os.makedirs'):
            daemon = JasminDaemon({'config': 'unused', 'disable-jcli': True})
        with patch.dict(os.environ, self.config(), clear=True), \
                self.safe_management_patches(), \
                patch('jasmin.bin.jasmind.JCliConfig') as jcli_config:
            self.assertIs(daemon.configureTestHubC2(), self.guard)
        jcli_config.assert_not_called()

    def test_c2_interceptor_auth_rejects_disabled_and_default_credentials(self):
        custom = SimpleNamespace(authentication=True, admin_username='operator',
                                 admin_password=md5(b'unique-interceptor-password').digest())
        require_nondefault_interceptor_auth(custom)
        for unsafe in (
                SimpleNamespace(authentication=False, admin_username='operator',
                                admin_password=custom.admin_password),
                SimpleNamespace(authentication=True, admin_username='iadmin',
                                admin_password=custom.admin_password),
                SimpleNamespace(authentication=True, admin_username='operator',
                                admin_password=md5(b'ipwd').digest())):
            with self.assertRaisesRegex(C2BootstrapError, 'interceptor PB'):
                require_nondefault_interceptor_auth(unsafe)

    def test_c2_main_pb_auth_rejects_shipped_defaults(self):
        custom = SimpleNamespace(authentication=True, admin_username='operator',
                                 admin_password=md5(b'unique-test-password').digest())
        for check, username, digest in (
                (require_nondefault_router_auth, 'radmin', '82a606ca5a0deea2b5777756788af5c8'),
                (require_nondefault_smppcm_auth, 'cmadmin', 'e1c5136acafb7016bc965597c992eb82'),
                (require_nondefault_smpps_auth, 'smppsadmin', 'e97ab122faa16beea8682d84f3d2eea4')):
            check(custom)
            for unsafe in (
                    SimpleNamespace(authentication=False, admin_username='operator',
                                    admin_password=custom.admin_password),
                    SimpleNamespace(authentication=True, admin_username=username,
                                    admin_password=custom.admin_password),
                    SimpleNamespace(authentication=True, admin_username='operator',
                                    admin_password=bytes.fromhex(digest))):
                with self.assertRaises(C2BootstrapError):
                    check(unsafe)

    def test_interceptor_process_rejects_defaults_before_listener(self):
        defaults = SimpleNamespace(authentication=True, admin_username='iadmin',
                                   admin_password=md5(b'ipwd').digest())
        with patch.dict(os.environ, self.config(), clear=True), \
                patch('jasmin.bin.os.makedirs'), \
                patch('jasmin.bin.interceptord.InterceptorPBConfig', return_value=defaults), \
                patch('jasmin.bin.interceptord.reactor.listenTCP') as listen:
            with self.assertRaises(C2BootstrapError):
                InterceptorDaemon({'config': 'unused'})
        listen.assert_not_called()

    def test_main_daemon_rejects_interceptor_defaults_before_authority(self):
        with patch('jasmin.bin.os.makedirs'):
            daemon = JasminDaemon({'config': 'unused', 'enable-interceptor-client': True})
        safe_jcli = SimpleNamespace(authentication=True, admin_username='operator',
                                    admin_password=md5(b'unique-test-password').digest())
        defaults = SimpleNamespace(authentication=True, admin_username='iadmin',
                                   admin_password=md5(b'ipwd').digest())
        with patch.dict(os.environ, self.config(), clear=True), \
                self.safe_management_patches(), \
                patch('jasmin.bin.jasmind.JCliConfig', return_value=safe_jcli), \
                patch('jasmin.bin.jasmind.InterceptorPBConfig', return_value=defaults), \
                patch('jasmin.bin.jasmind.reactor.listenTCP') as listen:
            with self.assertRaises(C2BootstrapError):
                daemon.configureTestHubC2()
        self.factory.assert_not_called()
        listen.assert_not_called()

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
                self.safe_management_patches(fake_config), \
                patch('jasmin.bin.jasmind.JCliConfig', return_value=SimpleNamespace(
                    authentication=True, admin_username='operator',
                    admin_password=md5(b'unique-test-password').digest())), \
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
                self.safe_management_patches(), \
                patch('jasmin.bin.jasmind.JCliConfig', return_value=SimpleNamespace(
                    authentication=True, admin_username='operator',
                    admin_password=md5(b'unique-test-password').digest())), \
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
                self.safe_management_patches(), \
                patch('jasmin.bin.jasmind.JCliConfig', return_value=SimpleNamespace(
                    authentication=True, admin_username='operator',
                    admin_password=md5(b'unique-test-password').digest())), \
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

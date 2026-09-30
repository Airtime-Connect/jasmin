"""Check the packaged C2 image rejects its shipped management configuration."""

import os
import subprocess
from hashlib import md5
from unittest.mock import patch

from jasmin.bin.interceptord import InterceptorDaemon
from jasmin.bin.jasmind import JasminDaemon
from jasmin.managers.testhub_c2_bootstrap import C2BootstrapError


def main():
    os.environ['JASMIN_TESTHUB_C2_REQUIRED'] = '1'
    checks = (
        ('main', lambda: JasminDaemon({
            'config': '/etc/jasmin/jasmin.cfg',
            'enable-interceptor-client': True}).configureTestHubC2()),
        ('interceptor', lambda: InterceptorDaemon({
            'config': '/etc/jasmin/interceptor.cfg'})),
    )
    for name, check in checks:
        try:
            check()
        except C2BootstrapError:
            print('%s shipped management config rejected PASS' % name)
        else:
            raise AssertionError('%s accepted shipped management config' % name)

    # Synthetic credentials pass management checks. The sovereign factory then
    # rejects an empty domain before reading a vault secret or opening a socket.
    environment = os.environ.copy()
    environment['JASMIN_TESTHUB_C2_FACTORY'] = 'jasmin.managers.testhub_c2_sovereign:build'
    environment['JASMIN_TESTHUB_C2_VAULT_DOMAIN'] = ''
    digest = md5(b'synthetic-ci-password').hexdigest()
    for section in ('ROUTER', 'CLIENT_MANAGEMENT', 'SMPP_SERVER_PB', 'JCLI', 'INTERCEPTOR'):
        environment['%s_ADMIN_USERNAME' % section] = 'synthetic-ci-admin'
        environment['%s_ADMIN_PASSWORD' % section] = digest
    with patch.dict(os.environ, environment, clear=True):
        try:
            JasminDaemon({'config': '/etc/jasmin/jasmin.cfg',
                          'enable-interceptor-client': True}).configureTestHubC2()
        except C2BootstrapError as exc:
            if str(exc) != 'C2 AMQP broker authentication is unsafe':
                raise AssertionError('packaged default broker identity was not the rejected gate')
        else:
            raise AssertionError('packaged default broker identity was accepted')
    print('packaged default AMQP identity rejected PASS')

    environment['AMQP_BROKER_USERNAME'] = 'synthetic-ci-broker'
    environment['AMQP_BROKER_PASSWORD'] = 'synthetic-ci-password'
    with patch.dict(os.environ, environment, clear=True):
        try:
            JasminDaemon({'config': '/etc/jasmin/jasmin.cfg',
                          'enable-interceptor-client': True}).configureTestHubC2()
        except C2BootstrapError as exc:
            if str(exc) != 'C2 authority initialization failed':
                raise AssertionError('synthetic broker config did not reach sovereign factory')
        else:
            raise AssertionError('empty vault domain was accepted')
    print('synthetic AMQP identity reaches sovereign authority PASS')

    result = subprocess.run(
        ['/docker-entrypoint.sh', 'jasmind.py', '--enable-interceptor-client',
         '--enable-dlr-thrower', '--enable-dlr-lookup', '-u', 'jcliadmin',
         '-p', 'jclipwd'],
        env=environment, capture_output=True, timeout=10, check=False)
    output = result.stdout + result.stderr
    if (result.returncode == 0
            or b'C2 entrypoint preflight failed' not in output
            or b'Traceback' in output
            or b'Starting interceptord' in output
            or b'Starting jasmind' in output):
        raise AssertionError('C2 entrypoint launched a child before authority validation')
    print('entrypoint authority failure before child launch PASS')


if __name__ == '__main__':
    main()

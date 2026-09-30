"""Check the packaged C2 image rejects its shipped management configuration."""

import os
import subprocess
from hashlib import md5

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

"""Check the packaged C2 image rejects its shipped management configuration."""

import os

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


if __name__ == '__main__':
    main()

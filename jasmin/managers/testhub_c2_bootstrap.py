"""Install the C2 authority from a trusted, deployment-packaged adapter.

No registry, lease, or key is synthesized here. A protected deployment must
provide a factory backed by the sovereign control plane and SOPS vault.
"""

import importlib
import os
from hashlib import md5

from .testhub_c2 import TestHubC2Runtime


class C2BootstrapError(RuntimeError):
    """The requested C2 guard is not ready; the daemon must not start."""


_SHIPPED_MANAGEMENT_USERS = frozenset((
    'jcliadmin', 'iadmin', 'radmin', 'cmadmin', 'smppsadmin',
))
_SHIPPED_MANAGEMENT_DIGESTS = frozenset((
    md5(b'jclipwd').digest(),
    md5(b'ipwd').digest(),
    bytes.fromhex('82a606ca5a0deea2b5777756788af5c8'),
    bytes.fromhex('e1c5136acafb7016bc965597c992eb82'),
    bytes.fromhex('e97ab122faa16beea8682d84f3d2eea4'),
    md5(b'').digest(),
))


def _require_nondefault_management_auth(config, default_user, default_digest, endpoint):
    username = config.admin_username
    digest = config.admin_password
    if (config.authentication is not True
            or not isinstance(username, str) or not username or username != username.strip()
            or username == default_user or username in _SHIPPED_MANAGEMENT_USERS
            or not isinstance(digest, bytes) or len(digest) != 16
            or digest == default_digest or digest in _SHIPPED_MANAGEMENT_DIGESTS):
        raise C2BootstrapError('C2 %s management authentication is unsafe' % endpoint)


def require_nondefault_jcli_auth(config):
    """Reject shipped console credentials before the main daemon starts."""
    _require_nondefault_management_auth(config, 'jcliadmin', md5(b'jclipwd').digest(), 'jCLI')


def require_nondefault_interceptor_auth(config):
    """Reject shipped interceptor PB credentials before its daemon starts."""
    _require_nondefault_management_auth(config, 'iadmin', md5(b'ipwd').digest(), 'interceptor PB')


def require_nondefault_router_auth(config):
    _require_nondefault_management_auth(
        config, 'radmin', bytes.fromhex('82a606ca5a0deea2b5777756788af5c8'), 'router PB')


def require_nondefault_smppcm_auth(config):
    _require_nondefault_management_auth(
        config, 'cmadmin', bytes.fromhex('e1c5136acafb7016bc965597c992eb82'), 'SMPP client PB')


def require_nondefault_smpps_auth(config):
    _require_nondefault_management_auth(
        config, 'smppsadmin', bytes.fromhex('e97ab122faa16beea8682d84f3d2eea4'), 'SMPP server PB')


def require_nondefault_amqp_auth(config):
    """The shipped broker identity cannot protect the C2 submit queues."""
    username = config.username
    password = config.password
    if (not isinstance(username, str) or not username or username != username.strip()
            or not isinstance(password, str) or not password or password != password.strip()
            or username == 'guest' or password == 'guest'):
        raise C2BootstrapError('C2 AMQP broker authentication is unsafe')


def load_testhub_c2_guard(environ=None):
    environ = os.environ if environ is None else environ
    required = environ.get('JASMIN_TESTHUB_C2_REQUIRED', '0')
    factory_path = environ.get('JASMIN_TESTHUB_C2_FACTORY', '')
    if required not in ('0', '1'):
        raise C2BootstrapError('invalid C2 required flag')
    if required == '0':
        if factory_path:
            raise C2BootstrapError('C2 factory configured without required guard')
        return None
    if not factory_path or factory_path.count(':') != 1:
        raise C2BootstrapError('C2 factory missing or invalid')
    module_name, function_name = factory_path.split(':')
    if not module_name or not function_name or not function_name.isidentifier():
        raise C2BootstrapError('C2 factory missing or invalid')
    try:
        factory = getattr(importlib.import_module(module_name), function_name)
        guard = factory()
        if (not isinstance(guard, TestHubC2Runtime)
                or any(not callable(getattr(guard, name, None)) for name in
                       ('is_test_uid', 'is_test_cid', 'get_scope', 'get_lease'))
                or not isinstance(guard.key, bytes) or len(guard.key) < 32):
            raise C2BootstrapError('C2 factory returned invalid authority')
        return guard
    except Exception:
        # Do not leak the factory's exception: it may contain a secret or DSN.
        raise C2BootstrapError('C2 authority initialization failed') from None

"""Install the C2 authority from a trusted, deployment-packaged adapter.

No registry, lease, or key is synthesized here. A protected deployment must
provide a factory backed by the sovereign control plane and SOPS vault.
"""

import importlib
import os

from .testhub_c2 import TestHubC2Runtime


class C2BootstrapError(RuntimeError):
    """The requested C2 guard is not ready; the daemon must not start."""


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

"""Disposable PostgreSQL contract across api-gateway SQL and Jasmin C2 code.

The shell harness creates a socket-only database with synthetic identities.
This file accepts only that socket path; it never reads deployment credentials.
"""

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import psycopg

from jasmin.managers.testhub_c2 import C2Denied, TestHubC2Runtime
from jasmin.managers.testhub_c2_pg import PostgresC2Authority
from jasmin.managers.testhub_c2_sovereign import _preflight


DATABASE = 'testhub_c2_crossrepo'
UID = 'synthetic-uid-a'
CID = 'synthetic-cid-a'
ROUTE = '10000000-0000-4000-8000-000000000011'
TENANT = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'
PAIRS = frozenset({
    ('synthetic-uid-a', 'synthetic-cid-a'),
    ('synthetic-uid-disabled', 'synthetic-cid-disabled'),
    ('synthetic-uid-tenant-b', 'synthetic-cid-tenant-b'),
})


def connect(socket, user):
    return psycopg.connect(host=socket, dbname=DATABASE, user=user,
                           connect_timeout=2, autocommit=True)


def require_denied(action, label):
    try:
        action()
    except C2Denied:
        return
    raise AssertionError(f'{label} unexpectedly passed C2')


def runtime(authority):
    return TestHubC2Runtime(authority.is_test_uid, authority.is_test_cid,
                            authority.get_scope, authority.get_lease, b'k' * 32,
                            verify_peer=lambda *_: True)  # DB contract only; peer gate has separate tests.


def run_live(socket):
    factory = lambda: connect(socket, 'testhub_c2_reader')
    _preflight(factory)
    authority = PostgresC2Authority(factory)
    assert authority.list_reserved_pairs() == PAIRS
    assert authority.is_test_uid('synthetic-uid-tenant-b')
    assert authority.is_test_cid('synthetic-cid-disabled')
    assert not authority.is_test_uid('commercial-uid')
    assert not authority.is_test_cid('commercial-cid')

    guard = runtime(authority)
    assert not guard.remote_pb_submit_allowed(UID, 'commercial-cid')
    assert not guard.remote_pb_submit_allowed('commercial-uid', CID)
    assert guard.remote_pb_submit_allowed('commercial-uid', 'commercial-cid')

    content = SimpleNamespace(properties={'message-id': 'synthetic-message',
                                          'headers': {}}, body=b'synthetic-only')
    require_denied(lambda: guard.enqueue(UID, CID, content), 'missing lease')
    require_denied(lambda: guard.enqueue(UID, 'commercial-cid', content),
                   'commercial connector')
    require_denied(lambda: guard.enqueue('synthetic-uid-disabled',
                                        'synthetic-cid-disabled', content),
                   'disabled connector')

    with connect(socket, 'testhub_c2_provisioner') as connection:
        with connection.cursor() as cursor:
            cursor.execute('SELECT (testhub.issue_c2_lease(%s,%s,%s)).generation',
                           (UID, ROUTE, 30))
            assert cursor.fetchone() == (1,)

    token = guard.enqueue(UID, CID, content)
    assert json.loads(token)['uid'] == UID
    message = SimpleNamespace(content=SimpleNamespace(
        properties={'message-id': 'synthetic-message',
                    'headers': {'testhub-c2': token}}, body=b'synthetic-only'))
    config = SimpleNamespace(id=CID)
    protocol = SimpleNamespace(transport=SimpleNamespace(
        connected=True, getPeer=lambda: SimpleNamespace(host='192.0.2.10')))
    assert guard.egress(CID, message, config, protocol)
    require_denied(lambda: guard.egress('commercial-cid', message),
                   'commercial egress with Test Hub provenance')

    with connect(socket, 'testhub_route_operator') as connection:
        with connection.transaction():
            with connection.cursor() as cursor:
                cursor.execute("SELECT set_config('app.tenant_id', %s, true)",
                               (TENANT,))
                cursor.execute('UPDATE testhub.routes SET status = %s WHERE route_id = %s',
                               ('EXPIRED', ROUTE))
                assert cursor.rowcount == 1

    lease = authority.get_lease(UID)
    assert lease.revoked is True and lease.generation == 2
    require_denied(lambda: guard.egress(CID, message, config, protocol), 'egress after route exit')
    require_denied(lambda: guard.enqueue(UID, CID, content),
                   'enqueue after route exit')
    print('PASS: real PG18 reader preflight, cross-tenant registry, PB gate, '
          'lease issuance, enqueue/egress, route-exit revocation')


def run_outage(socket):
    authority = PostgresC2Authority(lambda: connect(socket, 'testhub_c2_reader'))
    require_denied(lambda: authority.get_lease(UID), 'reader outage')
    require_denied(lambda: runtime(authority).enqueue(
        UID, CID, SimpleNamespace(properties={'message-id': 'synthetic-message'},
                                  body=b'synthetic-only')), 'enqueue during outage')
    print('PASS: reader outage denies C2 authority and protected enqueue')


if __name__ == '__main__':
    if len(sys.argv) != 3 or sys.argv[1] not in ('live', 'outage'):
        raise SystemExit('usage: c2_pg_crossrepo.py live|outage SOCKET')
    socket_path = Path(sys.argv[2])
    if not str(socket_path).startswith('/private/tmp/atc-testhub-c2-crossrepo.'):
        raise SystemExit('refusing non-disposable PostgreSQL socket')
    (run_live if sys.argv[1] == 'live' else run_outage)(str(socket_path))

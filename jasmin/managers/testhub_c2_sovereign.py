"""Opt-in sovereign factory for the Test Hub C2 startup gate.

The two secret names are a proposed deployment contract, not provisioned
credentials. The bootstrap calls build() only when C2_REQUIRED=1.
"""

import base64
import binascii
import importlib
import json
import os
import re
import subprocess
from urllib.parse import parse_qs, urlsplit

from .testhub_c2 import TestHubC2Runtime
from .testhub_c2_pg import PostgresC2Authority


VAULT_HELPER = '/opt/vault/bin/read-secret.sh'
DB_SECRET = 'testhub-c2-db-url'
KEY_SECRET = 'testhub-c2-hmac-key-b64'
RESERVED_SECRET = 'testhub-c2-reserved-identifiers-json'
SAFE_DOMAIN = re.compile(r'^(?!.*\.\.)(?!\.)([A-Za-z0-9][A-Za-z0-9._-]*)$')

# A cross-tenant classifier must see all reserved UIDs/CIDs. This query also
# rejects mutation privileges on the three tables it reads. RLS completeness
# still requires a separate DB-side attestation before deployment.
ROLE_PREFLIGHT = '''
SELECT NOT r.rolsuper AND NOT r.rolbypassrls
 AND has_table_privilege(current_user, 'testhub.c2_principals', 'SELECT')
 AND has_table_privilege(current_user, 'testhub.c2_leases', 'SELECT')
 AND has_table_privilege(current_user, 'testhub.airtime_connectors', 'SELECT')
 AND NOT has_schema_privilege(current_user, 'testhub', 'CREATE')
 AND NOT has_function_privilege(current_user, 'testhub.issue_c2_lease(text,uuid,integer)', 'EXECUTE')
 AND NOT has_function_privilege(current_user, 'testhub.revoke_c2_lease(text)', 'EXECUTE')
 AND NOT has_table_privilege(current_user, 'testhub.routes', 'SELECT')
 AND NOT has_any_column_privilege(current_user, 'testhub.routes', 'SELECT')
 AND NOT has_table_privilege(current_user, 'testhub.witness_hops', 'SELECT')
 AND NOT has_any_column_privilege(current_user, 'testhub.witness_hops', 'SELECT')
 AND NOT has_table_privilege(current_user, 'testhub.verdicts', 'SELECT')
 AND NOT has_any_column_privilege(current_user, 'testhub.verdicts', 'SELECT')
 AND NOT has_table_privilege(current_user, 'testhub.c2_principals', 'INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER')
 AND NOT has_table_privilege(current_user, 'testhub.c2_leases', 'INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER')
 AND NOT has_table_privilege(current_user, 'testhub.airtime_connectors', 'INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER')
 AND NOT EXISTS (
   SELECT 1 FROM pg_class c
   WHERE c.oid IN ('testhub.c2_principals'::regclass, 'testhub.c2_leases'::regclass)
     AND c.relrowsecurity
 )
FROM pg_roles r WHERE r.rolname = current_user
'''


class C2SovereignError(RuntimeError):
    """Configuration or sovereign authority is unavailable."""


def _read_secret(domain, name):
    try:
        result = subprocess.run(
            [VAULT_HELPER, domain, name], check=True, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, timeout=10)
        value = result.stdout.removesuffix(b'\n')
        if not value or len(value) > 65536 or b'\n' in value or b'\r' in value:
            raise ValueError('invalid vault value')
        return value
    except Exception:
        raise C2SovereignError('C2 vault read unavailable') from None


def _connect(dsn):
    try:
        psycopg = importlib.import_module('psycopg')
        return psycopg.connect(
            dsn, connect_timeout=3, autocommit=True,
            options='-c statement_timeout=3000 -c default_transaction_read_only=on')
    except Exception:
        # libpq errors may include DSN fields; never forward them to bootstrap.
        raise C2SovereignError('C2 PostgreSQL connection unavailable') from None


def _preflight(connection_factory):
    connection = None
    cursor = None
    cleanup_failed = False
    try:
        connection = connection_factory()
        cursor = connection.cursor()
        cursor.execute(ROLE_PREFLIGHT)
        row = cursor.fetchone()
        if not isinstance(row, tuple) or len(row) != 1 or type(row[0]) is not bool or not row[0]:
            raise C2SovereignError('C2 database role lacks read-only scope')
    except Exception:
        raise C2SovereignError('C2 database role preflight failed') from None
    finally:
        if cursor is not None:
            try:
                cursor.close()
            except Exception:
                cleanup_failed = True
        if connection is not None:
            try:
                connection.close()
            except Exception:
                cleanup_failed = True
    if cleanup_failed:
        raise C2SovereignError('C2 database role preflight failed') from None


def _reserved_identifiers(raw):
    """Exact, independently inventoried Jasmin IDs; never infer from a prefix."""
    try:
        document = json.loads(raw)
        if type(document) is not dict or set(document) != {'principals'}:
            raise ValueError()
        pairs = document['principals']
        if type(pairs) is not list or not 1 <= len(pairs) <= 4096:
            raise ValueError()
        uids, cids = set(), set()
        for pair in pairs:
            if type(pair) is not dict or set(pair) != {'uid', 'cid'}:
                raise ValueError()
            uid, cid = pair['uid'], pair['cid']
            if (type(uid) is not str or type(cid) is not str or not uid or not cid
                    or uid != uid.strip() or cid != cid.strip()
                    or len(uid) > 256 or len(cid) > 256
                    or uid in uids or cid in cids):
                raise ValueError()
            uids.add(uid)
            cids.add(cid)
        return tuple((pair['uid'], pair['cid']) for pair in pairs), frozenset(uids), frozenset(cids)
    except (ValueError, TypeError, UnicodeError):
        raise C2SovereignError('C2 reserved identifier inventory invalid') from None


def _build(environ, read_secret, connect):
    domain = environ.get('JASMIN_TESTHUB_C2_VAULT_DOMAIN', '')
    if not SAFE_DOMAIN.fullmatch(domain):
        raise C2SovereignError('C2 vault domain missing or invalid')
    raw_dsn = read_secret(domain, DB_SECRET)
    raw_key = read_secret(domain, KEY_SECRET)
    raw_reserved = read_secret(domain, RESERVED_SECRET)
    try:
        dsn = raw_dsn.decode('utf-8')
        parsed = urlsplit(dsn)
        parsed.port  # Reject a malformed explicit port before opening a socket.
        sslmode = parse_qs(parsed.query, keep_blank_values=True).get('sslmode')
        key = base64.b64decode(raw_key, validate=True)
        if (parsed.scheme not in ('postgresql', 'postgres') or not parsed.hostname
                or not parsed.username or len(parsed.path) < 2
                or sslmode != ['verify-full']
                or any(char.isspace() for char in dsn) or len(key) < 32):
            raise ValueError('invalid authority material')
    except (UnicodeError, ValueError, binascii.Error):
        raise C2SovereignError('C2 authority material invalid') from None
    connection_factory = lambda: connect(dsn)
    _preflight(connection_factory)
    authority = PostgresC2Authority(connection_factory)
    pairs, reserved_uids, reserved_cids = _reserved_identifiers(raw_reserved)
    try:
        for uid, cid in pairs:
            scope = authority.get_scope(uid)
            if scope is None or scope.cid != cid:
                raise ValueError()
    except Exception:
        raise C2SovereignError('C2 reserved identifier reconciliation failed') from None
    return TestHubC2Runtime(lambda uid: uid in reserved_uids or authority.is_test_uid(uid),
                            lambda cid: cid in reserved_cids or authority.is_test_cid(cid),
                            authority.get_scope, authority.get_lease, key)


def build():
    """Entry point for JASMIN_TESTHUB_C2_FACTORY, default disabled."""
    return _build(os.environ, _read_secret, _connect)

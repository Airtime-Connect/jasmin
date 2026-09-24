"""Fresh, read-only PostgreSQL lookups for the Test Hub C2 guard.

The connection factory must use a dedicated SELECT-only sovereign database role.
No result is cached: loss of the database must deny protected submissions and
egress. This adapter never creates leases or obtains the provenance key.
"""

from .testhub_c2 import C2Denied, PrincipalScope, RouteLease


class PostgresC2Authority:
    def __init__(self, connection_factory):
        if not callable(connection_factory):
            raise ValueError('connection factory required')
        self.connection_factory = connection_factory

    def _one(self, query, value):
        connection = None
        cursor = None
        try:
            connection = self.connection_factory()
            cursor = connection.cursor()
            cursor.execute(query, (value,))
            return cursor.fetchone()
        except Exception as exc:
            raise C2Denied('C2 registry or lease store unavailable') from exc
        finally:
            if cursor is not None:
                cursor.close()
            if connection is not None:
                connection.close()

    def is_test_uid(self, uid):
        if not isinstance(uid, str) or not uid:
            raise C2Denied('invalid UID')
        row = self._one('SELECT 1 FROM testhub.c2_principals WHERE uid = %s', uid)
        return row is not None

    def is_test_cid(self, cid):
        if not isinstance(cid, str) or not cid:
            raise C2Denied('invalid CID')
        row = self._one('SELECT 1 FROM testhub.c2_principals WHERE cid = %s', cid)
        return row is not None

    def get_scope(self, uid):
        if not isinstance(uid, str) or not uid:
            raise C2Denied('invalid UID')
        row = self._one(
            'SELECT p.uid, p.tenant_id::text, p.cid, '
            '(p.enabled AND c.enabled) '
            'FROM testhub.c2_principals p '
            'JOIN testhub.airtime_connectors c ON c.connector_id = p.connector_id '
            'WHERE p.uid = %s', uid)
        if row is None:
            return None
        if len(row) != 4 or type(row[3]) is not bool:
            raise C2Denied('invalid C2 principal record')
        return PrincipalScope(*row)

    def get_lease(self, uid):
        if not isinstance(uid, str) or not uid:
            raise C2Denied('invalid UID')
        row = self._one(
            'SELECT l.route_id::text, l.tenant_id::text, l.test_id::text, '
            'l.uid, l.cid, l.generation, l.not_before, l.expires_at, '
            'l.nonce, l.revoked '
            'FROM testhub.c2_leases l WHERE l.uid = %s', uid)
        if row is None:
            return None
        if len(row) != 10:
            raise C2Denied('invalid C2 lease record')
        return RouteLease(*row)

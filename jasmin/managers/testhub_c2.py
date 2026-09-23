"""Test Hub C2 authorization contract for Jasmin's enqueue and egress boundaries.

The caller must obtain scopes and leases from trusted control-plane storage. HTTP
parameters, SMPP TLVs, AMQP headers, and ``source_connector`` are not authorities.
This module deliberately does not fetch secrets or install a runtime guard.
"""

from dataclasses import dataclass
from dataclasses import asdict
import hashlib
import hmac
import json
import time


class C2Denied(Exception):
    """A Test Hub submission cannot cross the requested boundary."""


@dataclass(frozen=True)
class PrincipalScope:
    uid: str
    tenant_id: str
    cid: str
    enabled: bool


@dataclass(frozen=True)
class RouteLease:
    route_id: str
    tenant_id: str
    test_id: str
    uid: str
    cid: str
    generation: int
    not_before: int
    expires_at: int
    nonce: str
    revoked: bool = False


@dataclass(frozen=True)
class Provenance:
    message_id: str
    uid: str
    cid: str
    route_id: str
    tenant_id: str
    test_id: str
    generation: int
    nonce: str
    body_sha256: str
    mac: str


def _required_text(*values):
    return all(isinstance(value, str) and value and value.strip() == value for value in values)


def _check_scope(scope, lease, now):
    if scope is None or lease is None or not isinstance(scope, PrincipalScope) or not isinstance(lease, RouteLease):
        raise C2Denied('missing trusted scope or lease')
    if not _required_text(scope.uid, scope.tenant_id, scope.cid, lease.route_id,
                          lease.tenant_id, lease.test_id, lease.uid, lease.cid, lease.nonce):
        raise C2Denied('incomplete scope or lease')
    if not scope.enabled or lease.revoked:
        raise C2Denied('disabled or revoked')
    if (scope.uid, scope.tenant_id, scope.cid) != (lease.uid, lease.tenant_id, lease.cid):
        raise C2Denied('principal, tenant, or connector mismatch')
    if (not isinstance(lease.generation, int) or isinstance(lease.generation, bool)
            or lease.generation < 1 or not isinstance(lease.not_before, int)
            or not isinstance(lease.expires_at, int) or lease.expires_at <= lease.not_before):
        raise C2Denied('invalid lease generation or interval')
    if now < lease.not_before or now >= lease.expires_at:
        raise C2Denied('lease outside its validity interval')


def _payload(message_id, scope, lease, body):
    return {
        'body_sha256': hashlib.sha256(body).hexdigest(),
        'cid': scope.cid,
        'generation': lease.generation,
        'message_id': message_id,
        'nonce': lease.nonce,
        'route_id': lease.route_id,
        'tenant_id': lease.tenant_id,
        'test_id': lease.test_id,
        'uid': scope.uid,
    }


def _mac(key, payload):
    if not isinstance(key, bytes) or len(key) < 32:
        raise C2Denied('missing C2 authentication key')
    canonical = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode('ascii')
    return hmac.new(key, canonical, hashlib.sha256).hexdigest()


def authorize_enqueue(message_id, authenticated_uid, routed_cid, body, scope, lease, key, now=None):
    """Sign provenance after Jasmin authenticates UID and finishes routing/failover."""
    now = int(time.time()) if now is None else now
    _check_scope(scope, lease, now)
    if not _required_text(message_id, authenticated_uid, routed_cid) or not isinstance(body, bytes):
        raise C2Denied('invalid message identity or body')
    if authenticated_uid != scope.uid or routed_cid != scope.cid:
        raise C2Denied('authenticated principal or final connector mismatch')
    payload = _payload(message_id, scope, lease, body)
    return Provenance(**payload, mac=_mac(key, payload))


def authorize_egress(provenance, message_id, consumer_cid, body, scope, lease, key, now=None):
    """Verify provenance and a fresh authoritative lease before network send."""
    now = int(time.time()) if now is None else now
    _check_scope(scope, lease, now)
    if not isinstance(provenance, Provenance) or not isinstance(body, bytes):
        raise C2Denied('missing or invalid provenance')
    if not _required_text(message_id, consumer_cid) or message_id != provenance.message_id:
        raise C2Denied('message identity mismatch')
    if consumer_cid != scope.cid:
        raise C2Denied('consumer connector mismatch')
    expected = _payload(message_id, scope, lease, body)
    supplied = {field: getattr(provenance, field) for field in expected}
    if (supplied != expected or not isinstance(provenance.mac, str)
            or not hmac.compare_digest(provenance.mac, _mac(key, expected))):
        raise C2Denied('provenance or message tampered')
    return True


class TestHubC2Runtime:
    """Adapter for trusted registry/lease lookups; both boundaries deny lookup errors.

    `is_test_uid` and `is_test_cid` must use an authoritative registry and must
    classify all dedicated Test Hub principals/connectors. Broker ACLs must keep
    untrusted publishers off `submit.sm.*` queues. The control plane owns leases.
    """

    def __init__(self, is_test_uid, is_test_cid, get_scope, get_lease, key):
        self.is_test_uid = is_test_uid
        self.is_test_cid = is_test_cid
        self.get_scope = get_scope
        self.get_lease = get_lease
        self.key = key

    def enqueue(self, authenticated_uid, routed_cid, content):
        try:
            protected = self.is_test_uid(authenticated_uid) or self.is_test_cid(routed_cid)
            if not protected:
                return None
            scope = self.get_scope(authenticated_uid)
            lease = self.get_lease(scope.uid) if scope is not None else None
            token = authorize_enqueue(content.properties['message-id'], authenticated_uid,
                                      routed_cid, content.body, scope, lease, self.key)
            return json.dumps(asdict(token), sort_keys=True, separators=(',', ':'))
        except Exception as exc:
            raise C2Denied('Test Hub enqueue authority unavailable or denied') from exc

    def egress(self, consumer_cid, message):
        try:
            headers = message.content.properties.get('headers') or {}
            raw_token = headers.get('testhub-c2')
            protected = self.is_test_cid(consumer_cid)
            if not protected and raw_token is None:
                return True
            if not isinstance(raw_token, str):
                raise C2Denied('missing signed Test Hub provenance')
            token = Provenance(**json.loads(raw_token))
            scope = self.get_scope(token.uid)
            lease = self.get_lease(token.uid)
            return authorize_egress(token, message.content.properties['message-id'],
                                    consumer_cid, message.content.body, scope, lease, self.key)
        except Exception as exc:
            raise C2Denied('Test Hub egress authority unavailable or denied') from exc

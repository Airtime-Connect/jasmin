# AIR-1353 — Jasmin Test Hub C2 boundary contract (draft)

This change adds an injectable guard at the shared `perspective_submit_sm` enqueue
path and at `SMPPClientSMListener.submit_sm_callback` immediately before
`sendDataRequest`. Both HTTP and SMPP submissions traverse the enqueue path.
The adapter checks the authenticated Jasmin UID and final routed CID, then signs
the message ID, PDU bytes hash, tenant, route, test, UID, CID, lease generation
and nonce. The consumer verifies that provenance and rechecks the current lease
before deserializing the AMQP PDU and again immediately before network send.
The first check keeps unauthenticated protected-queue content away from
`pickle.loads`; the second catches revocation or expiry during a queue or QoS
delay. Test Hub connector queues reject messages without a valid token when
the guard is installed. Store failure, revocation, queue delay beyond expiry and
connector failover deny. A lookup never renews the lease.

## Activation prerequisites

The daemon's PB portal now returns a distinct facade per login. When the guard
is installed, remote PB `submit_sm` calls using a protected Test Hub UID or CID
are denied before the shared manager is invoked. Other manager PB methods and
ordinary commercial submissions continue to delegate. This removes the PB
signing-oracle path for protected identities under complete registry lookup.
The facade does not turn the client-supplied UID into authenticated identity;
it excludes protected identities from that remote interface altogether.

The daemon now loads a trusted factory before it starts services and installs
its `TestHubC2Runtime` on the manager before PB listens or any connector can
consume. A protected deployment must set `JASMIN_TESTHUB_C2_REQUIRED=1` and
`JASMIN_TESTHUB_C2_FACTORY=jasmin.managers.testhub_c2_sovereign:build`. The function must return
a complete synchronous runtime with a key of at least 32 bytes. Missing,
invalid, or failing authority initialization stops startup; a factory supplied
without the required flag is rejected. The factory must be packaged and
reviewed as part of the trusted deployment image, and must obtain registry,
lease and key material from sovereign infrastructure. The stacked factory
candidate supplies code and synthetic tests but **does not prove the vault
helper, sovereign role, TLS endpoint, image packaging, or production
connection**. C2 remains NO-GO and no live Test Hub run
is permitted. A non-Test Hub instance can start with both bootstrap settings
absent; that path has no Test Hub guard and must never host dedicated routes.

The runtime bootstrap must supply authoritative `is_test_uid`, `is_test_cid`,
`get_scope` and `get_lease` functions with complete, fresh classifications.
`get_lease(uid)` assumes at most one active route/test lease per dedicated UID;
the provisioner must enforce that uniqueness and atomically revoke an old
generation before issuing a replacement.
Both registry classifiers must affirm a protected UID and its exact protected
CID at enqueue and egress. An incomplete classification on either side denies
the attempted Test Hub message; any non-boolean or failed classifier result
also denies. The registry must retain reserved identifiers
until every queued message and lease has expired.
Test Hub UIDs and CIDs must be dedicated and cannot share commercial routes.
The key must come from the sovereign vault, be at least 32 random bytes, and
must never be committed, logged, or sent over a client protocol. The control
plane alone creates and renews leases. The registry must bind each authenticated
UID to exactly one tenant and exact CID. No HTTP request value, SMPP TLV,
`source_connector`, or AMQP header can establish that binding.

The shared manager still receives `uid` as an argument; it does not independently
authenticate that UID. The PB facade blocks protected UID/CID submissions once
the guard is installed. Trusted in-process HTTP/SMPP components remain the only
allowed Test Hub submitters. The deployed PB service and its configuration must
be checked to prove this facade is active; this PR has no runtime proof.

Broker policy must deny direct untrusted publication to `messaging` /
`submit.sm.*` and access to the signing key. Otherwise a message stripped of
its provenance and sent to an ordinary commercial CID cannot be identified by
this guard. Ordinary commercial queues still deserialize their existing AMQP
payloads, so the broker publish ACL protects that separate trust boundary.
The deployed Jasmin image digest and broker ACLs must be verified
before activation. No such evidence is part of this PR.

## Evidence and remaining gate

`python3 -m unittest -q tests.managers.test_testhub_c2_bootstrap
tests.managers.test_testhub_c2 tests.managers.test_testhub_c2_hooks
tests.managers.test_testhub_c2_pre_deserialize` runs 40
bootstrap, contract, enqueue-hook and PB facade tests using a fake broker,
without SMSC or live SMS. The tests and imports
run on Python 3.12 with the fork's declared dependencies in a temporary venv.
`python3 -m twisted.trial tests.managers.test_testhub_c2_pb_portal` adds one
real loopback PB login/dispatch test with a fake manager; it verifies denial of
a protected remote submit and delegation of an ordinary method. It uses no
broker or SMSC. `git diff --check` covers edited modules. Full
Jasmin integration tests with a broker were not run here. A controlled end-to-end
egress test must show that a
Test Hub UID cannot reach a commercial CID through either HTTP or SMPP and
that a protected CID rejects direct broker messages and expired queued work.

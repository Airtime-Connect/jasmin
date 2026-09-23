# AIR-1353 — Jasmin Test Hub C2 boundary contract (draft)

This change adds an injectable guard at the shared `perspective_submit_sm` enqueue
path and at `SMPPClientSMListener.submit_sm_callback` immediately before
`sendDataRequest`. Both HTTP and SMPP submissions traverse the enqueue path.
The adapter checks the authenticated Jasmin UID and final routed CID, then signs
the message ID, PDU bytes hash, tenant, route, test, UID, CID, lease generation
and nonce. The consumer verifies that provenance and rechecks the current lease
at egress. Test Hub connector queues reject messages without a valid token when
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

This PR **does not install** `TestHubC2Runtime` at daemon bootstrap. Until a
trusted bootstrap calls `setTestHubC2Guard`, the new hooks are inert. This PR
does not make C2 operational or permit a live Test Hub run.

The runtime bootstrap must install the guard **before** the PB server begins
listening or any SMPP connector starts consuming. If the registry, lease store
or key is unavailable at startup, the protected service must not start; a
late setter call leaves a window where PB traffic is unrestricted. No secret
or production connection is loaded by this PR.

The runtime bootstrap must supply authoritative `is_test_uid`, `is_test_cid`,
`get_scope` and `get_lease` functions with complete, fresh classifications.
`get_lease(uid)` assumes at most one active route/test lease per dedicated UID;
the provisioner must enforce that uniqueness and atomically revoke an old
generation before issuing a replacement.
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
this guard. The deployed Jasmin image digest and broker ACLs must be verified
before activation. No such evidence is part of this PR.

## Evidence and remaining gate

`python3 -m unittest -v tests.managers.test_testhub_c2
tests.managers.test_testhub_c2_hooks` runs 26 contract, enqueue-hook and PB
facade tests using a fake broker, without SMSC or live SMS. The tests and imports
run on Python 3.12 with the fork's declared dependencies in a temporary venv.
`python3 -m twisted.trial tests.managers.test_testhub_c2_pb_portal` adds one
real loopback PB login/dispatch test with a fake manager; it verifies denial of
a protected remote submit and delegation of an ordinary method. It uses no
broker or SMSC. `python3 -m compileall -q` covers the edited modules. Full
Jasmin integration tests with a broker were not run here. A controlled end-to-end
egress test must show that a
Test Hub UID cannot reach a commercial CID through either HTTP or SMPP and
that a protected CID rejects direct broker messages and expired queued work.

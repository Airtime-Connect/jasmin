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

This PR **does not install** `TestHubC2Runtime` at daemon bootstrap. Until a
trusted bootstrap calls `setTestHubC2Guard`, the new hooks are inert. This PR
does not make C2 operational or permit a live Test Hub run.

The runtime bootstrap must supply authoritative `is_test_uid`, `is_test_cid`,
`get_scope` and `get_lease` functions with complete, fresh classifications.
Test Hub UIDs and CIDs must be dedicated and cannot share commercial routes.
The key must come from the sovereign vault, be at least 32 random bytes, and
must never be committed, logged, or sent over a client protocol. The control
plane alone creates and renews leases. The registry must bind each authenticated
UID to exactly one tenant and exact CID. No HTTP request value, SMPP TLV,
`source_connector`, or AMQP header can establish that binding.

Broker policy must deny direct untrusted publication to `messaging` /
`submit.sm.*` and access to the signing key. Otherwise a message stripped of
its provenance and sent to an ordinary commercial CID cannot be identified by
this guard. The deployed Jasmin image digest and broker ACLs must be verified
before activation. No such evidence is part of this PR.

## Evidence and remaining gate

`python3 -m unittest -v tests.managers.test_testhub_c2
tests.managers.test_testhub_c2_hooks` runs 16 contract tests and two enqueue
hook tests using a fake broker, without SMSC or live SMS. The tests and imports
run on Python 3.12 with the fork's declared dependencies in a temporary venv.
`python3 -m compileall -q` covers the edited modules. Full Jasmin integration
tests with a broker were not run here. A controlled end-to-end egress test must show that a
Test Hub UID cannot reach a commercial CID through either HTTP or SMPP and
that a protected CID rejects direct broker messages and expired queued work.

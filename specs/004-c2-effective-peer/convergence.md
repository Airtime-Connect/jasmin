# Convergence — 2026-09-30

The draft runtime now denies protected egress without a live observed peer and a literal-true in-process peer-authority decision. The listener authenticates AMQP bytes before pickle and uses the current protocol immediately before send. A disconnected protected item still follows the existing retry path. Synthetic same-CID config and peer swaps deny; commercial path remains unchanged.

Verified locally with Python 3.12 disposable virtual environment: `ci/run_testhub_c2.py` 73/73, zero skips/failures/errors; `python -m twisted.trial tests.managers.test_testhub_c2_pb_portal` 4/4; `git diff --check` exit 0. PG integration tests use a labelled synthetic peer callback and do not certify an upstream. No real network, production DB, vault or SMPP peer was exercised.

Remaining release gate: an approved authoritative CID→upstream mapping and effective peer verification policy, its sovereign adapter implementation, negative same-CID and unverified TLS/peer tests against the chosen transport, and target evidence. The current sovereign builder intentionally supplies no peer authority, so protected sends remain denied. This is a reviewable seam, not a C2 release approval.

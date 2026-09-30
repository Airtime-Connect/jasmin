# AIR-1353 — Effective peer gate for protected Test Hub egress

Status: draft implementation seam; release remains NO-GO.

## Problem

The C2 lease and HMAC authenticate a CID, but the current pre-send check does not observe the actual SMPP connection. A connector using the same CID with a different upstream can pass. `CtxFactory` also does not verify the TLS server peer.

## Requirements

1. A protected message must fail closed unless the egress guard receives the current connector configuration and an actual live transport with an effective peer observation.
2. The guard must require a trusted in-process peer-authority decision of the exact boolean `True` for the observed CID, configuration, transport and peer. Missing authority, observation, or an exception denies. A raw config host/port alone is insufficient.
3. The listener must authenticate protected AMQP bytes before deserialization, including while SMPP is disconnected. It must recheck message authority and the effective peer immediately before `sendDataRequest`, using the current protocol/transport. A temporary disconnect must retain the existing retry behavior instead of discarding a valid queued message.
4. Commercial traffic without C2 provenance keeps the existing path.
5. The sovereign factory must not supply a permissive peer authority until the CEO-approved CID→upstream identity and peer verification method are implemented and tested. This draft must not enable Test Hub or claim peer authentication.

## Acceptance

- Synthetic same-CID upstream swap fails with a restrictive test peer authority.
- Missing or unavailable peer authority and missing live transport deny protected egress.
- Pre-deserialization authenticates bytes without requiring transport; pre-send hands the current SMPP protocol to the guard.
- Existing C2 lease, broker and PB tests remain green. No production network or DB action.

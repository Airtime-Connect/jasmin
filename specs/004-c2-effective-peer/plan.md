# Plan

Base: Jasmin draft #11 `a55cb1689659c93dc4e2690a6eff4f150697f9e9`.

Add an optional `verify_peer` dependency to `TestHubC2Runtime`, default absent. Split pre-deserialization `authenticate_message` from pre-send `egress` so disconnected retry remains intact. At protected egress, obtain `protocol.transport.getPeer()` and pass the observed peer with the config and transport to the verifier; accept only literal `True`. Pass the current protocol at the pre-send call. Synthetic tests use a restrictive authority; the sovereign factory remains without one, so protected egress stays denied pending approved policy. Run focused C2 tests and exact-head CI. No TLS policy is inferred from config or user input.

# Plan

Base on Jasmin draft #10. Add one fail-closed CID classification method to `TestHubC2Runtime`. At the remote PB avatar, wrap the three CID-targeted mutators and deny add/load/stopall whenever a C2 guard is installed. Never deserialize a remote connector config in the facade. Keep trusted in-process manager calls unchanged. Extend the existing loopback PB fixture and a small unit suite; update the C2 contract and record the target operator gate. Use Spec Kit 1.0.10 only in this isolated worktree, stage scoped files, run focused tests and diff check, and open one stacked draft PR with one push.

Follow-up review of #11: `connector_config` returns a pickled `SMPPClientConfig` with password, and `persist` saves the full profile. Extend the same CID classifier to protected config reads, deny remote bulk persist while C2 is active, and prove commercial/legacy delegation in the loopback PB test. This is a separate correction task with one additional push to the existing draft #11.

# Tasks

- [x] T001 Consult sovereign RAG and AIR-1353; inspect Jasmin #12 and actual Supermicro image metadata.
- [x] T002 Add Docker context exclusions before retaining an image archive.
- [x] T003 Bind the CI image to exact PR head and AMD64, save/reload/hash the artifact and retain a receipt.
- [x] T004 Verify local AMD64 build, C2 import, excluded paths, archive hash and image ID round trip; lint the workflow.
- [ ] T005 Record exact-head official CI and artifact digest after the draft push.
- [x] T006 Reject shipped or disabled jCLI authentication before a C2 listener opens; prove the negative path with synthetic tests.
- [x] T007 Reject shipped/disabled authentication on enabled router, SMPP manager/server and interceptor PB management surfaces, including the entrypoint's separate interceptor process.
- [x] T008 Validate C2 authority in the Docker entrypoint before interceptor launch, with a fail-closed, redacted negative-path check.
- [x] T009 Reject blank/malformed and cross-surface shipped management credentials for all five C2 management checks before authority or listener startup; focused red 33 failures, green local 86/86 C2 tests.
- [x] T010 Reject effective AMQP `guest`/blank identity in C2 startup before authority or listeners; focused daemon test red before wiring, green local 88/88 and packaged AMD64 83/83 with separate default-broker and sovereign-authority negative paths.
- [x] T011 Reject an overprivileged sovereign C2 reader on a newly added `testhub` relation: disposable PostgreSQL 18.6 red grant test, then green table/column/sequence grant/revoke negatives and normal cross-repo C2 flow; local C2 88/88.
- [x] T012 Reject a C2 reader login with any PostgreSQL role membership and reject `current_user != session_user`: a disposable PostgreSQL 18.6 `NOINHERIT` membership had a working `SET ROLE` route-read path and passed old preflight (red); corrected preflight denies it and privileged-login role switching while retaining normal cross-repo C2 behavior.
- [x] T013 Run a self-contained PostgreSQL 18 reader-preflight fixture in the `c2-contract` workflow with exact grant/revoke and role-switch negatives, using a pinned disposable container on loopback. Local fixture and workflow lint passed; official exact-head CI receipt is recorded separately after push.
- [x] T014 Pin `c2-contract` checkout to the PR head and assert `git rev-parse HEAD` equals that SHA before installing dependencies or running PostgreSQL; the default PR merge-ref checkout did not bind previous contract jobs to exact source bytes.
- [x] T015 Wait for a successful connection through the ephemeral host port before running the PostgreSQL fixture. The first exact-head CI run failed because an in-container socket `pg_isready` returned true while host-port forwarding still closed the connection; the new readiness probe uses the same host/port/client path as the test.

Target image selection, sovereign transfer/deployment and C2 release remain open.

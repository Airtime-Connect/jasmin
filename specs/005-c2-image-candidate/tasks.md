# Tasks

- [x] T001 Consult sovereign RAG and AIR-1353; inspect Jasmin #12 and actual Supermicro image metadata.
- [x] T002 Add Docker context exclusions before retaining an image archive.
- [x] T003 Bind the CI image to exact PR head and AMD64, save/reload/hash the artifact and retain a receipt.
- [x] T004 Verify local AMD64 build, C2 import, excluded paths, archive hash and image ID round trip; lint the workflow.
- [ ] T005 Record exact-head official CI and artifact digest after the draft push.
- [x] T006 Reject shipped or disabled jCLI authentication before a C2 listener opens; prove the negative path with synthetic tests.
- [x] T007 Reject shipped/disabled authentication on enabled router, SMPP manager/server and interceptor PB management surfaces, including the entrypoint's separate interceptor process.
- [x] T008 Validate C2 authority in the Docker entrypoint before interceptor launch, with a fail-closed, redacted negative-path check.

Target image selection, sovereign transfer/deployment and C2 release remain open.

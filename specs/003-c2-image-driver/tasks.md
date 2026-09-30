# Tasks

- [x] Consult RAG, Linear AIR-1353 and current Jasmin #8.
- [x] Reproduce missing `psycopg` and x86 jemalloc preload in the baseline ARM64 image.
- [x] Add the C2 extra and architecture-neutral jemalloc preload to image variants.
- [x] Build corrected primary ARM64 image and verify imports with network disabled.
- [x] Confirm `psycopg[binary]` installation in a disposable Alpine ARM64 container.
- [x] Add a non-publishing primary image PR workflow.
- [ ] Verify exact-head official image and C2 checks.
- [ ] Verify target image digest, vault helper, reader role, broker ACL and live egress under CEO/Council gates.

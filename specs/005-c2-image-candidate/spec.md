# AIR-1353 — reviewable Jasmin C2 image candidate

Status: draft, stacked on Jasmin #12. This produces a CI artifact for review; it is not a registry publication, sovereign deployment or C2 release receipt.

## Requirement

The C2 image check must build from the exact PR head on `linux/amd64`, bind that source SHA to the image, verify the required C2 imports, and retain the exact image bytes with an independently checkable archive SHA-256. The build context must exclude Git metadata and project environment files before the image is archived. CI must reload the archive and verify that the image ID and revision label survive.

## Acceptance

- The PR checkout HEAD equals the head SHA recorded in the candidate receipt, rather than an implicit GitHub merge ref.
- The image architecture is `amd64`; the `org.opencontainers.image.revision` label equals the reviewed source SHA.
- C2 reader driver and allocator imports pass both before and after an offline `docker save`/`docker load` round trip.
- The packaged image runs the nonempty C2 contract suite with no skips, including management authentication startup rejection.
- The packaged image also rejects its actual shipped `jasmin.cfg` and `interceptor.cfg` in C2 mode without launching either management listener.
- The artifact contains `image.tar.gz` and `receipt.txt` with source SHA, platform, local image ID, archive SHA-256 and CI run link; the archive hash can be recomputed.
- Git metadata, `.specify` and project `.env` files are absent from the built image. No image is published or deployed.
- When C2 is required and jCLI is enabled, main-daemon startup rejects disabled jCLI authentication, the shipped admin username, or the shipped password digest before opening its PB or SMPP listeners. The target still needs an independently reviewed management-network ACL and configured credentials from the sovereign vault.
- When C2 is required, the main daemon also rejects disabled or shipped credentials for router PB and SMPP client PB (and SMPP server PB when enabled). If interceptor client is enabled, both the main daemon and the separately launched interceptor daemon reject disabled or shipped interceptor PB credentials before their own listeners open.
- In the Docker image, C2 or a configured C2 factory triggers a credential and authority preflight before the entrypoint launches its separate interceptor process. The main daemon must validate again before opening its listeners; a failed preflight must leave the child unstarted and must not print vault or DSN details.
- Every enabled C2 management surface rejects an empty or malformed MD5 digest, the digest of an empty password, blank or padded usernames, and any shipped Jasmin management username or password digest even if copied from another surface. The rejection occurs before the authority factory and any listener. This validates only the candidate configuration shape; approved target credentials and network ACL remain separate evidence.
- C2 startup rejects the effective AMQP broker `guest` username or password, or a blank/padded broker identity, before loading the sovereign authority or opening listeners. The packaged default broker configuration fails; a synthetic non-default identity must reach the separately tested authority failure. This does not prove target broker-user separation, topic ACL, vhost grants or network access.
- The sovereign PostgreSQL reader preflight rejects any table, column or sequence privilege on a non-allowlisted relation in the `testhub` schema, including a relation added after this draft's named deny checks. The three global C2 authority relations remain the only allowed Test Hub reads; they must remain non-writable. A disposable real PostgreSQL grant/revoke test must prove the refusal and normal recovery. Target role membership, RLS and grants still need independent attestation.
- The C2 reader login is the effective session role and has no PostgreSQL role memberships. A `NOINHERIT` membership with a later `SET ROLE` path, or a privileged login already switched to the reader role, fails preflight. Prove both against disposable PostgreSQL while preserving the normal C2 read flow. Target role/credential identity and RLS remain independent deployment gates.
- The C2 contract workflow reruns the reader privilege and role-switch negatives on a pinned disposable PostgreSQL 18 container for every PR head. It must prove the allowed reader still passes after each grant is revoked and delete the container on exit. This workflow does not claim the cross-repository lease/egress or target role gates.

The image ID and archive digest do not prove target installation, approved peer identity, broker ACL, vault/role provisioning or live C2 isolation. A target operator must independently verify the selected artifact and record the deployed digest under an approved change.

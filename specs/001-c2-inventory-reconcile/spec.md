# AIR-1353 — C2 inventory parser and startup reconciliation

Status: Draft. Base: Jasmin PR #6. This is a fail-closed startup hardening task; it does not establish target inventory completeness.

## Requirement

When the Test Hub C2 guard is required, the sovereign inventory must have unambiguous JSON and equal the full `testhub.c2_principals` UID/CID pair set visible to the dedicated reader at startup. The process must stop before listeners start if either condition fails.

## Acceptance

- Duplicate JSON property names at the document or pair level are rejected, as are invalid Unicode identifiers.
- An extra registry UID/CID pair absent from the vault inventory rejects startup; an extra or remapped inventory pair already rejects startup.
- The registry read is fresh, uses the SELECT-only C2 reader, and denies query, shape or cleanup failure.
- Existing dedicated and commercial behavior remains covered by the focused C2 contract suite.
- No target vault, production database, broker, SMS or deployment is touched.

This still requires an independently attested complete Jasmin UID/CID universe, audited provisioner, broker ACL and live isolation proof before C2 is ready.

# AIR-1353: cross-repository C2 authority gate

## Need

Jasmin #7 tests its PostgreSQL adapter with fakes, while api-gateway #455 tests migration 101 in disposable PostgreSQL. A local contract must run those exact components together to detect schema, privilege and lease-state mismatches before any target rollout.

## Requirements

1. Use api-gateway #455 migration 100/101 and fixture at its exact reviewed SHA.
2. Create only an isolated, socket-only PostgreSQL 18 database with synthetic roles and identities.
3. Execute Jasmin's real SELECT-only preflight, registry lookups, enqueue and egress guard with `psycopg` and actual PostgreSQL rows.
4. Prove missing lease and disabled connector deny; active protected path allows; route exit revokes the lease and denies both boundaries; reader outage denies.
5. Leave production credentials, networks, SMS and databases untouched.

## Acceptance

The shell harness exits zero with both live and outage PASS lines, and any unmet assertion exits nonzero. Documentation distinguishes this gate from live broker and egress proof.

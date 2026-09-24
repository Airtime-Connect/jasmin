# AIR-1353 — proposed sovereign PostgreSQL authority boundary

`PostgresC2Authority` replaces the four synthetic registry/lease callbacks of
`TestHubC2Runtime` with fresh parameterized PostgreSQL reads. Each call opens a
new connection and closes it; it never caches a lease or renews its TTL. A store
outage, malformed row, disabled connector, wrong tenant, revoked lease, or
expired lease denies Test Hub enqueue/egress. Reserved UID/CID classification
still includes disabled principals so the PB facade blocks those identifiers.

This is an **adapter draft**, not an enabled C2 deployment. The deployment
factory, SOPS+age key reader, database role/DSN, schema migration, broker ACL,
image provenance, and controlled live isolation test remain separate gates.
The factory must pass a callable that yields a DB-API connection using a
dedicated SELECT-only role; it must never accept a client supplied DSN. It may
then pass the four bound methods and vault key to `TestHubC2Runtime`.

## Required control-plane schema contract

The API/control-plane migration owner must create and verify these relations
before a Jasmin factory can be configured. This PR deliberately performs no
DDL and grants no database privileges.

| Relation | Required fields and constraint |
| --- | --- |
| `testhub.c2_principals` | `uid` text primary key; `cid` text unique; `tenant_id` UUID; `connector_id` UUID FK to `testhub.airtime_connectors`; `enabled` strict boolean. Reserve IDs even when disabled until all leases and queued messages expire. |
| `testhub.c2_leases` | `uid` primary key and FK to principal; `route_id`, `tenant_id`, `test_id` UUID; `cid` text; `generation` positive bigint; `not_before`, `expires_at` integer epoch seconds; `nonce` nonempty text; `revoked` boolean. Route/tenant must reference `testhub.routes`. A control-plane transaction must prove the exact route connector equals the principal connector, atomically revoke the old generation, then issue one new generation per UID with `expires_at - not_before <= 180`. |

`is_test_uid` and `is_test_cid` query all reserved rows. `get_scope` joins the
existing Airtime connector allowlist and returns `principal.enabled AND
connector.enabled`; `get_lease` reads the single current row by UID. The
provisioner must enforce one dedicated UID, one exact CID, one tenant, and one
active route/test lease. Its write role must be separate from the Jasmin
SELECT-only role; only the provisioner may extend expiry. Access to the
registry must be complete across tenants or these classifier lookups cannot
prove a negative result. Any RLS policy for the Jasmin role must account for
that complete reserved-ID view while keeping route/evidence tables protected.

The adapter still relies on Jasmin's local clock for expiry. Before activation,
measure clock skew against the DB host and make lease duration/skew limits a
release gate. PostgreSQL's relation/row constraints, migration integration,
multi-tenant transaction tests, vault factory, and broker ACL need independent
proof. The local 48-test run includes seven new adapter tests with a fake
DB-API store; it does **not** certify a PostgreSQL deployment or live SMS.

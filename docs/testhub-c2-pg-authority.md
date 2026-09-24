# AIR-1353 — proposed sovereign PostgreSQL authority boundary

`PostgresC2Authority` replaces the four synthetic registry/lease callbacks of
`TestHubC2Runtime` with fresh parameterized PostgreSQL reads. Each call opens a
new connection and closes it; it never caches a lease or renews its TTL. A store
outage, malformed row, disabled connector, wrong tenant, revoked lease, or
expired lease denies Test Hub enqueue/egress. Reserved UID/CID classification
still includes disabled principals so the PB facade blocks those identifiers.

This is a **factory candidate**, not an enabled C2 deployment. The packaged
`jasmin.managers.testhub_c2_sovereign:build` factory invokes the proposed
`/opt/vault/bin/read-secret.sh` helper for `testhub-c2-db-url` and
`testhub-c2-hmac-key-b64`, using `JASMIN_TESTHUB_C2_VAULT_DOMAIN`. The helper,
secret names, actual role/DSN, schema migration, broker ACL, image provenance,
and controlled live isolation test still require target verification.
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
connector.enabled AND connector.is_airtime`; `get_lease` reads the single current row by UID. The
provisioner must enforce one dedicated UID, one exact CID, one tenant, and one
active route/test lease. Its write role must be separate from the Jasmin
SELECT-only role; only the provisioner may extend expiry. Access to the
registry must be complete across tenants or these classifier lookups cannot
prove a negative result. Any RLS policy for the Jasmin role must account for
that complete reserved-ID view while keeping route/evidence tables protected.

The factory accepts only a PostgreSQL URL with a named reader and
`sslmode=verify-full`; libpq must validate the destination certificate against
a trusted CA and hostname. It sets `connect_timeout=3` seconds and PostgreSQL
`statement_timeout=3000` milliseconds and `default_transaction_read_only=on`,
then executes the reader role preflight before the daemon starts services. The target image
must contain compatible Python, `psycopg[binary]` from the optional
`testhub-c2` extra, the helper at the proposed path, and a trusted CA bundle.
Its exact digest, TLS chain, certificate rotation, helper behavior, role grants,
and network path are unverified. The reader must see all C2 principal and lease
rows across tenants, but no evidence rows, schema CREATE, lease issuance
function EXECUTE, or table mutation privileges. Migration 101 leaves the C2
tables without RLS; migration 100 gives allowlist SELECT via an open read policy.

The adapter still relies on Jasmin's local clock for expiry. Before activation,
measure clock skew against the DB host and make lease duration/skew limits a
release gate. PostgreSQL's relation/row constraints, migration integration,
multi-tenant transaction tests, vault factory, and broker ACL need independent
proof. The local 59-test focused run uses a fake DB-API store and mocked vault
helper; it does **not** certify a PostgreSQL deployment or live SMS.

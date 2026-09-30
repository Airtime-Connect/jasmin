# AIR-1353 C2 cross-repository PostgreSQL gate (draft)

This harness exercises Jasmin's real `PostgresC2Authority`, sovereign role preflight and `TestHubC2Runtime` against api-gateway migrations 100/101 from draft PR #455, exact head `ae7cb0e7e3f98d7d5685353bf3a1b2fbb541ec52`. It creates a fresh PostgreSQL 18 cluster on a unique Unix socket with `listen_addresses=''`, synthetic roles and the API's synthetic fixture. The cluster is deleted when the command exits. No vault secret, deployed database, SMS, AMQP broker or external network target is used.

From an isolated Jasmin worktree, with a separate isolated api-gateway #455 worktree:

```bash
PATH=/opt/homebrew/opt/postgresql@18/bin:$PATH \
ATC_C2_TEST_PYTHON=/private/tmp/atc-testhub-c2-pg-venv/bin/python3.12 \
bash scripts/testhub/run-c2-pg-crossrepo.sh /private/tmp/atc-testhub-route-lease-race
```

The Python 3.12 environment needs the declared `psycopg[binary]>=3.2,<4` C2 extra. The shell script rejects any API path outside `/private/tmp/atc-*` or at a different commit. PostgreSQL must provide `postgres`, `initdb`, `pg_ctl` and `psql` from the same 18 installation.

The live phase checks the reader's actual least-privilege preflight, including denial of extra Test Hub relation grants, a `NOINHERIT` membership that can `SET ROLE` into route access, and a privileged login that switches to the reader role. It also checks the complete three-pair registry, cross-tenant reserved-ID classification, PB denial, absence of a lease, disabled connector, lease issuance by a separate provisioner, protected enqueue/egress, commercial egress denial, and egress/enqueue denial after a tenant-scoped route update revokes the lease and increments its generation. The outage phase stops the local PostgreSQL server and checks fresh authority and protected enqueue deny. A failure exits nonzero; the script's trap stops and deletes its cluster.

This is cross-repository data/runtime contract evidence. It does not cover deployed Jasmin image wiring, independently complete live identity inventory, AMQP ACLs, an actual SMPP/HTTP submission, real connector network egress, target vault/roles or the CEO's production gate. Those remain AIR-1353/Council no-go items.

The `c2-contract` workflow also runs `scripts/testhub/run-c2-role-preflight-ci.sh` against a pinned PostgreSQL 18 container bound to an ephemeral loopback port. Its self-contained synthetic schema checks normal reader access, extra table/column/sequence grants, a `NOINHERIT` membership with a working `SET ROLE` route read, and a privileged login switched to the reader. The container is removed on exit. This CI gate covers role preflight only; the cross-repository migration/lease/egress flow above remains a separate local test and target role/RLS attestation remains open.

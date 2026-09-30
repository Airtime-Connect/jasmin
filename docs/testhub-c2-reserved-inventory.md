# Test Hub C2 reserved identifier inventory (draft)

When `JASMIN_TESTHUB_C2_REQUIRED=1`, the sovereign factory requires a third
vault-helper value named `testhub-c2-reserved-identifiers-json` in the same
explicit vault domain as the C2 DSN and HMAC key. Its JSON shape is:

```json
{"principals":[{"uid":"dedicated-jasmin-user","cid":"dedicated-jasmin-connector"}]}
```

The names above are examples, not provisioned identities. The inventory must
contain every dedicated active **and reserved** Jasmin UID/CID pair. It is
independent of `testhub.c2_principals` and must come from an audited inventory
of Jasmin identities and the control-plane reservation process. No prefix,
client field, or live message metadata can establish protected status.

Startup rejects a missing, empty, malformed, duplicate, or mismatched inventory.
Duplicate JSON property names and invalid Unicode identifiers fail parsing. The
dedicated reader retrieves all `testhub.c2_principals` UID/CID pairs in one
fresh query; that set must equal the vault inventory exactly. An extra registry
pair or an extra inventory pair stops startup. Each pair must also have a
matching joined scope row at startup, even if disabled. At
runtime, an inventoried UID or CID remains protected if its registry row is
removed: enqueue and egress then deny because scope/lease authority is absent.
Unlisted identifiers still use the fresh PostgreSQL classifier, so ordinary
commercial traffic is not classified by a broad prefix or a general Airtime
connector flag. A registry outage also denies commercial classification while
C2 is enabled; this is the existing fail-closed behavior.

The startup query checks registry/vault parity at one instant; it does not
establish completeness against Jasmin's active and reserved identity universe,
nor protect an unlisted new pair after its registry row is later deleted.
Before enabling C2, the
owner must reconcile all dedicated and reserved Jasmin IDs, registry rows and
the vault inventory on the target deployment, verify the effective reader role
and broker ACLs, and keep provisioning/rotation atomic. A newly reserved pair
requires an inventory update and guarded restart before it may be used. No
target vault, database, broker, Coolify runtime, or live SMS is exercised by
the synthetic tests.

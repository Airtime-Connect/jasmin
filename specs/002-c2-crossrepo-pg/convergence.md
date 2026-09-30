# Convergence

Base: Jasmin #7 `0f8abf287ef44d2a2205de974248782af95c1513`; API input: draft #455 `ae7cb0e7e3f98d7d5685353bf3a1b2fbb541ec52`. In a PostgreSQL 18 disposable socket-only cluster, both phases exited zero:

```text
PASS: real PG18 reader preflight, cross-tenant registry, PB gate, lease issuance, enqueue/egress, route-exit revocation
PASS: reader outage denies C2 authority and protected enqueue
```

During construction, the first run failed to import Jasmin because direct script execution lacked the repo on `PYTHONPATH`; the second failed because PostgreSQL `SET LOCAL` cannot take a bind parameter. The harness now supplies its own repo path and uses parameterized `set_config(..., true)` inside the route operator transaction. No target endpoint or credential was touched. This evidence joins the two draft implementations locally; it does not certify live AMQP, HTTP/SMPP or connector egress, target roles/vault/image, or production activation.

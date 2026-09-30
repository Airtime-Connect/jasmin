# Convergence

Jasmin #9 declares `messaging` as a topic exchange and publishes protected enqueue to `submit.sm.<cid>`. RabbitMQ's own documentation confirms routing-key topic authorization is an additional check and permits a topic when no topic rule is configured. A disposable pinned RabbitMQ 3.13 broker and AMQP 0-9-1 probe produced:

```text
PASS: unscoped topic route accepted (red); scoped sandbox allowed; protected topic and default-exchange publishes denied 403 (green)
```

The script's initial local runs exposed RabbitMQ startup races: invoking Erlang diagnostics before the cookie was owned by the server made startup fail, and a node ping could succeed before the Rabbit application started. The final harness waits for the cookie to be readable by the `rabbitmq` user and for `check_running`, then configures users and probes. The container was removed after the passing run. This is a synthetic ACL contract, not a target broker receipt, AMQP credential inventory, real Jasmin enqueue or live egress isolation proof.

A later read-only Supermicro audit at 2026-09-30 20:03 UTC found RabbitMQ 3.13.7 with only one `jasmin` administrator, full `.*` permissions on `/`, no topic rules and no active protected `submit.sm.*` binding. One connection mapped to the old Jasmin container; the HTTP adapter shared its Docker network but was not connected to AMQP in the snapshot. This narrows the next evidence: the owner must approve the effective principal/routing matrix and test it with an actual protected binding in staging before any target ACL or live isolation claim. The observation neither proves an exploit nor authorizes a broker mutation.

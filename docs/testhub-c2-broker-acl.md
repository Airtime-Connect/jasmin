# AIR-1353: C2 broker publish boundary (draft)

Jasmin declares `messaging` as a topic exchange and binds `submit.sm.<cid>` queues to matching routing keys. Its protected consumer checks signed C2 provenance before deserializing and again before send, but a broker publisher outside the manager can still try to inject into those queues. RabbitMQ's [access-control documentation](https://www.rabbitmq.com/docs/access-control) says a topic exchange publication checks both resource write permission and routing-key topic permission; if the user has no topic-permission entry, the default backend authorizes topic routing. The [rabbitmqctl reference](https://www.rabbitmq.com/docs/3.13/man/rabbitmqctl.8) defines `set_topic_permissions` for an exchange and user.

Run `scripts/testhub/run-c2-broker-acl.sh` with `ATC_C2_BROKER_PYTHON` pointing to a Python 3.12 environment with `pika==1.4.4`. It starts only a pinned RabbitMQ 3.13 image in a disposable container, publishes port 5672 on an ephemeral `127.0.0.1` port, configures a synthetic vhost and three synthetic users, then removes the container on exit. An ephemeral local Erlang cookie is generated for startup. No deployed broker, vault credential, SMS or external route is used.

The probe shows four distinct outcomes:

1. The synthetic internal user publishes to `submit.sm.synthetic-cid-a` and the matching queue receives it.
2. A user with resource write permission on `messaging` but **no topic rule** also reaches that queue. This is the red baseline.
3. A user with the same resource write permission and topic write allowlist `^sandbox\..*$` can publish `sandbox.ping`, but receives AMQP channel 403 for `submit.sm.synthetic-cid-a`.
4. That restricted user also receives 403 when trying to publish directly to the protected queue through the default exchange, because its resource write permission matches only `messaging`.

Before deployment, the broker owner must inventory every actual AMQP credential, virtual host, exchange, binding and publisher that can reach `submit.sm.*`. A shared credential with broad topic rights defeats separation; dedicated producer identities and their effective permissions need target receipts. The owner must prove the deployed broker denies an untrusted publisher's protected route while still allowing Jasmin's legitimate enqueue, and confirm the default-exchange path cannot bypass it. Those target ACL changes and any live SMS/egress test remain CEO/Council gates; this local fixture authorizes none of them.

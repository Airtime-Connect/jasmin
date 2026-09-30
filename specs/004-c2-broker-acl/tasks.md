# Tasks

- [x] Consult sovereign RAG and Linear AIR-1353 before work.
- [x] Inspect Jasmin's exchange and protected routing key.
- [x] Verify RabbitMQ topic-permission semantics in official documentation.
- [x] Reproduce unscoped publication and scoped 403 denial on local RabbitMQ.
- [x] Build a disposable, loopback-only repeatable harness and PR workflow.
- [x] Record target broker identity and ACL evidence still required.
- [ ] Verify exact-head official broker ACL check.
- [x] Record the 2026-09-30 read-only Supermicro broker baseline: RabbitMQ 3.13.7, one `jasmin` administrator with `.*` on `/`, zero topic rules, no active `submit.sm.*` binding, one Jasmin AMQP connection. This is inventory, not ACL acceptance.
- [ ] Ratify every effective publisher/vhost and protected-route policy, then prove the intended ACL on a staging broker with a real protected binding and negative default-exchange test.
- [ ] Prove target permissions, image, vault role and real connector egress under CEO/Council gates.

# AIR-1353: deny unauthorized AMQP publishes to protected routes

## Problem

Jasmin uses a RabbitMQ topic exchange named `messaging` and routing keys `submit.sm.<cid>`. A publisher with exchange write permission but no topic-specific rule can inject into a protected queue without calling Jasmin's enqueue manager. The C2 consumer has its own signature guard, but broker identity must also be constrained for a credible routing boundary.

## Requirements

1. Reproduce the actual topic-exchange and protected routing-key shape in a disposable local broker.
2. Show that resource write permission alone admits an unscoped publisher to the protected queue.
3. Show a synthetic publisher with an explicit topic allowlist can publish its allowed route but receives 403 for protected and default-exchange paths.
4. Add a non-publishing PR gate and document the distinct target identity/ACL evidence still required.
5. Do not access or alter a deployed broker, credential, queue or SMS route.

## Acceptance

The local harness prints the red/green PASS line and exits zero; an unexpected protected publish fails the job. The exact-head official broker ACL check passes. No claim of deployed ACL or egress isolation follows from this fixture.

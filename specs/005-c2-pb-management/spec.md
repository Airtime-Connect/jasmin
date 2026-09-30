# AIR-1353: protect connector management on the PB facade

## Problem

The C2 PB facade denies protected `submit_sm`, but delegates connector management. A remote PB caller can remove, stop or restart a reserved CID, while `connector_add`, `load` and `stopall` can replace or affect protected connectors without an auditable C2 control-plane decision. `connector_add` accepts pickle bytes, so inspecting its CID by unpickling before the guard would be unsafe.

## Requirements

1. With C2 active, remote PB remove/start/stop of a reserved CID must fail before manager mutation. A complete authoritative classifier must decide CID membership; lookup errors and non-boolean results deny.
2. With C2 active, remote PB add/load/stopall must fail before manager mutation because their affected CIDs cannot be safely bounded at the facade. Operator provisioning then needs a separate authenticated and audited path before release.
3. Commercial CID-targeted operations and ordinary commercial submission keep their existing behavior, and the facade keeps its legacy behavior when C2 is inactive.
4. A real loopback PB test must prove denied remote dispatch and allowed commercial delegation with no broker, SMSC, target connector or production change.

## Acceptance

The focused contract and loopback PB suites pass. C2 release remains NO-GO until the target operator-management path, actual connector identity, broker ACL, image, inventory, lease and egress gates are evidenced.

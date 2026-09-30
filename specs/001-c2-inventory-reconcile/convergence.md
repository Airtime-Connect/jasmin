# Convergence — AIR-1353 C2 startup inventory

The code now rejects duplicate JSON keys and invalid Unicode identifiers, reads every visible C2 registry UID/CID pair, and requires exact equality with the vault inventory before installing the runtime guard. The preexisting per-pair scope check remains. Two focused tests were red before implementation (four failing assertions); after implementation the full local C2 gate ran 67/67 with zero skips, failures and errors on Python 3.12. Diff check is clean.

This closes only the parser and startup registry/vault parity slice. It does not prove the source inventory is complete, that a future provisioner updates registry and vault atomically, that the target reader sees all rows, that broker ACLs and the deployed image enforce C2, or that live commercial egress is isolated. T013j and T013 remain open. No target secrets, database, SMS or deployment were used.

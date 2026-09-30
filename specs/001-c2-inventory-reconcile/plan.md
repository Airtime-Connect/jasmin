# Plan

1. Add failing synthetic cases for duplicate JSON keys, invalid Unicode and a registry-only pair.
2. Parse the inventory with duplicate-key rejection and validate identifier encoding.
3. Read every registry UID/CID pair with the dedicated reader and compare exact sets at startup, then preserve the existing per-pair scope check.
4. Run the focused C2 suite, check the diff and record remaining gate evidence.

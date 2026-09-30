# AIR-1353: make the Jasmin C2 reader importable in images

## Problem

The C2 factory requires the declared `psycopg` extra, while six Jasmin Dockerfiles install only the base package. ARM64 Debian images additionally preload jemalloc through an x86-specific absolute path. A C2-required service built from these files cannot pass startup even if its sovereign authorities are available.

## Requirements

1. Every Dockerfile variant that runs `jasmind` includes the declared C2 database driver.
2. Debian jemalloc preload resolves on ARM64 and AMD64.
3. A pull-request check builds the primary image without publishing and imports the C2 driver/factory in a network-disabled container.
4. C2 remains default off; no secret, target database, SMS or deployment is touched.

## Acceptance

An ARM64 image built before the fix fails the `psycopg` import; the corrected image passes both the import and jemalloc load. The official primary-image PR check passes on the exact head. Other production gates remain open.

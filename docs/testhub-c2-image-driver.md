# AIR-1353: C2 image dependency gate

The sovereign C2 factory imports `psycopg` when `JASMIN_TESTHUB_C2_REQUIRED=1`. The package declares that driver in the `testhub-c2` extra, but the six Jasmin Dockerfile variants previously ran `pip install .`. A baseline local `linux/arm64` build of `docker/Dockerfile` succeeded, then `docker run --network none --entrypoint python ... -c 'import psycopg'` exited 1 with `ModuleNotFoundError`. Its x86-only `LD_PRELOAD` path also produced a loader error on ARM64.

All Jasmin image variants now install `.[testhub-c2]`. The four Debian variants preload `libjemalloc.so.2` by soname, which the loader resolved in a local ARM64 container. The default C2 runtime flag remains off. The pull-request image workflow builds only the primary Dockerfile without pushing it and verifies that `psycopg`, the sovereign factory and jemalloc load in a network-disabled container.

Local primary-image evidence: baseline ARM64 image `sha256:9da7b993195576d63d53f4d6062aba8e36b5a7d639e668589ab8e17002fc7262` failed the import; corrected ARM64 image `sha256:533c8ad65439973328cb5a1cd3ef86c260319b2440c741c9ef1fb686a5f8d7c8` printed `C2 image import and allocator PASS`. A separate disposable `python:3.12-alpine3.19` ARM64 container installed and imported `psycopg[binary]` 3.3.6. The alternate complete image variants were not built in this task.

This removes a packaging obstacle; it does not prove a deployed image digest, vault helper mount, target PostgreSQL role, AMQP ACL, real SMPP/HTTP submission or connector egress. No image was pushed to a registry or deployed.

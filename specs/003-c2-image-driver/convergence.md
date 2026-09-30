# Convergence

Baseline `linux/arm64` primary image built from Jasmin #8, digest `sha256:9da7b993195576d63d53f4d6062aba8e36b5a7d639e668589ab8e17002fc7262`. A network-disabled `import psycopg` failed with `ModuleNotFoundError`, and the image logged that `/usr/lib/x86_64-linux-gnu/libjemalloc.so.2` could not be preloaded. With `LD_PRELOAD=libjemalloc.so.2`, the baseline container resolved jemalloc.

After image changes, the local primary ARM64 build produced `sha256:533c8ad65439973328cb5a1cd3ef86c260319b2440c741c9ef1fb686a5f8d7c8`. A network-disabled container imported `psycopg` and `jasmin.managers.testhub_c2_sovereign.build`, loaded jemalloc and printed `C2 image import and allocator PASS`. Disposable Alpine ARM64 Python 3.12 also installed and imported `psycopg[binary]` 3.3.6. These are local build receipts, not a deployed digest or C2 enablement proof. The primary Dockerfile's official PR workflow still needs its exact-head receipt.

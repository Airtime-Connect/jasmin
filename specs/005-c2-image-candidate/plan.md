# Plan

1. Exclude Git metadata, Spec Kit local state and project environment files from the Docker build context.
2. Check out the exact PR head in the C2 image workflow and label an explicit AMD64 build with that SHA.
3. Save a compressed Docker image archive, hash it, reload it, verify identity and C2 imports, then upload the bytes and receipt as a short-lived private CI artifact.
4. Validate locally with Docker, run workflow lint and Spec Kit prerequisites, then create one draft PR stacked on #12.
5. After review found shipped jCLI defaults, add a C2-only daemon startup check against disabled/default jCLI authentication and exercise its negative path without a broker, vault or network listener.
6. Audit the image entrypoint's separate interceptor process and all enabled main-daemon PB management listeners; extend the C2 preflight to reject disabled/shipped authentication before those processes listen.

This plan does not select a target, publish to a registry or authorize deployment.

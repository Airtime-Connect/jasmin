# AIR-1353 — reviewable Jasmin C2 image candidate

Status: draft, stacked on Jasmin #12. This produces a CI artifact for review; it is not a registry publication, sovereign deployment or C2 release receipt.

## Requirement

The C2 image check must build from the exact PR head on `linux/amd64`, bind that source SHA to the image, verify the required C2 imports, and retain the exact image bytes with an independently checkable archive SHA-256. The build context must exclude Git metadata and project environment files before the image is archived. CI must reload the archive and verify that the image ID and revision label survive.

## Acceptance

- The PR checkout HEAD equals the head SHA recorded in the candidate receipt, rather than an implicit GitHub merge ref.
- The image architecture is `amd64`; the `org.opencontainers.image.revision` label equals the reviewed source SHA.
- C2 reader driver and allocator imports pass both before and after an offline `docker save`/`docker load` round trip.
- The artifact contains `image.tar.gz` and `receipt.txt` with source SHA, platform, local image ID, archive SHA-256 and CI run link; the archive hash can be recomputed.
- Git metadata, `.specify` and project `.env` files are absent from the built image. No image is published or deployed.

The image ID and archive digest do not prove target installation, approved peer identity, broker ACL, vault/role provisioning or live C2 isolation. A target operator must independently verify the selected artifact and record the deployed digest under an approved change.

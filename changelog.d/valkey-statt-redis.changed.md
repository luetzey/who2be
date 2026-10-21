- The rate-limit store of the cloud edition now runs on Valkey 8 instead of
  Redis. Valkey is a BSD-3-licensed, protocol-compatible fork; the previous
  `redis:7-alpine` image was already Redis 7.4 under RSALv2/SSPLv1, and the
  Redis 8 line offers only RSALv2, SSPLv1 or AGPLv3, so the container was the
  last one in the stack outside an OSI-approved permissive licence. All three
  cloud overlays (repository root, `deploy/dokploy`, `deploy/hetzner/who2be`)
  pin `valkey/valkey:8-alpine` by digest, start `valkey-server` without
  persistence as before and check health with `valkey-cli`. The service name
  `redis`, the `redis://` storage URI and the `redis` Python client stay
  unchanged, so no environment file needs editing; the store holds only
  rate-limit windows, so switching images loses nothing worth migrating. A new
  test keeps every overlay on a digest-pinned Valkey image.

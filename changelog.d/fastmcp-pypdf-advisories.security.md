- Bumped `fastmcp` from 4.1.1 to 4.1.3 and `pypdf` from 6.21.1 to 6.21.2 in
  `uv.lock`, clearing five advisories the CI `audit` job started reporting on
  2026-10-23 (GHSA-7xgj-8392-5q4r and GHSA-vqqp-x5qm-5qp4 for fastmcp;
  CVE-2026-115572, CVE-2026-115585 and CVE-2026-115580 for pypdf). The resolver
  took fastmcp to 4.1.3 rather than 4.1.2 and pulled along `fastmcp-slim`
  4.1.3, `openapi-pydantic` 0.6.0 and a direct `certifi` dependency of the
  fastmcp server extra (already locked at 2026.10.19). The declared lower
  bounds in `apps/mcp/pyproject.toml` and `apps/api/pyproject.toml` are
  unchanged, and no advisory is ignored. pypdf is reachable from user input:
  the WorkArea ingest extracts text from uploaded PDFs in the API image.
- Bumped `undici` from 6.29.0 to 6.29.1 in `apps/web/package-lock.json`,
  clearing GHSA-4qv8-2p9j-2685 and GHSA-xjj6-f33q-929c reported by the OSV
  scan. undici is a dev-only transitive dependency (license gate tooling via
  `node-gyp`, range `^6.25.0`) and is not part of the shipped web bundle;
  `package.json` is unchanged and no other package moved.

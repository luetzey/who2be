- The `tools/list` payload budget test now measures what the server actually
  sends. It calls `tools/list` through an in-memory client, so the per-tool
  `title` and `_meta` fields that FastMCP 4 adds are counted. The old
  measurement only summed `name`, `description` and `inputSchema` and missed
  about 2.4 KB: the catalog measures 142,295 bytes instead of 136,764 against
  the 160,000-byte budget. A new red probe inflates `title` or `_meta` on a
  single tool and fails if the measurement does not see it.

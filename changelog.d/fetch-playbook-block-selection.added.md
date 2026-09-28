- `fetch_playbook` (MCP) can return a single section instead of the whole
  playbook. The two-step path is now the documented default: `format="outline"`
  lists the body's headings as anchors (`sections`), and
  `block_ids=[...]` then renders only the chosen sections — heading plus
  everything down to the next heading of the same level, nested subsections
  included. Anchors follow the same heading-only rule already used for
  resource block refs.

  The outline ships with every response, including sliced ones, so the anchor
  names are discoverable without fetching the full document first, and a client
  can fetch a second section later without re-inventorying.

  The full fetch (`format="full"`, still the default) is unchanged and remains
  the right choice for consumers that process the body structurally.

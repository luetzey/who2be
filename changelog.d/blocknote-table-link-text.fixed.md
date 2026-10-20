- Activating a resource that contains a table no longer fails with HTTP 500.
  BlockNote stores a table's `content` as a `tableContent` object rather than
  a list of inline elements, and every plain-text path (prompt renderer,
  passage index, MCP text view) assumed a list. Tables now render as a GFM
  Markdown table — first row as header, cells as single-line plain text with
  `|` escaped — identically in all three paths. Inline links no longer lose
  their text: `See [docs](https://x.de)` used to become `See`, it now reads
  `See docs (https://x.de)`. Block content of any other unexpected shape yields
  no text instead of an error.

- Groundwork for readable MCP read tools (ADR-0056): the plain-text
  serialisation of editor documents now lives in the shared models package, so
  the API and the MCP server use one implementation. The MCP server gains a
  Markdown view for each read tool that returns editor content (metadata
  header plus the content as readable text, no JSON escaping). No tool uses
  it yet; tool responses are unchanged in this release.

- The MCP server now runs on FastMCP 4.0.11 (previously 3.4.7), which also
  brings the underlying MCP SDK from 1.28 to 2.3. The upgrade goes straight to
  4.0.11 instead of the 4.0.10 that Dependabot proposed, because the newer
  patch release carries upstream security fixes in schema handling and
  transport protection. Tool names, inputs, the Markdown response form
  (ADR-0056), authentication and the HTTP transport behave as before.

  FastMCP 4 pulls in `httpx2`, and Starlette's test client types its responses
  against `httpx2` as soon as that package is installed. Six test modules had
  annotated those responses as `httpx.Response`; they now import the response
  type from the same source as the test client, only for type checking, so no
  test gains a runtime dependency. Because those modules now import `httpx2`
  directly, it is declared in the `dev` dependency group instead of arriving
  only transitively through FastMCP. Application code is unchanged.

- E2E-Test `apps/web/e2e/review-gate.spec.ts` belegt den Kernablauf „Agent
  configuration you review" bis zum Agenten: Persona anlegen, v1 einreichen,
  prüfen und veröffentlichen, dann v2 einreichen. Der Abruf läuft über den
  echten MCP-Dienst des Compose-Stacks (`get_persona`, `w2b_`-Token eines
  Konsum-Agenten).

  Der Test sichert zu, dass eine Version im Review nie beim Agenten ankommt:
  Solange v2 nur eingereicht ist, liefert MCP weiter v1, erst nach der
  Veröffentlichung v2. Außerdem sichert er zu, dass `draft → active` direkt
  gesperrt ist (UI bietet es nicht an, API antwortet mit 409
  `forbidden_transition`). Der neue Helfer `apps/web/e2e/helpers/mcp.ts`
  spricht MCP über Streamable-HTTP.

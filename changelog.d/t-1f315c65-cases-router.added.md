- REST-Endpunkte für Fälle (ADR-0053 6.5, Paket D2b) unter
  `/v1/workspaces/{workspace_id}`: `POST /cases` (melden),
  `GET /cases?agent_id&status&target` (neueste zuerst, Keyset-Seiten mit
  `cursor`/`limit` und `X-Next-Cursor`), `GET /cases/counts` (Anzahl je
  Status), `GET /cases/{case_id}` (Fall mit Verlauf, Zuordnungen und
  Schilderungen), `POST /cases/{case_id}/transition`,
  `PUT /cases/{case_id}/elements` (ersetzt die Zuordnung vollständig),
  `POST /cases/{case_id}/statement` und `DELETE /cases/{case_id}` (ab
  `editor`). Ein agent-gebundener Aufruf ohne geladene Tool-Policy darf
  Fälle nicht mehr einordnen oder zuordnen (403 `missing_capability`).

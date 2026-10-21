- Markdown-Schreibweg in der API nach ADR-0058 §6 (W1-P2). Ein Router für
  alle fünf Elementarten (`personas`, `playbooks`, `resources`,
  `system-prompts`, `external_tools`) unter `/v1/workspaces/{workspace_id}`:
  `GET …/{entity_type}/{id}/markdown?format=source` liefert die Quellfassung
  in Markdown-Normalform mit Überschriften-Ankern `[#id]`, Pill-Tokens und dem
  Konflikt-Token `base_rev` im Kopf; `…/versions/{v}/markdown` liefert einen
  Snapshot als Vorlage für eine Wiederherstellung. `POST …/{entity_type}/markdown`
  legt an (mit Entity-Kontingent, der System-Prompt wie im JSON-Weg ohne),
  `PUT …/{id}/markdown` schreibt den Vollstand, `PATCH …/{id}/markdown`
  ändert einen Abschnitt (Anker) oder ein ganzes Feld im offenen Draft.
  Beim externen Tool ist `usage_notes` das Markdown-Feld.

  Neue Fehlergründe: 409 `version_conflict` bei veraltetem `base_rev` (mit
  aktueller Version und aktuellem `base_rev`), 422 `anchor_unknown`,
  `anchor_duplicate`, `markdown_unsupported` und `block_not_representable`.
  Rechte, Tag-Scope, Schreib-Drossel und der Schutz verwalteter Inhalte gelten
  wie im JSON-Weg, auch beim System-Prompt. Die JSON-Antworten
  (`format=full`) bleiben bitgleich, unveränderte Felder werden bitgleich
  zurückgeschrieben. Keine Migration.

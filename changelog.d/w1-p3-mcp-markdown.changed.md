- MCP schreibt Inhalte nur noch als Markdown (ADR-0058, W1-P3, harter
  Schnitt). `create_*`/`update_*` für Persona, Playbook, Resource,
  System-Prompt und externes Tool nehmen die Markdown-Felder (`profile`,
  `body`, Modus-Felder, `usage_notes`) als Strings und laufen über die
  `/markdown`-Routen der API; `update_*` nimmt optional `base_rev`. Ein
  BlockNote-Block-Array scheitert an der Schema-Validierung, serialisiertes
  Editor-JSON in einem Markdown-String weist das Werkzeug mit Feldnamen ab,
  bevor die API gefragt wird. Die Antwort ist der neue Stand samt neuem
  `base_rev`.

  Neu: `edit_content(entity_type, entity_id, base_rev, op, anchor | field,
  markdown)` ändert einen Abschnitt (Überschriften-Anker) oder ein ganzes Feld
  als Draft; 409 `version_conflict` kommt als Fehler mit Hinweis, neu zu lesen.
  `get_persona`, `fetch_playbook`, `fetch_resource`, `get_system_prompt`,
  `get_external_tool` und `get_version` kennen `format="source"`: die
  Schreibvorlage mit Ankern, Platzhalter-Tokens und `base_rev` im Kopf.
  `format="full"` bleibt für Diagnose. Server-`instructions` und
  Lesefassungs-Hinweis verweisen auf `source`.

  Katalog-Payload (M1): vorher 100 Werkzeuge / 114.203 Bytes, nachher 101
  Werkzeuge / 104.777 Bytes; Builder-Start 115.807 → 106.509 Bytes.

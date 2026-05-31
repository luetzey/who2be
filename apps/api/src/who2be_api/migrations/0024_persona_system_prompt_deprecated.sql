-- Migration 0024 — persona.system_prompt deprecated
-- (Phase 3 Runde 3 Track 3 — Template ist der System-Prompt des Agenten).
--
-- Das Feld bleibt aus Backward-Compat-Gruenden in `persona_version.content`
-- (jsonb) erhalten. Mit diesem Track wird es aber nicht mehr in der Editor-
-- UI editiert; bestehende Personas mit Wert zeigen einen Read-Only-Hinweis.
--
-- Diese Migration ist rein deklarativ: das System-Prompt-Feld lebt in `jsonb`
-- (`persona_version.content -> 'system_prompt'`) und hat dort keinen SQL-
-- erzwingenden Default. Die Pydantic-Klasse `PersonaVersionContent`
-- defaultet `system_prompt` auf '' (siehe packages/models/persona.py),
-- wodurch neue Create-Calls ohne System-Prompt funktionieren. Wir nutzen
-- diese Migration als Anker fuer den Audit-Trail / kuenftige Drop-Migration.

COMMENT ON COLUMN persona_version.content IS
    'jsonb-Snapshot der Persona-Version. Das eingebettete Feld '
    '"system_prompt" ist seit Migration 0024 deprecated — das Template '
    'eines Agenten uebernimmt den System-Prompt. Bestehende Daten bleiben '
    'aus Backward-Compat-Gruenden erhalten.';

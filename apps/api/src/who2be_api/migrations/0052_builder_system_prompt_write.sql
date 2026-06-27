-- Migration 0052 — Builder erhaelt `system_prompt_write` (ADR-0040)
--
-- Neue Per-Agent-Capability `system_prompt_write`: erlaubt agent-gebundenen
-- Tokens, System-Prompt-Templates zu verfassen + zur Review einzureichen
-- (draft/review). Das Aktivieren (→active/→inactive) bleibt serverseitig hart
-- gesperrt — diese Capability schaltet es NICHT frei.
--
-- Das Feld lebt im JSONB `agent.tool_policy` (kein Schema-Migrationszwang,
-- ADR-0009); das Pydantic-Modell defaultet auf False. Bestands-Agenten erben
-- damit „aus". Nur den geseedeten Builder (verlinktes System-Prompt-Template mit
-- Slug 'agent-builder') auf True heben, damit er den vollen Agent-Erstellungs-
-- Workflow inkl. System-Prompt-Authoring fahren kann.
--
-- Idempotent: jsonb_set(create=true) setzt den Key deterministisch; ein erneuter
-- Lauf schreibt denselben Wert.

UPDATE agent a
SET tool_policy = jsonb_set(a.tool_policy, '{system_prompt_write}', 'true', true)
FROM system_prompt_template t
WHERE a.system_prompt_template_id = t.id
  AND t.slug = 'agent-builder';

-- Migration 0059 — Zielloses System-/MCP-Feedback (ADR-0038-Folge)
--
-- Neuer Feedback-Typ fuer Probleme an der Plattform selbst (technisch oder am
-- MCP), die an KEINEM Inhalts-Element haengen: entity_type='system',
-- entity_id=NULL, signal traegt die Kategorie (technical/mcp/performance/other).
-- Das fliesst in denselben Kurations-Posteingang (Triage/Delete) wie das
-- Inhalts-Feedback.
--
-- Schema-Anpassung: `entity_id` war NOT NULL (jedes Feedback hatte ein Ziel).
-- System-Feedback hat keines → NOT-NULL fallenlassen. `entity_type`/`signal`
-- haben keine DB-CHECKs (Enum-Validierung liegt in Pydantic), daher genuegt
-- die eine Spalten-Aenderung. usage_event bleibt unveraendert (System hat keine
-- Nutzungs-Telemetrie). Idempotent: DROP NOT NULL ist wiederholbar.

ALTER TABLE agent_feedback ALTER COLUMN entity_id DROP NOT NULL;

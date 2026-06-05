-- Migration 0042 — locale pro Version (Content-i18n, ADR-0027, Stream D2)
--
-- Persona/Playbook/Resource/System-Prompt-Template werden mehrsprachig: jede
-- Version traegt ein `locale`-Kuerzel, jede Sprache ist ein eigener Versions-
-- Track. Identitaets-Zeilen (persona/playbook/resource/system_prompt_template)
-- und alle Refs/FKs bleiben unangetastet — locale lebt ausschliesslich auf den
-- `*_version`-Tabellen (ADR-0027, Option B).
--
-- KEIN CHECK-Constraint auf `locale` (User-Entscheidung 2026-06-04): das
-- Sprach-Set bleibt DB-seitig offen, damit weitere Sprachen ohne Migration
-- moeglich sind. Validierung/Normalisierung passiert in der Anwendungs-Schicht
-- (Pydantic). Heute bietet die UI nur 'de'/'en' an.
--
-- Backward-Compat: `NOT NULL DEFAULT 'de'` fuellt bestehende Rows automatisch
-- mit 'de' ("Bestandsdaten = implizit de") — kein separater Backfill noetig.
--
-- Versions-Track pro Sprache: die alten `UNIQUE (entity_id, version)`-
-- Constraints werden durch `(entity_id, locale, version)` ersetzt, damit
-- DE v1 und EN v1 koexistieren koennen. Die Status-Invariante "max. 1 Draft /
-- 1 Review / 1 Active" (Partial-Unique-Indices aus 0011/0015/0022) gilt
-- fortan pro (entity, locale).
--
-- Idempotenz: ADD COLUMN IF NOT EXISTS, DROP ... IF EXISTS, CREATE INDEX
-- IF NOT EXISTS. Constraints werden ueber ihre deterministischen PG-Auto-Namen
-- (`<table>_<col>_<col>_key`) bzw. neue explizite Namen referenziert.

-- 1) locale-Spalte (offen, ohne CHECK; Default 'de' fuellt Bestand) -----------

ALTER TABLE persona_version
    ADD COLUMN IF NOT EXISTS locale text NOT NULL DEFAULT 'de';
ALTER TABLE playbook_version
    ADD COLUMN IF NOT EXISTS locale text NOT NULL DEFAULT 'de';
ALTER TABLE resource_version
    ADD COLUMN IF NOT EXISTS locale text NOT NULL DEFAULT 'de';
ALTER TABLE system_prompt_template_version
    ADD COLUMN IF NOT EXISTS locale text NOT NULL DEFAULT 'de';

-- 2) Versions-Track pro Sprache: (entity_id, version) -> (entity_id, locale, version)

ALTER TABLE persona_version
    DROP CONSTRAINT IF EXISTS persona_version_persona_id_version_key;
ALTER TABLE persona_version
    ADD CONSTRAINT persona_version_persona_id_locale_version_key
    UNIQUE (persona_id, locale, version);

ALTER TABLE playbook_version
    DROP CONSTRAINT IF EXISTS playbook_version_playbook_id_version_key;
ALTER TABLE playbook_version
    ADD CONSTRAINT playbook_version_playbook_id_locale_version_key
    UNIQUE (playbook_id, locale, version);

ALTER TABLE resource_version
    DROP CONSTRAINT IF EXISTS resource_version_resource_id_version_key;
ALTER TABLE resource_version
    ADD CONSTRAINT resource_version_resource_id_locale_version_key
    UNIQUE (resource_id, locale, version);

ALTER TABLE system_prompt_template_version
    DROP CONSTRAINT IF EXISTS system_prompt_template_version_template_id_version_key;
ALTER TABLE system_prompt_template_version
    ADD CONSTRAINT system_prompt_template_version_template_id_locale_version_key
    UNIQUE (template_id, locale, version);

-- 3) Status-Invariante pro (entity, locale): Partial-Unique-Indices erweitern

DROP INDEX IF EXISTS persona_version_active_uniq;
DROP INDEX IF EXISTS persona_version_draft_uniq;
DROP INDEX IF EXISTS persona_version_review_uniq;
CREATE UNIQUE INDEX IF NOT EXISTS persona_version_active_uniq
    ON persona_version (persona_id, locale) WHERE status = 'active';
CREATE UNIQUE INDEX IF NOT EXISTS persona_version_draft_uniq
    ON persona_version (persona_id, locale) WHERE status = 'draft';
CREATE UNIQUE INDEX IF NOT EXISTS persona_version_review_uniq
    ON persona_version (persona_id, locale) WHERE status = 'review';

DROP INDEX IF EXISTS playbook_version_active_uniq;
DROP INDEX IF EXISTS playbook_version_draft_uniq;
DROP INDEX IF EXISTS playbook_version_review_uniq;
CREATE UNIQUE INDEX IF NOT EXISTS playbook_version_active_uniq
    ON playbook_version (playbook_id, locale) WHERE status = 'active';
CREATE UNIQUE INDEX IF NOT EXISTS playbook_version_draft_uniq
    ON playbook_version (playbook_id, locale) WHERE status = 'draft';
CREATE UNIQUE INDEX IF NOT EXISTS playbook_version_review_uniq
    ON playbook_version (playbook_id, locale) WHERE status = 'review';

DROP INDEX IF EXISTS resource_version_active_uniq;
DROP INDEX IF EXISTS resource_version_draft_uniq;
DROP INDEX IF EXISTS resource_version_review_uniq;
CREATE UNIQUE INDEX IF NOT EXISTS resource_version_active_uniq
    ON resource_version (resource_id, locale) WHERE status = 'active';
CREATE UNIQUE INDEX IF NOT EXISTS resource_version_draft_uniq
    ON resource_version (resource_id, locale) WHERE status = 'draft';
CREATE UNIQUE INDEX IF NOT EXISTS resource_version_review_uniq
    ON resource_version (resource_id, locale) WHERE status = 'review';

DROP INDEX IF EXISTS system_prompt_template_version_active_uniq;
DROP INDEX IF EXISTS system_prompt_template_version_draft_uniq;
DROP INDEX IF EXISTS system_prompt_template_version_review_uniq;
CREATE UNIQUE INDEX IF NOT EXISTS system_prompt_template_version_active_uniq
    ON system_prompt_template_version (template_id, locale) WHERE status = 'active';
CREATE UNIQUE INDEX IF NOT EXISTS system_prompt_template_version_draft_uniq
    ON system_prompt_template_version (template_id, locale) WHERE status = 'draft';
CREATE UNIQUE INDEX IF NOT EXISTS system_prompt_template_version_review_uniq
    ON system_prompt_template_version (template_id, locale) WHERE status = 'review';

-- 4) Lese-Indizes fuer locale-gefilterte Current-/Active-Selects

CREATE INDEX IF NOT EXISTS persona_version_locale_idx
    ON persona_version (persona_id, locale, version DESC);
CREATE INDEX IF NOT EXISTS playbook_version_locale_idx
    ON playbook_version (playbook_id, locale, version DESC);
CREATE INDEX IF NOT EXISTS resource_version_locale_idx
    ON resource_version (resource_id, locale, version DESC);
CREATE INDEX IF NOT EXISTS system_prompt_template_version_locale_idx
    ON system_prompt_template_version (template_id, locale, version DESC);

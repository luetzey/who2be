-- Migration 0022 — system_prompt_template + system_prompt_template_version
-- (Phase 3 Runde 3 Track 3 — Agent + SystemPromptTemplate-Hierarchie)
--
-- Aufbau analog persona/persona_version (ADR-0004): die Identitaets-Zeile
-- `system_prompt_template` traegt Aktuell-Stand-Metadaten + current_version,
-- jeder Update schreibt einen unveraenderlichen Versions-Snapshot mit
-- status-Feld in `system_prompt_template_version`.
--
-- Mandantenschluessel ist `workspace_id` (kein owner_id-Schwenk wie bei
-- Persona/Playbook). `owner_id` bleibt als Audit-Spalte (created_by-Bruecke).
-- Slug ist innerhalb des Workspaces eindeutig — Default-Templates aus dem
-- Seed (Migration 0023b) referenzieren ihre Identitaet darueber, sodass
-- erneute Seed-Laeufe idempotent bleiben.

CREATE TABLE system_prompt_template (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id    uuid NOT NULL REFERENCES workspace (id) ON DELETE CASCADE,
    owner_id        uuid NOT NULL,
    name            text NOT NULL,
    slug            text NOT NULL,
    current_version int NOT NULL DEFAULT 1,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now(),
    UNIQUE (workspace_id, id),
    UNIQUE (workspace_id, slug)
);

CREATE INDEX system_prompt_template_workspace_id_idx
    ON system_prompt_template (workspace_id);

CREATE TABLE system_prompt_template_version (
    id          uuid PRIMARY KEY
                DEFAULT gen_random_uuid(),
    template_id uuid NOT NULL REFERENCES system_prompt_template (id)
                ON DELETE CASCADE,
    version     int NOT NULL,
    content     jsonb NOT NULL,
    status      text NOT NULL DEFAULT 'draft'
                CHECK (status IN ('draft', 'review', 'active', 'inactive')),
    created_by  uuid NOT NULL,
    created_at  timestamptz NOT NULL DEFAULT now(),
    UNIQUE (template_id, version)
);

-- DB-erzwungene Invariante "max. 1 Draft / 1 Review / 1 Active je Template"
-- (analog 0011 fuer persona/playbook und 0015 fuer resource).
CREATE UNIQUE INDEX system_prompt_template_version_active_uniq
    ON system_prompt_template_version (template_id) WHERE status = 'active';
CREATE UNIQUE INDEX system_prompt_template_version_draft_uniq
    ON system_prompt_template_version (template_id) WHERE status = 'draft';
CREATE UNIQUE INDEX system_prompt_template_version_review_uniq
    ON system_prompt_template_version (template_id) WHERE status = 'review';

-- status_history fuer Templates wird in derselben Tabelle gefuehrt wie fuer
-- persona/playbook/resource; die CHECK-Constraint wird hier erweitert.
ALTER TABLE status_history
    DROP CONSTRAINT IF EXISTS status_history_entity_type_check;
ALTER TABLE status_history
    ADD CONSTRAINT status_history_entity_type_check
    CHECK (entity_type IN ('persona', 'playbook', 'resource',
                           'system_prompt_template'));

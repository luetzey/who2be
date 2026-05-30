-- Migration 0023 — agent
-- (Phase 3 Runde 3 Track 3 — Agent + SystemPromptTemplate-Hierarchie)
--
-- Agents sind die Top-Level-Konfiguration: jeder Agent verweist auf genau
-- eine Persona (1:1) und genau einen SystemPromptTemplate (1:1). Templates
-- bleiben wiederverwendbar — derselbe Template kann in mehreren Agents
-- referenziert sein.
--
-- Bewusst KEINE Versionshistorie (Plan §"Agent-Versionierung — Nein"): Agent
-- ist Konfig-Datensatz, nicht Inhalt. Spaeter nachruestbar.
--
-- Tenancy: workspace_id NOT NULL, Composite-FKs auf persona/system_prompt_template
-- erzwingen DB-seitig, dass Persona + Template aus demselben Workspace stammen
-- wie der Agent. Damit ist Cross-Workspace-Referenzierung auch ohne
-- Service-Pruefung unmoeglich.

CREATE TABLE agent (
    id                          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id                uuid NOT NULL REFERENCES workspace (id)
                                ON DELETE CASCADE,
    owner_id                    uuid NOT NULL,
    name                        text NOT NULL,
    description                 text NOT NULL DEFAULT '',
    persona_id                  uuid NOT NULL,
    system_prompt_template_id   uuid NOT NULL,
    status                      text NOT NULL DEFAULT 'enabled'
                                CHECK (status IN ('enabled', 'disabled')),
    created_at                  timestamptz NOT NULL DEFAULT now(),
    updated_at                  timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (workspace_id, persona_id)
        REFERENCES persona (workspace_id, id) ON DELETE RESTRICT,
    FOREIGN KEY (workspace_id, system_prompt_template_id)
        REFERENCES system_prompt_template (workspace_id, id) ON DELETE RESTRICT
);

CREATE INDEX agent_workspace_id_idx ON agent (workspace_id);
CREATE INDEX agent_persona_id_idx ON agent (workspace_id, persona_id);
CREATE INDEX agent_template_id_idx
    ON agent (workspace_id, system_prompt_template_id);

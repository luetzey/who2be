-- Migration 0057 — Managed-Flag + Content-Versions-Stempel (Builder-Lock + Sync)
--
-- Zwei neue Spalten je Kern-Aggregat (persona/playbook/system_prompt_template/
-- agent):
--   * is_managed              — vom System verwaltet: User-Edits werden geblockt
--                               (403), zentrale Updates duerfen ersetzen.
--   * managed_content_version — welcher kanonische Content-Stand zuletzt
--                               eingespielt wurde (Start-Sync vergleicht gegen
--                               BUILDER_CONTENT_VERSION; 0 = unverwaltet).
--
-- Backfill: der geseedete Builder (Persona/Agent name='Builder',
-- Template slug='agent-builder', die vier an die Builder-Persona geknuepften
-- Playbooks) wird als managed markiert und auf Content-Version 1 gestempelt
-- (der aktuelle Stand nach 0055/0056). Idempotent: ADD COLUMN IF NOT EXISTS,
-- Backfill setzt nur noch-nicht-gesetzte Zeilen.

ALTER TABLE persona
    ADD COLUMN IF NOT EXISTS is_managed boolean NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS managed_content_version int NOT NULL DEFAULT 0;
ALTER TABLE playbook
    ADD COLUMN IF NOT EXISTS is_managed boolean NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS managed_content_version int NOT NULL DEFAULT 0;
-- Resource: der Builder seedet keine Resources, aber der gemeinsame
-- VersionedAggregate-SELECT liest `is_managed` auch hier — Spalte muss existieren.
ALTER TABLE resource
    ADD COLUMN IF NOT EXISTS is_managed boolean NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS managed_content_version int NOT NULL DEFAULT 0;
ALTER TABLE system_prompt_template
    ADD COLUMN IF NOT EXISTS is_managed boolean NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS managed_content_version int NOT NULL DEFAULT 0;
ALTER TABLE agent
    ADD COLUMN IF NOT EXISTS is_managed boolean NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS managed_content_version int NOT NULL DEFAULT 0;

-- Builder-Persona.
UPDATE persona
    SET is_managed = true, managed_content_version = 1
    WHERE name = 'Builder' AND is_managed = false;

-- Builder-Agent.
UPDATE agent
    SET is_managed = true, managed_content_version = 1
    WHERE name = 'Builder' AND is_managed = false;

-- agent-builder-Template.
UPDATE system_prompt_template
    SET is_managed = true, managed_content_version = 1
    WHERE slug = 'agent-builder' AND is_managed = false;

-- Die vier Builder-Playbooks: per persona_playbook an eine Persona 'Builder'
-- geknuepft UND einer der vier Builder-Namen (keine gleichnamigen Nutzer-PBs).
UPDATE playbook pb
    SET is_managed = true, managed_content_version = 1
    WHERE pb.is_managed = false
      AND pb.name = ANY (ARRAY[
        'Persona anlegen & pflegen',
        'Playbook anlegen & pflegen',
        'Agent anlegen & pflegen',
        'Konsistenz- & Drift-Check'
      ])
      AND EXISTS (
        SELECT 1 FROM persona_playbook pp
        JOIN persona per ON per.id = pp.persona_id
        WHERE pp.playbook_id = pb.id
          AND per.name = 'Builder'
          AND per.workspace_id = pb.workspace_id
      );

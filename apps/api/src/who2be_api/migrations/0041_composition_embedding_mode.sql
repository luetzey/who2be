-- Migration 0041 — embedding_mode auf resource_composition + persona_playbook
-- Plan: .claude/plan/2026-06-04_embedding-mode-resource-compose.md
--
-- Gleicher Embed-Modus wie 0040 (playbook_resource_link), nun fuer die
-- Resource->Resource-Komposition (`resource_composition`) und — als
-- Schema-Vorbereitung — fuer die Persona->Playbook-Relation (`persona_playbook`).
--   * 'lazy'   (DEFAULT) — Pointer-Referenz, NICHT inline vom MCP gesendet.
--   * 'inline' — das Ziel-Dokument wird fest mitgesendet.
--
-- BEWUSST BREAKING analog 0040: Bestandszeilen kippen ueber den Default auf
-- 'lazy'. Bei `resource_composition` lieferte der MCP die Kinder ohnehin nur
-- als Pointer-Tabelle aus — fuer diese Tabelle ist 'inline' damit neues,
-- additives Verhalten (siehe apps/mcp/server.py:fetch_resource).
--
-- Idempotent: ADD COLUMN/Constraint pruefen vorher per pg_catalog.

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
          FROM pg_attribute
         WHERE attrelid = 'resource_composition'::regclass
           AND attname = 'embedding_mode'
           AND NOT attisdropped
    ) THEN
        ALTER TABLE resource_composition
            ADD COLUMN embedding_mode text NOT NULL DEFAULT 'lazy';
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
          FROM pg_constraint
         WHERE conname = 'resource_composition_embedding_mode_check'
           AND conrelid = 'resource_composition'::regclass
    ) THEN
        ALTER TABLE resource_composition
            ADD CONSTRAINT resource_composition_embedding_mode_check
            CHECK (embedding_mode IN ('lazy', 'inline'));
    END IF;
END $$;

-- persona_playbook existiert seit Migration 0004 — Schema-Vorbereitung fuer
-- einen kuenftigen Persona->Playbook-Inline-Modus. Der MCP-Persona-Pfad nutzt
-- die Spalte noch nicht (Persona-Editor liegt ausserhalb dieses Tracks).
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_class WHERE relname = 'persona_playbook' AND relkind = 'r'
    ) AND NOT EXISTS (
        SELECT 1
          FROM pg_attribute
         WHERE attrelid = 'persona_playbook'::regclass
           AND attname = 'embedding_mode'
           AND NOT attisdropped
    ) THEN
        ALTER TABLE persona_playbook
            ADD COLUMN embedding_mode text NOT NULL DEFAULT 'lazy';
        ALTER TABLE persona_playbook
            ADD CONSTRAINT persona_playbook_embedding_mode_check
            CHECK (embedding_mode IN ('lazy', 'inline'));
    END IF;
END $$;

-- Migration 0040 — playbook_resource_link.embedding_mode (Embed-Modus)
-- Plan: .claude/plan/2026-06-04_embedding-mode-resource-compose.md
--
-- Ergaenzt jeden Playbook->Resource-Link um einen Einbettungs-Modus:
--   * 'lazy'   (DEFAULT) — der Link ist eine reine Referenz; der MCP-Server
--                sendet das Ziel NICHT inline mit, der Agent laedt es bei Bedarf
--                via `fetch_resource` nach. Reduziert den gesendeten Kontext.
--   * 'inline' — das Ziel-Dokument wird vom MCP fest mitgesendet (Alt-Verhalten
--                fuer `link_scope='resource'`-Links).
--
-- BEWUSST BREAKING: Bestandszeilen bekommen ueber den Spalten-Default 'lazy'.
-- Bisherige 'resource'-scope-Links wurden immer inline geliefert; nach dieser
-- Migration sind sie standardmaessig lazy, bis ein User sie auf 'inline' stellt.
--
-- Idempotenz: ADD COLUMN/Constraint pruefen vorher per pg_catalog (search-path-
-- aware, analog 0021).

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
          FROM pg_attribute
         WHERE attrelid = 'playbook_resource_link'::regclass
           AND attname = 'embedding_mode'
           AND NOT attisdropped
    ) THEN
        ALTER TABLE playbook_resource_link
            ADD COLUMN embedding_mode text NOT NULL DEFAULT 'lazy';
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
          FROM pg_constraint
         WHERE conname = 'playbook_resource_link_embedding_mode_check'
           AND conrelid = 'playbook_resource_link'::regclass
    ) THEN
        ALTER TABLE playbook_resource_link
            ADD CONSTRAINT playbook_resource_link_embedding_mode_check
            CHECK (embedding_mode IN ('lazy', 'inline'));
    END IF;
END $$;

-- Migration 0021 — playbook_resource_link.link_scope (Phase-3-Fixes, Track 4)
-- Plan: .claude/plan/2026-05-29-2011_phase-3-fixes-track-4-resource-link-scope.md
--
-- Bisher: ein Link verweist immer auf einen einzelnen Heading-Block einer
-- Resource (`block_id` ist PK-Bestandteil, ADR-0021, Migration 0016). Track 4
-- ergaenzt einen zweiten Modus: ein Playbook kann eine Resource auch als
-- Gesamtdokument referenzieren (`link_scope='resource'`, `block_id IS NULL`),
-- exakt einmal pro `(playbook_id, resource_id)`. Block-Links (`'block'`)
-- bleiben mehrfach erlaubt — eine Section pro Heading.
--
-- Backfill: Bestandszeilen bekommen `link_scope='block'` ueber den
-- Spalten-Default. Der alte Primaerschluessel laesst sich nicht erweitern,
-- ohne `block_id` nullable zu machen — wir loesen ihn auf und ersetzen ihn
-- durch zwei partielle UNIQUE-Indexe, einen je Scope.
--
-- Idempotenz: alle ALTER/CREATE-Statements pruefen vorher per
-- pg_catalog, ob die Zielzustaende bereits vorliegen.

DO $$
BEGIN
    -- pg_attribute + regclass statt information_schema.columns, weil letzteres
    -- nicht search-path-aware ist: in Tests, die das Schema isolieren
    -- (`SET search_path TO phase3_xxx`), wuerde der Check sonst die gleich
    -- benannte Spalte im `public`-Schema sehen und das ADD COLUMN
    -- ueberspringen.
    IF NOT EXISTS (
        SELECT 1
          FROM pg_attribute
         WHERE attrelid = 'playbook_resource_link'::regclass
           AND attname = 'link_scope'
           AND NOT attisdropped
    ) THEN
        ALTER TABLE playbook_resource_link
            ADD COLUMN link_scope text NOT NULL DEFAULT 'block';
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
          FROM pg_constraint
         WHERE conname = 'playbook_resource_link_scope_check'
           AND conrelid = 'playbook_resource_link'::regclass
    ) THEN
        ALTER TABLE playbook_resource_link
            ADD CONSTRAINT playbook_resource_link_scope_check
            CHECK (link_scope IN ('resource', 'block'));
    END IF;
END $$;

-- Primaerschluessel aufloesen (block_id muss nullable werden, damit der
-- 'resource'-Modus geht). Vorher pruefen, damit der Replay nicht in den
-- pg_constraint-Conflict laeuft.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
          FROM pg_constraint
         WHERE conname = 'playbook_resource_link_pkey'
           AND conrelid = 'playbook_resource_link'::regclass
    ) THEN
        ALTER TABLE playbook_resource_link
            DROP CONSTRAINT playbook_resource_link_pkey;
    END IF;
END $$;

ALTER TABLE playbook_resource_link
    ALTER COLUMN block_id DROP NOT NULL;

-- Pflicht-/Verbot-Kopplung: 'resource' -> block_id NULL; 'block' -> block_id gesetzt.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
          FROM pg_constraint
         WHERE conname = 'playbook_resource_link_scope_block_id_check'
           AND conrelid = 'playbook_resource_link'::regclass
    ) THEN
        ALTER TABLE playbook_resource_link
            ADD CONSTRAINT playbook_resource_link_scope_block_id_check
            CHECK (
                (link_scope = 'resource' AND block_id IS NULL)
                OR (link_scope = 'block' AND block_id IS NOT NULL)
            );
    END IF;
END $$;

-- Genau ein 'resource'-Link je (playbook, resource).
CREATE UNIQUE INDEX IF NOT EXISTS playbook_resource_link_resource_scope_uniq
    ON playbook_resource_link (playbook_id, resource_id)
    WHERE link_scope = 'resource';

-- Bisheriger PK ersetzt durch partiellen UNIQUE-Index fuer 'block'-Links.
CREATE UNIQUE INDEX IF NOT EXISTS playbook_resource_link_block_scope_uniq
    ON playbook_resource_link (playbook_id, resource_id, block_id)
    WHERE link_scope = 'block';

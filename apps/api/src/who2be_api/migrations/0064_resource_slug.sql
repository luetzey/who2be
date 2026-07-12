-- Migration 0064 — resource.slug (workspace-eindeutig) + Backfill
--
-- Resources bekommen — wie system_prompt_template (0022) — einen
-- workspace-eindeutigen Slug. Neue Rows liefert der Service (aus dem Namen
-- abgeleitet oder explizit); Bestandsrows werden hier deterministisch
-- gebackfillt, damit die anschliessende NOT-NULL- und UNIQUE-Constraint haelt.
--
-- Idempotent: ADD COLUMN IF NOT EXISTS, Backfill nur fuer slug IS NULL,
-- CREATE UNIQUE INDEX IF NOT EXISTS, SET NOT NULL ist bei bereits gefuellter
-- Spalte ein No-Op. Jede Migration laeuft in eigener Transaktion (Runner).

ALTER TABLE resource ADD COLUMN IF NOT EXISTS slug text;

-- Backfill: slugify(name) in SQL (lower + Nicht-Alphanumerik -> '-', getrimmt),
-- Fallback 'resource' fuer leere Ergebnisse. De-Duplizierung je Workspace ueber
-- ROW_NUMBER(): der erste Treffer behaelt den Basis-Slug, jeder weitere haengt
-- ein 8-stelliges id-Praefix an (garantiert eindeutig fuer die UNIQUE-Constraint).
UPDATE resource r
SET slug = s.final_slug
FROM (
    SELECT
        id,
        CASE
            WHEN rn = 1 THEN base
            ELSE base || '-' || substr(replace(id::text, '-', ''), 1, 8)
        END AS final_slug
    FROM (
        SELECT
            id,
            base,
            ROW_NUMBER() OVER (
                PARTITION BY workspace_id, base ORDER BY created_at, id
            ) AS rn
        FROM (
            SELECT
                id,
                workspace_id,
                created_at,
                COALESCE(
                    NULLIF(
                        trim(both '-' from lower(regexp_replace(name, '[^a-zA-Z0-9]+', '-', 'g'))),
                        ''
                    ),
                    'resource'
                ) AS base
            FROM resource
            WHERE slug IS NULL
        ) a
    ) b
) s
WHERE r.id = s.id;

ALTER TABLE resource ALTER COLUMN slug SET NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS resource_workspace_slug_uniq
    ON resource (workspace_id, slug);

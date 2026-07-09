-- Migration 0063 — Bestands-Trigger normalisieren (WP-D1)
--
-- Playbook-Trigger sind ein kanonisch kommagetrennter String. Bestand, der
-- mit ';' als Separator erfasst wurde, rendert in der UI als eine Riesen-Pill
-- und faellt im Discovery-Aggregat (`list_triggers`) als EIN Trigger zusammen.
-- Neue Writes normalisiert seit WP-D1 der Pydantic-Validator
-- (`PlaybookContent.triggers` → `normalize_triggers`): Split an ',' UND ';',
-- trim je Eintrag, Dedupe case-insensitiv (die erste Schreibweise gewinnt),
-- Join mit ', '. Diese Migration zieht den Bestand mit exakt derselben Logik
-- nach — die denormalisierte Spalte `playbook.triggers` UND das
-- `triggers`-Feld ALLER `playbook_version.content`-Snapshots, jeweils
-- IN-PLACE.
--
-- Rein syntaktische Normalisierung, keine inhaltliche Aenderung: es entsteht
-- KEINE neue Version, `updated_at` wird bewusst nicht angefasst. NULL bleibt
-- NULL; ein String ohne verwertbare Eintraege (leer/nur Separatoren) wird zum
-- Leerstring (non-NULL bleibt non-NULL — Spiegel des Modell-Validators).
-- Idempotent: der IS-DISTINCT-FROM-Guard laesst den zweiten Lauf als
-- vollstaendigen No-op durchlaufen.

-- 1. Denormalisierte Spalte `playbook.triggers` -------------------------------
DO $$
DECLARE
    r record;
    norm text;
BEGIN
    FOR r IN SELECT id, triggers FROM playbook WHERE triggers IS NOT NULL LOOP
        SELECT coalesce(string_agg(s.entry, ', ' ORDER BY s.ord), '') INTO norm
        FROM (
            SELECT DISTINCT ON (lower(t.entry)) t.entry, t.ord
            FROM (
                SELECT trim(u.raw) AS entry, u.ord
                FROM unnest(regexp_split_to_array(r.triggers, '[,;]'))
                     WITH ORDINALITY AS u(raw, ord)
            ) t
            WHERE t.entry <> ''
            ORDER BY lower(t.entry), t.ord
        ) s;
        IF norm IS DISTINCT FROM r.triggers THEN
            UPDATE playbook SET triggers = norm WHERE id = r.id;
        END IF;
    END LOOP;
END
$$;

-- 2. Versions-Snapshots: `playbook_version.content -> 'triggers'` ------------
-- Alle Versionen (nicht nur die aktive): die Snapshots bleiben inhaltlich
-- unveraendert, nur die Trigger-Syntax wird vereinheitlicht — sonst zeigt
-- jeder Versions-Diff dauerhaft Trigger-Rauschen gegen die neue Kanonik.
DO $$
DECLARE
    r record;
    norm text;
BEGIN
    FOR r IN
        SELECT id, content ->> 'triggers' AS triggers
        FROM playbook_version
        WHERE content ->> 'triggers' IS NOT NULL
    LOOP
        SELECT coalesce(string_agg(s.entry, ', ' ORDER BY s.ord), '') INTO norm
        FROM (
            SELECT DISTINCT ON (lower(t.entry)) t.entry, t.ord
            FROM (
                SELECT trim(u.raw) AS entry, u.ord
                FROM unnest(regexp_split_to_array(r.triggers, '[,;]'))
                     WITH ORDINALITY AS u(raw, ord)
            ) t
            WHERE t.entry <> ''
            ORDER BY lower(t.entry), t.ord
        ) s;
        IF norm IS DISTINCT FROM r.triggers THEN
            UPDATE playbook_version
            SET content = jsonb_set(content, '{triggers}', to_jsonb(norm))
            WHERE id = r.id;
        END IF;
    END LOOP;
END
$$;

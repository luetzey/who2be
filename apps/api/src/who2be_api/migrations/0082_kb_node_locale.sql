-- Migration 0082 — `kb_node` bekommt eine Sprache (Befund B, 2026-08-16)
--
-- 0077 indiziert `kb_node.search` mit `to_tsvector('simple', content)` und
-- begruendet das mit „Aussagen sind kurz und ggf. gemischtsprachig". Die
-- Begruendung bleibt dort stehen (dated Dokumente werden nicht rueckwirkend
-- umgeschrieben) — hier wird die Entscheidung revidiert, weil ihr Preis im
-- Betrieb sichtbar wurde:
--
-- `'simple'` kennt kein Stemming. Eine Aussage ueber den „Fehlercode" ist
-- damit fuer eine Suche nach „Fehlercodes" unsichtbar — waehrend
-- `search_workarea` denselben Text findet, weil `wa_chunk` (0076) ueber eine
-- `locale`-Spalte auf 'german'/'english' abbildet. Fuer einen Agenten ist
-- dieser Unterschied nicht lesbar: kein Treffer sieht aus wie kein Wissen.
--
-- Die Annahme „gemischtsprachig" trifft den Regelfall nicht:
-- `workspace.content_locale` (0069, Default 'de') sagt bereits, in welcher
-- Sprache ein Workspace schreibt — dieselbe Quelle, aus der Persona,
-- Playbook, Resource und Artifact ihre Sprache beziehen.
--
-- Abbildung und Fallback sind 1:1 von 0076 uebernommen: unbekannte Sprachen
-- landen auf 'simple' (die DB-Schicht bleibt fuer Sprachen offen, 0069 setzt
-- bewusst KEIN CHECK).

-- 1) Sprach-Spalte + Backfill aus dem Workspace.
ALTER TABLE kb_node ADD COLUMN IF NOT EXISTS locale text NOT NULL DEFAULT 'de';

UPDATE kb_node n
   SET locale = w.content_locale
  FROM workspace w
 WHERE w.id = n.workspace_id
   AND n.locale IS DISTINCT FROM w.content_locale;

-- 2) Generierte Spalte ersetzen. Postgres kann den Ausdruck einer Generated
--    Column nicht aendern — also DROP + ADD. Der Neuaufbau der Spalte IST der
--    Reindex (kein separater Backfill-Lauf); der GIN-Index faellt mit der
--    Spalte und wird darunter neu angelegt.
ALTER TABLE kb_node DROP COLUMN IF EXISTS search;

ALTER TABLE kb_node ADD COLUMN search tsvector GENERATED ALWAYS AS (
    to_tsvector(
        CASE split_part(locale, '-', 1)
            WHEN 'de' THEN 'german'::regconfig
            WHEN 'en' THEN 'english'::regconfig
            ELSE 'simple'::regconfig
        END,
        content
    )
) STORED;

CREATE INDEX IF NOT EXISTS kb_node_search_idx
    ON kb_node USING gin (search);

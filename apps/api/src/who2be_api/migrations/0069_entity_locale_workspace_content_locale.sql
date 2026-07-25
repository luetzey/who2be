-- Migration 0069 — Entity-locale + Workspace-Content-Sprache ("Ein Element,
-- eine Sprache", ADR-0045 / Plan `.claude/plan/2026-07-24-1900_sprache-
-- vertiefen-ein-element-eine-sprache.md`, WP2)
--
-- Locale wandert von den `*_version`-Tabellen (ADR-0027/0042: ein Track pro
-- Sprache) auf die Identitaets-Zeile (persona/playbook/resource/
-- external_tool/system_prompt_template): `locale` ist fortan ein einzelnes
-- Attribut des Elements, nicht mehr eine Achse mit parallelen Versions-Tracks.
-- `*_version.locale` bleibt als Historien-Spalte bestehen (kein Schema-Drop
-- -> billiger Rollback; Writes uebernehmen kuenftig die Entity-Sprache,
-- WP3/nicht Teil dieser Migration).
--
-- KEIN CHECK-Constraint auf `locale`/`content_locale` (Fortfuehrung der
-- 0042-Entscheidung): das Sprach-Set bleibt DB-seitig offen, Validierung
-- passiert in der Anwendungs-Schicht (Pydantic, `SUPPORTED_LOCALES`).
--
-- Reihenfolge (bewusst, siehe Kommentare pro Block):
--   1) Spalten anlegen (workspace.content_locale, 5x entity.locale) — Default
--      'de' fuellt Bestand automatisch (Backward-Compat wie 0042).
--   2) Backfill entity.locale aus der aktiven Version, sonst aus der Version
--      mit der hoechsten Versionsnummer.
--   3) Legacy-Multi-Track-Konsolidierung: Versionen in einer anderen Sprache
--      als die (nun gesetzte) Entity-Sprache werden von draft/review/active
--      auf 'inactive' gesetzt — VOR dem Index-Rueckbau in Schritt 4, weil die
--      neuen per-Entity-Partial-Unique-Indices sonst an Bestandsdaten mit z.B.
--      einer aktiven DE- UND einer aktiven EN-Version scheitern wuerden.
--      Historie bleibt vollstaendig erhalten (Status-Wechsel, keine Loeschung).
--   4) Partial-Unique-Indices (active/draft/review) von `(entity_id, locale)`
--      (0042/0065) zurueck auf `(entity_id)` — erzwingt wieder "max. 1
--      Draft/Review/Active je Element" unabhaengig von der Sprache.
--   5) `UNIQUE (entity_id, locale, version)` aus 0042/0065 wird bewusst NICHT
--      auf `(entity_id, version)` zurueckgebaut (Abweichung vom Plan-Entwurf,
--      s. Kommentar unten) — sonst koennten Legacy-Rows mit z.B. DE-v1 UND
--      EN-v1 unter derselben Entity nicht mehr koexistieren.
--   6) Zusaetzliche Lese-Indices `(entity_id, version DESC)` fuer die
--      kuenftig locale-agnostischen Reads (WP3) — die bestehenden
--      `*_version_locale_idx (entity_id, locale, version DESC)` aus 0042/0065
--      bleiben (sie decken `(entity_id, version DESC)` nicht ab, weil
--      `locale` zwischen den beiden Spalten sitzt).
--
-- Idempotenz: ADD COLUMN IF NOT EXISTS, DROP INDEX IF EXISTS + CREATE INDEX
-- IF NOT EXISTS (0042-Muster), Backfill-/Konsolidierungs-UPDATEs sind
-- idempotent (zweiter Lauf findet keine abweichenden Rows mehr).

-- 1a) Workspace-Content-Sprache -----------------------------------------

ALTER TABLE workspace
    ADD COLUMN IF NOT EXISTS content_locale text NOT NULL DEFAULT 'de';

-- 1b) Entity-locale auf den 5 Identitaets-Tabellen ------------------------

ALTER TABLE persona
    ADD COLUMN IF NOT EXISTS locale text NOT NULL DEFAULT 'de';
ALTER TABLE playbook
    ADD COLUMN IF NOT EXISTS locale text NOT NULL DEFAULT 'de';
ALTER TABLE resource
    ADD COLUMN IF NOT EXISTS locale text NOT NULL DEFAULT 'de';
ALTER TABLE external_tool
    ADD COLUMN IF NOT EXISTS locale text NOT NULL DEFAULT 'de';
ALTER TABLE system_prompt_template
    ADD COLUMN IF NOT EXISTS locale text NOT NULL DEFAULT 'de';

-- 2) Backfill: entity.locale = locale der aktiven Version, sonst der Version
--    mit der hoechsten Versionsnummer. Beide Subqueries sind je auf genau
--    eine Zeile begrenzt (ORDER BY version DESC LIMIT 1) — vor Schritt 4
--    kann es wegen der noch per-(entity, locale) geltenden 0042/0065-Partial-
--    Unique-Indices mehr als eine aktive Version pro Entity geben (je eine
--    pro Sprache); die hoechste Versionsnummer ist der deterministische
--    Tie-Breaker. COALESCE faellt auf den Spalten-Default zurueck, falls eine
--    Entity (theoretisch) keine Versionen hat.

UPDATE persona p
   SET locale = COALESCE(
       (SELECT pv.locale FROM persona_version pv
         WHERE pv.persona_id = p.id AND pv.status = 'active'
         ORDER BY pv.version DESC LIMIT 1),
       (SELECT pv.locale FROM persona_version pv
         WHERE pv.persona_id = p.id
         ORDER BY pv.version DESC LIMIT 1),
       p.locale
   );

UPDATE playbook p
   SET locale = COALESCE(
       (SELECT pv.locale FROM playbook_version pv
         WHERE pv.playbook_id = p.id AND pv.status = 'active'
         ORDER BY pv.version DESC LIMIT 1),
       (SELECT pv.locale FROM playbook_version pv
         WHERE pv.playbook_id = p.id
         ORDER BY pv.version DESC LIMIT 1),
       p.locale
   );

UPDATE resource r
   SET locale = COALESCE(
       (SELECT rv.locale FROM resource_version rv
         WHERE rv.resource_id = r.id AND rv.status = 'active'
         ORDER BY rv.version DESC LIMIT 1),
       (SELECT rv.locale FROM resource_version rv
         WHERE rv.resource_id = r.id
         ORDER BY rv.version DESC LIMIT 1),
       r.locale
   );

UPDATE external_tool t
   SET locale = COALESCE(
       (SELECT tv.locale FROM external_tool_version tv
         WHERE tv.external_tool_id = t.id AND tv.status = 'active'
         ORDER BY tv.version DESC LIMIT 1),
       (SELECT tv.locale FROM external_tool_version tv
         WHERE tv.external_tool_id = t.id
         ORDER BY tv.version DESC LIMIT 1),
       t.locale
   );

UPDATE system_prompt_template s
   SET locale = COALESCE(
       (SELECT sv.locale FROM system_prompt_template_version sv
         WHERE sv.template_id = s.id AND sv.status = 'active'
         ORDER BY sv.version DESC LIMIT 1),
       (SELECT sv.locale FROM system_prompt_template_version sv
         WHERE sv.template_id = s.id
         ORDER BY sv.version DESC LIMIT 1),
       s.locale
   );

-- 3) Legacy-Multi-Track-Konsolidierung (defensiv, vor dem Index-Rueckbau):
--    jede Version mit abweichender Sprache und Status draft/review/active
--    wird auf 'inactive' konsolidiert. Konsolidierung auf "ein Element = eine
--    Sprache" — die Historie bleibt vollstaendig erhalten (nur Status-
--    Wechsel, keine Loeschung); real betrifft dies praktisch keine Rows
--    (heutiger Bestand ist durchgehend 'de'), ist aber Defensive fuer per
--    Multi-Checkbox (ADR-0027) angelegte EN-Tracks.

UPDATE persona_version pv
   SET status = 'inactive'
  FROM persona p
 WHERE pv.persona_id = p.id
   AND pv.locale <> p.locale
   AND pv.status IN ('draft', 'review', 'active');

UPDATE playbook_version pv
   SET status = 'inactive'
  FROM playbook p
 WHERE pv.playbook_id = p.id
   AND pv.locale <> p.locale
   AND pv.status IN ('draft', 'review', 'active');

UPDATE resource_version rv
   SET status = 'inactive'
  FROM resource r
 WHERE rv.resource_id = r.id
   AND rv.locale <> r.locale
   AND rv.status IN ('draft', 'review', 'active');

UPDATE external_tool_version tv
   SET status = 'inactive'
  FROM external_tool t
 WHERE tv.external_tool_id = t.id
   AND tv.locale <> t.locale
   AND tv.status IN ('draft', 'review', 'active');

UPDATE system_prompt_template_version sv
   SET status = 'inactive'
  FROM system_prompt_template s
 WHERE sv.template_id = s.id
   AND sv.locale <> s.locale
   AND sv.status IN ('draft', 'review', 'active');

-- 4) Partial-Unique-Indices zurueck auf per-Entity (statt per (entity, locale))

DROP INDEX IF EXISTS persona_version_active_uniq;
DROP INDEX IF EXISTS persona_version_draft_uniq;
DROP INDEX IF EXISTS persona_version_review_uniq;
CREATE UNIQUE INDEX IF NOT EXISTS persona_version_active_uniq
    ON persona_version (persona_id) WHERE status = 'active';
CREATE UNIQUE INDEX IF NOT EXISTS persona_version_draft_uniq
    ON persona_version (persona_id) WHERE status = 'draft';
CREATE UNIQUE INDEX IF NOT EXISTS persona_version_review_uniq
    ON persona_version (persona_id) WHERE status = 'review';

DROP INDEX IF EXISTS playbook_version_active_uniq;
DROP INDEX IF EXISTS playbook_version_draft_uniq;
DROP INDEX IF EXISTS playbook_version_review_uniq;
CREATE UNIQUE INDEX IF NOT EXISTS playbook_version_active_uniq
    ON playbook_version (playbook_id) WHERE status = 'active';
CREATE UNIQUE INDEX IF NOT EXISTS playbook_version_draft_uniq
    ON playbook_version (playbook_id) WHERE status = 'draft';
CREATE UNIQUE INDEX IF NOT EXISTS playbook_version_review_uniq
    ON playbook_version (playbook_id) WHERE status = 'review';

DROP INDEX IF EXISTS resource_version_active_uniq;
DROP INDEX IF EXISTS resource_version_draft_uniq;
DROP INDEX IF EXISTS resource_version_review_uniq;
CREATE UNIQUE INDEX IF NOT EXISTS resource_version_active_uniq
    ON resource_version (resource_id) WHERE status = 'active';
CREATE UNIQUE INDEX IF NOT EXISTS resource_version_draft_uniq
    ON resource_version (resource_id) WHERE status = 'draft';
CREATE UNIQUE INDEX IF NOT EXISTS resource_version_review_uniq
    ON resource_version (resource_id) WHERE status = 'review';

DROP INDEX IF EXISTS external_tool_version_active_uniq;
DROP INDEX IF EXISTS external_tool_version_draft_uniq;
DROP INDEX IF EXISTS external_tool_version_review_uniq;
CREATE UNIQUE INDEX IF NOT EXISTS external_tool_version_active_uniq
    ON external_tool_version (external_tool_id) WHERE status = 'active';
CREATE UNIQUE INDEX IF NOT EXISTS external_tool_version_draft_uniq
    ON external_tool_version (external_tool_id) WHERE status = 'draft';
CREATE UNIQUE INDEX IF NOT EXISTS external_tool_version_review_uniq
    ON external_tool_version (external_tool_id) WHERE status = 'review';

DROP INDEX IF EXISTS system_prompt_template_version_active_uniq;
DROP INDEX IF EXISTS system_prompt_template_version_draft_uniq;
DROP INDEX IF EXISTS system_prompt_template_version_review_uniq;
CREATE UNIQUE INDEX IF NOT EXISTS system_prompt_template_version_active_uniq
    ON system_prompt_template_version (template_id) WHERE status = 'active';
CREATE UNIQUE INDEX IF NOT EXISTS system_prompt_template_version_draft_uniq
    ON system_prompt_template_version (template_id) WHERE status = 'draft';
CREATE UNIQUE INDEX IF NOT EXISTS system_prompt_template_version_review_uniq
    ON system_prompt_template_version (template_id) WHERE status = 'review';

-- 5) `UNIQUE (entity_id, locale, version)` aus 0042/0065 BEWUSST BEIBEHALTEN
--    (Abweichung vom urspruenglichen Plan-Entwurf, der einen Rueckbau auf
--    `(entity_id, version)` vorsah): Legacy-Daten koennen DE-v1 UND EN-v1
--    unter derselben Entity tragen (angelegt ueber die ADR-0027-Multi-
--    Checkbox, bevor Schritt 3 dieser Migration konsolidiert hat — die
--    Konsolidierung aendert nur den Status, nicht die locale/version-Historie
--    der Bestandsrows). Ein Rueckbau auf `(entity_id, version)` wuerde bei
--    diesen Rows sofort mit einer UniqueViolation gegen die Migration selbst
--    scheitern. Die App berechnet `next_version` kuenftig global ueber alle
--    locales (WP3) — dadurch entstehen keine NEUEN Kollisionen, die
--    bestehende Constraint bleibt also weiterhin ausreichend UND ist die
--    einzige Variante, die ohne Daten-Bereinigung idempotent anwendbar ist.

-- 6) Zusaetzliche Lese-Indices (entity_id, version DESC) fuer locale-
--    agnostische Reads (WP3: "neueste/aktive Version ohne locale-Filter").
--    Die bestehenden `*_version_locale_idx` aus 0042/0065 decken das nicht ab
--    (locale sitzt zwischen entity_id und version, daher keine globale
--    Sortierung nach version je entity_id).

CREATE INDEX IF NOT EXISTS persona_version_id_version_idx
    ON persona_version (persona_id, version DESC);
CREATE INDEX IF NOT EXISTS playbook_version_id_version_idx
    ON playbook_version (playbook_id, version DESC);
CREATE INDEX IF NOT EXISTS resource_version_id_version_idx
    ON resource_version (resource_id, version DESC);
CREATE INDEX IF NOT EXISTS external_tool_version_id_version_idx
    ON external_tool_version (external_tool_id, version DESC);
CREATE INDEX IF NOT EXISTS system_prompt_template_version_id_version_idx
    ON system_prompt_template_version (template_id, version DESC);

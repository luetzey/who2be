-- Migration 0034 — agent: persona_id + system_prompt_template_id optional
-- (Feature-Expansion Track H — leere Huelle erlaubt)
--
-- Renumber 0030 -> 0034: Track H und Track D hatten beide parallel die Nummer
-- 0030 vergeben. Da diese Migration idempotent ist (siehe unten), ist die
-- Umbenennung gefahrlos — ein erneuter Lauf unter neuem Dateinamen ist ein No-Op.
--
-- Ein Agent darf als leere Huelle (ohne Persona und/oder Template) angelegt
-- werden, die spaeter per PUT vervollstaendigt wird. Dafuer fallen die
-- NOT-NULL-Constraints auf beiden Referenzspalten weg.
--
-- Die Composite-FKs aus Migration 0023 bleiben unveraendert: Postgres prueft
-- bei MATCH SIMPLE (Default) einen Fremdschluessel NICHT, sobald eine seiner
-- Spalten NULL ist. Eine Huelle mit persona_id IS NULL umgeht den FK also
-- sauber, waehrend ein gesetzter Wert weiterhin Workspace-gepinnt validiert
-- wird. Tenancy bleibt damit garantiert.
--
-- Idempotent: DROP NOT NULL auf einer bereits nullbaren Spalte ist ein No-Op.

ALTER TABLE agent ALTER COLUMN persona_id DROP NOT NULL;
ALTER TABLE agent ALTER COLUMN system_prompt_template_id DROP NOT NULL;

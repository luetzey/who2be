-- Migration 0055 — Builder-Content auf Feedback-Verankerung nachziehen (ADR-0038)
--
-- PR #272 hat die Feedback-Bullets nur in die SEED-Quelldateien
-- (builder_persona_content.json, agent_builder_body.json) geschrieben. Der Seed
-- ist „skip-if-exists" (ON CONFLICT DO NOTHING / NOT-EXISTS-Guards) — bestehende
-- Workspaces, die den Builder VOR #272 geseedet haben, bekommen die Bullets also
-- nicht. Diese Migration zieht sie fuer bestehende Workspaces nach.
--
-- Verfahren je Builder-Persona / agent-builder-Template: an den AKTIVEN
-- Versions-Inhalt den Feedback-Bullet ANHAENGEN (append-only — Nutzer-Anpassungen
-- bleiben erhalten) und als NEUE aktive Version schreiben; die bisherige aktive
-- Version wird auf 'inactive' gesetzt (Demote-vor-Insert haelt die
-- Partial-Unique-Invariante „genau eine aktive Version"). `current_version` der
-- Eltern-Zeile wird auf die neue Version gehoben (app-gepflegt, kein Trigger).
-- `workspace_id` der Versions-Zeile fuellt der Trigger aus Migration 0035.
--
-- Idempotent: enthaelt der aktive Inhalt den Bullet (per Block-`id`) bereits,
-- wird die Zeile uebersprungen — frisch geseedete Workspaces (Inhalt schon mit
-- Bullet) und Re-Laeufe sind No-ops. Persona-Bloecke liegen als echtes
-- JSON-Array unter content.content.blocks; der Template-Body ist ein
-- STRINGIFIZIERTES Array unter content.body (parse -> append -> re-stringify).

-- 1. Builder-Persona ----------------------------------------------------------
DO $$
DECLARE
    r record;
    fb jsonb := '[{"id":"bp-li-allowed-fb","type":"bulletListItem","props":{"textColor":"default","backgroundColor":"default","textAlignment":"left"},"content":[{"type":"text","text":"Nutzung und Qualitaet zurueckmelden via record_usage / submit_feedback — faellt dir beim Konsistenz-Check ein veraltetes oder widerspruechliches Element auf, melde es (signal outdated/incorrect), statt es stillschweigend zu uebergehen.","styles":{}}],"children":[]}]'::jsonb;
    new_ver int;
BEGIN
    FOR r IN
        SELECT pv.persona_id, pv.locale, pv.content, pv.created_by
        FROM persona_version pv
        JOIN persona p ON p.id = pv.persona_id
        WHERE p.name = 'Builder'
          AND pv.status = 'active'
          AND NOT (
            COALESCE(pv.content #> '{content,blocks}', '[]'::jsonb)
            @> '[{"id":"bp-li-allowed-fb"}]'::jsonb
          )
    LOOP
        SELECT max(version) + 1 INTO new_ver FROM persona_version
            WHERE persona_id = r.persona_id AND locale = r.locale;
        UPDATE persona_version SET status = 'inactive'
            WHERE persona_id = r.persona_id AND locale = r.locale AND status = 'active';
        INSERT INTO persona_version (persona_id, version, content, status, created_by, locale)
        VALUES (
            r.persona_id,
            new_ver,
            jsonb_set(
                r.content,
                '{content,blocks}',
                COALESCE(r.content #> '{content,blocks}', '[]'::jsonb) || fb
            ),
            'active',
            r.created_by,
            r.locale
        );
        UPDATE persona SET current_version = new_ver, updated_at = now()
            WHERE id = r.persona_id;
    END LOOP;
END
$$;

-- 2. agent-builder-Template ---------------------------------------------------
DO $$
DECLARE
    r record;
    fb jsonb := '[{"id":"ab-li-fb","type":"bulletListItem","props":{"textColor":"default","backgroundColor":"default","textAlignment":"left"},"content":[{"type":"text","text":"Rueckmeldung: Melde nach jedem genutzten Playbook bzw. jeder Resource via record_usage (outcome applied/skipped/error); melde Veraltetes oder Falsches via submit_feedback statt es selbst umzuschreiben.","styles":{}}],"children":[]}]'::jsonb;
    new_body text;
    new_ver int;
BEGIN
    FOR r IN
        SELECT tv.template_id, tv.content, tv.created_by
        FROM system_prompt_template_version tv
        JOIN system_prompt_template t ON t.id = tv.template_id
        WHERE t.slug = 'agent-builder'
          AND tv.status = 'active'
          AND tv.content ? 'body'
          AND NOT ((tv.content ->> 'body')::jsonb @> '[{"id":"ab-li-fb"}]'::jsonb)
    LOOP
        new_body := (((r.content ->> 'body')::jsonb) || fb)::text;
        SELECT max(version) + 1 INTO new_ver FROM system_prompt_template_version
            WHERE template_id = r.template_id;
        UPDATE system_prompt_template_version SET status = 'inactive'
            WHERE template_id = r.template_id AND status = 'active';
        INSERT INTO system_prompt_template_version (template_id, version, content, status, created_by)
        VALUES (
            r.template_id,
            new_ver,
            jsonb_set(r.content, '{body}', to_jsonb(new_body)),
            'active',
            r.created_by
        );
        UPDATE system_prompt_template SET current_version = new_ver, updated_at = now()
            WHERE id = r.template_id;
    END LOOP;
END
$$;

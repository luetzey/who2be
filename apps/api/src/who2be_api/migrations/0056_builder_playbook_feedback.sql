-- Migration 0056 — Builder-Playbooks um Feedback-Hinweis nachziehen (ADR-0038)
--
-- Analog zu 0055 (Persona/Template), aber fuer die vier Builder-Playbooks: der
-- Seed ist skip-if-exists, also tragen bestehende Workspaces den Feedback-Hinweis
-- nicht. Diese Migration haengt an den AKTIVEN Playbook-Body (content.body —
-- STRINGIFIZIERTES BlockNote-Array) eine kleine „Feedback"-Sektion (Heading +
-- Paragraph) an und schreibt eine NEUE aktive Version (alte -> inactive,
-- current_version gehoben). Append-only (Customizations bleiben), idempotent per
-- Block-id `pb-feedback-h`.
--
-- Zielgenauigkeit: nur Playbooks, die per persona_playbook an eine Persona namens
-- 'Builder' geknuepft sind UND einen der vier Builder-Namen tragen — so werden
-- gleichnamige Nutzer-Playbooks nicht angefasst.

DO $$
DECLARE
    r record;
    fb jsonb := '[{"id":"pb-feedback-h","type":"heading","props":{"level":2,"textColor":"default","backgroundColor":"default","textAlignment":"left"},"content":[{"type":"text","text":"Feedback","styles":{}}],"children":[]},{"id":"pb-feedback-p","type":"paragraph","props":{"textColor":"default","backgroundColor":"default","textAlignment":"left"},"content":[{"type":"text","text":"Faellt dir beim Lesen bestehender Elemente Veraltetes oder Falsches auf, melde es via submit_feedback (signal outdated/incorrect/unclear) statt es stillschweigend zu uebergehen; genutzte Playbooks/Resources via record_usage (applied/skipped/error). So wird die AgentDB selbst-verbessernd.","styles":{}}],"children":[]}]'::jsonb;
    new_body text;
    new_ver int;
BEGIN
    FOR r IN
        SELECT DISTINCT pv.playbook_id, pv.locale, pv.content, pv.created_by
        FROM playbook_version pv
        JOIN playbook pb ON pb.id = pv.playbook_id
        JOIN persona_playbook pp ON pp.playbook_id = pb.id
        JOIN persona per ON per.id = pp.persona_id
        WHERE per.name = 'Builder'
          AND per.workspace_id = pb.workspace_id
          AND pv.status = 'active'
          AND pv.content ? 'body'
          AND pb.name = ANY (ARRAY[
            'Persona anlegen & pflegen',
            'Playbook anlegen & pflegen',
            'Agent anlegen & pflegen',
            'Konsistenz- & Drift-Check'
          ])
          AND NOT ((pv.content ->> 'body')::jsonb @> '[{"id":"pb-feedback-h"}]'::jsonb)
    LOOP
        new_body := (((r.content ->> 'body')::jsonb) || fb)::text;
        SELECT max(version) + 1 INTO new_ver FROM playbook_version
            WHERE playbook_id = r.playbook_id AND locale = r.locale;
        UPDATE playbook_version SET status = 'inactive'
            WHERE playbook_id = r.playbook_id AND locale = r.locale AND status = 'active';
        INSERT INTO playbook_version (playbook_id, version, content, status, created_by, locale)
        VALUES (
            r.playbook_id,
            new_ver,
            jsonb_set(r.content, '{body}', to_jsonb(new_body)),
            'active',
            r.created_by,
            r.locale
        );
        UPDATE playbook SET current_version = new_ver, updated_at = now()
            WHERE id = r.playbook_id;
    END LOOP;
END
$$;

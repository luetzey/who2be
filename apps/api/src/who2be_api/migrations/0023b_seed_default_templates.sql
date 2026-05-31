-- Migration 0023b — Seed der drei Default-SystemPromptTemplates pro Workspace
-- (Phase 3 Runde 3 Track 3 — Agent + Template).
--
-- Drei kuratierte Default-Templates pro Workspace:
--   * customer-support-agent — Support-Agent mit Persona-Profil, Playbooks
--     und Trigger-Liste.
--   * knowledge-worker — Wissensarbeiter-Setup mit Resource-Snippets.
--   * conversational-coach — Coaching-Agent mit Persona-Voice + Playbooks.
--
-- Idempotenz: ON CONFLICT (workspace_id, slug) DO NOTHING (siehe 0022). Die
-- Versions-Inserts sind ueber NOT EXISTS gegen system_prompt_template_version
-- defensiv (zweiter Lauf erzeugt KEINE Duplikate, falls jemand zwischen den
-- Inserts manuell editiert hat).
--
-- owner_id: erster Admin des Workspaces (oder erstes Mitglied), CTE-Pickup.

WITH ws_owner AS (
    SELECT w.id AS workspace_id,
           COALESCE(
             (SELECT user_id FROM workspace_member
                WHERE workspace_id = w.id AND role = 'admin'
                ORDER BY joined_at ASC, user_id ASC LIMIT 1),
             (SELECT user_id FROM workspace_member
                WHERE workspace_id = w.id
                ORDER BY joined_at ASC, user_id ASC LIMIT 1)
           ) AS owner_id
      FROM workspace w
),
seeds(slug, name, body) AS (VALUES
    (
      'customer-support-agent',
      'Customer-Support-Agent',
      E'Du bist {{ persona.name }} — {{ persona.description }}.\n\n' ||
      E'## Hintergrund zur Rolle\n{{ persona.profile }}\n\n' ||
      E'## Themen-Tags\n{{ persona.tags }}\n\n' ||
      E'## Spielbuecher\nFolge konsequent diesen Playbooks, wenn der Nutzer einen passenden Auslöser anspricht:\n{{ playbooks }}\n\n' ||
      E'## Trigger-Stichworte\nReagiere besonders auf: {{ triggers }}\n\n' ||
      E'## Wissensquellen\n{{ resources }}\n\n' ||
      E'Antworte ruhig, präzise und in der gleichen Sprache wie der Nutzer.'
    ),
    (
      'knowledge-worker',
      'Knowledge-Worker',
      E'Du bist {{ persona.name }}, ein Wissensarbeiter mit folgendem Profil:\n{{ persona.description }}\n\n' ||
      E'## Persönliche Notizen\n{{ persona.profile }}\n\n' ||
      E'## Verfügbares Wissen\n{{ resources }}\n\n' ||
      E'## Arbeitsabläufe\n{{ playbooks }}\n\n' ||
      E'Nutze die Wissensquellen, bevor du externe Annahmen triffst. ' ||
      E'Wenn die Quelle widersprüchlich ist, weise höflich darauf hin.'
    ),
    (
      'conversational-coach',
      'Conversational-Coach',
      E'Du bist {{ persona.name }} — {{ persona.description }}.\n\n' ||
      E'## Coach-Stimme\n{{ persona.profile }}\n\n' ||
      E'## Schwerpunkte\nTags: {{ persona.tags }}\n\n' ||
      E'## Methodenkasten\n{{ playbooks }}\n\n' ||
      E'## Cues, die einen Methodenwechsel auslösen\n{{ triggers }}\n\n' ||
      E'Bleibe stets gesprächig, stelle Fragen statt Antworten zu predigen, und beziehe die Methoden nur ein, wenn sie zum Gespräch passen.'
    )
),
inserted_templates AS (
    INSERT INTO system_prompt_template (workspace_id, owner_id, name, slug)
    SELECT wo.workspace_id, wo.owner_id, s.name, s.slug
      FROM ws_owner wo
      CROSS JOIN seeds s
     WHERE wo.owner_id IS NOT NULL
    ON CONFLICT (workspace_id, slug) DO NOTHING
    RETURNING id, workspace_id, owner_id
)
INSERT INTO system_prompt_template_version
       (template_id, version, content, status, created_by)
SELECT it.id, 1,
       jsonb_build_object(
           'description', '',
           'body', s.body
       ),
       'active',
       it.owner_id
  FROM inserted_templates it
  JOIN system_prompt_template t ON t.id = it.id
  JOIN seeds s ON s.slug = t.slug
 WHERE NOT EXISTS (
       SELECT 1 FROM system_prompt_template_version v
        WHERE v.template_id = it.id AND v.version = 1
 );

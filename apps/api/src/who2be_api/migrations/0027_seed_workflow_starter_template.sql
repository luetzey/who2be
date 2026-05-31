-- Migration 0027 — Seed des Workflow-Starter-Templates (Welle 6)
--
-- Ein neues Default-Template `workflow-starter` (Name: "Workflow-Starter")
-- pro Workspace mit `body_format = 'blocknote'`. Es demonstriert die
-- Welle-5-Placeholder-Architektur und dient als Startpunkt fuer neue Agents.
--
-- Idempotenz: ON CONFLICT (workspace_id, slug) DO NOTHING (analog 0023b).
-- Versions-Insert ist ueber NOT EXISTS gegen system_prompt_template_version
-- defensiv — zweiter Lauf erzeugt keine Duplikate.
--
-- body: Top-Level-Array (kein {content: [...]}-Wrapper) — so wie Frontend
-- und der Renderer (daf93aa) es erwarten. Block-IDs sind stabile Kurzstrings.

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
inserted_templates AS (
    INSERT INTO system_prompt_template
           (workspace_id, owner_id, name, slug, body_format)
    SELECT wo.workspace_id, wo.owner_id,
           'Workflow-Starter', 'workflow-starter', 'blocknote'
      FROM ws_owner wo
     WHERE wo.owner_id IS NOT NULL
    ON CONFLICT (workspace_id, slug) DO NOTHING
    RETURNING id, workspace_id, owner_id
)
INSERT INTO system_prompt_template_version
       (template_id, version, content, status, created_by)
SELECT it.id,
       1,
       jsonb_build_object(
           'description', 'Universeller Workflow-Starter mit Persona, Werkzeugen und Schritt-fuer-Schritt-Anleitung.',
           'body', $body$[
  {
    "id": "ws-h1",
    "type": "heading",
    "props": {"level": 2, "textColor": "default", "backgroundColor": "default", "textAlignment": "left"},
    "content": [{"type": "text", "text": "Rolle", "styles": {}}],
    "children": []
  },
  {
    "id": "ws-p1",
    "type": "paragraph",
    "props": {"textColor": "default", "backgroundColor": "default", "textAlignment": "left"},
    "content": [
      {"type": "text", "text": "Du bist ", "styles": {}},
      {"type": "placeholder", "props": {"kind": "persona-field", "target_id": "name", "label": "Persona: Name"}},
      {"type": "text", "text": " — ", "styles": {}},
      {"type": "placeholder", "props": {"kind": "persona-field", "target_id": "description", "label": "Persona: Beschreibung"}},
      {"type": "text", "text": ".", "styles": {}}
    ],
    "children": []
  },
  {
    "id": "ws-h2",
    "type": "heading",
    "props": {"level": 2, "textColor": "default", "backgroundColor": "default", "textAlignment": "left"},
    "content": [{"type": "text", "text": "Verfuegbare Werkzeuge", "styles": {}}],
    "children": []
  },
  {
    "id": "ws-p2",
    "type": "paragraph",
    "props": {"textColor": "default", "backgroundColor": "default", "textAlignment": "left"},
    "content": [
      {"type": "placeholder", "props": {"kind": "tools-overview", "target_id": "", "label": "Werkzeuge"}}
    ],
    "children": []
  },
  {
    "id": "ws-h3",
    "type": "heading",
    "props": {"level": 2, "textColor": "default", "backgroundColor": "default", "textAlignment": "left"},
    "content": [{"type": "text", "text": "So gehst du vor", "styles": {}}],
    "children": []
  },
  {
    "id": "ws-li1",
    "type": "bulletListItem",
    "props": {"textColor": "default", "backgroundColor": "default", "textAlignment": "left"},
    "content": [{"type": "text", "text": "Hoere der Anfrage zu und identifiziere das Thema.", "styles": {}}],
    "children": []
  },
  {
    "id": "ws-li2",
    "type": "bulletListItem",
    "props": {"textColor": "default", "backgroundColor": "default", "textAlignment": "left"},
    "content": [{"type": "text", "text": "Rufe list_triggers() auf, um zu sehen, ob ein Playbook reagiert.", "styles": {}}],
    "children": []
  },
  {
    "id": "ws-li3",
    "type": "bulletListItem",
    "props": {"textColor": "default", "backgroundColor": "default", "textAlignment": "left"},
    "content": [{"type": "text", "text": "Wenn ja: fetch_playbook(id) und folge dessen Schritten.", "styles": {}}],
    "children": []
  },
  {
    "id": "ws-li4",
    "type": "bulletListItem",
    "props": {"textColor": "default", "backgroundColor": "default", "textAlignment": "left"},
    "content": [{"type": "text", "text": "Wenn das Playbook auf eine Resource verweist: fetch_resource(id).", "styles": {}}],
    "children": []
  },
  {
    "id": "ws-li5",
    "type": "bulletListItem",
    "props": {"textColor": "default", "backgroundColor": "default", "textAlignment": "left"},
    "content": [{"type": "text", "text": "Erst wenn keines passt, antworte aus deinem allgemeinen Wissen.", "styles": {}}],
    "children": []
  },
  {
    "id": "ws-h4",
    "type": "heading",
    "props": {"level": 2, "textColor": "default", "backgroundColor": "default", "textAlignment": "left"},
    "content": [{"type": "text", "text": "Letzter Stand", "styles": {}}],
    "children": []
  },
  {
    "id": "ws-p3",
    "type": "paragraph",
    "props": {"textColor": "default", "backgroundColor": "default", "textAlignment": "left"},
    "content": [
      {"type": "text", "text": "Heute ist der ", "styles": {}},
      {"type": "placeholder", "props": {"kind": "date", "target_id": "human", "label": "Datum"}},
      {"type": "text", "text": ".", "styles": {}}
    ],
    "children": []
  }
]$body$::text
       ),
       'active',
       it.owner_id
  FROM inserted_templates it
 WHERE NOT EXISTS (
       SELECT 1 FROM system_prompt_template_version v
        WHERE v.template_id = it.id AND v.version = 1
 );

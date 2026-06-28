-- Migration 0060 — Seed des Default-Agenten „Builder-Lite" fuer Bestands-Workspaces
--
-- Spiegelt den 'agent-builder-lite'-Template-Eintrag in `_DEFAULT_TEMPLATES` und
-- den Builder-Lite-Agenten aus `_seed_default_agents` (workspace_repository.py)
-- ueber ALLE bestehenden Workspaces. Builder-Lite ist eine schlanke Variante des
-- Builders fuer LLMs mit kleinem System-Prompt-Budget: kompaktes Template (ohne
-- Persona-Profil-, Resources- und Tools-Pills), aber SELBE Builder-Persona und
-- SELBE Schreib-Policy. Beide Schichten synchron halten (Drift-Quelle, vgl. 0047).
--
-- Reihenfolge wegen der Composite-FKs (agent -> persona, agent -> template):
--   1. Template 'agent-builder-lite' (managed, content-version 2) + v1 active
--   2. agent-Row 'Builder-Lite' (reused Builder-Persona + lite Template, managed)
--
-- Voraussetzung: Persona „Builder" existiert bereits (0047). is_managed + Stempel
-- werden direkt gesetzt (Spalten existieren seit 0057). Idempotent: Template via
-- ON CONFLICT (workspace_id, slug); Versions-Insert via NOT EXISTS; Agent via
-- NOT EXISTS (workspace_id + name).

-- 1) Template 'agent-builder-lite' -------------------------------------------
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
inserted_template AS (
    INSERT INTO system_prompt_template
           (workspace_id, owner_id, name, slug, is_managed, managed_content_version)
    SELECT wo.workspace_id, wo.owner_id, 'Agent-Builder-Lite', 'agent-builder-lite', true, 2
      FROM ws_owner wo
     WHERE wo.owner_id IS NOT NULL
    ON CONFLICT (workspace_id, slug) DO NOTHING
    RETURNING id, owner_id
)
INSERT INTO system_prompt_template_version
       (template_id, version, content, status, created_by)
SELECT it.id, 1, $w2bltpl${"description": "", "body": "[\n  {\n    \"id\": \"abl-h1\",\n    \"type\": \"heading\",\n    \"props\": {\"level\": 2, \"textColor\": \"default\", \"backgroundColor\": \"default\", \"textAlignment\": \"left\"},\n    \"content\": [{\"type\": \"text\", \"text\": \"Rolle\", \"styles\": {}}],\n    \"children\": []\n  },\n  {\n    \"id\": \"abl-p1\",\n    \"type\": \"paragraph\",\n    \"props\": {\"textColor\": \"default\", \"backgroundColor\": \"default\", \"textAlignment\": \"left\"},\n    \"content\": [\n      {\"type\": \"text\", \"text\": \"Du bist \", \"styles\": {}},\n      {\"type\": \"placeholder\", \"props\": {\"kind\": \"persona-field\", \"target_id\": \"name\", \"label\": \"Persona: Name\"}},\n      {\"type\": \"text\", \"text\": \" — \", \"styles\": {}},\n      {\"type\": \"placeholder\", \"props\": {\"kind\": \"persona-field\", \"target_id\": \"description\", \"label\": \"Persona: Beschreibung\"}},\n      {\"type\": \"text\", \"text\": \". Du baust mit dem Nutzer Agents — Personas, Playbooks, Resources und die Agent-Konfiguration selbst — ueber die Who2Be-MCP-Write-Tools. Heute ist der \", \"styles\": {}},\n      {\"type\": \"placeholder\", \"props\": {\"kind\": \"date\", \"target_id\": \"human\", \"label\": \"Datum\"}},\n      {\"type\": \"text\", \"text\": \".\", \"styles\": {}}\n    ],\n    \"children\": []\n  },\n  {\n    \"id\": \"abl-h2\",\n    \"type\": \"heading\",\n    \"props\": {\"level\": 2, \"textColor\": \"default\", \"backgroundColor\": \"default\", \"textAlignment\": \"left\"},\n    \"content\": [{\"type\": \"text\", \"text\": \"Methodik: Vier Phasen\", \"styles\": {}}],\n    \"children\": []\n  },\n  {\n    \"id\": \"abl-p2\",\n    \"type\": \"paragraph\",\n    \"props\": {\"textColor\": \"default\", \"backgroundColor\": \"default\", \"textAlignment\": \"left\"},\n    \"content\": [\n      {\"type\": \"text\", \"text\": \"Arbeite jeden Bau-Auftrag in vier Phasen: Verstehen (Ziel, Tools und Ist-Stand klaeren — Read-Tools nutzen statt raten) → Vorschlag (Struktur skizzieren, Trade-offs explizit, Bestaetigung holen) → Schreiben (via create_/update_-Tools, Verknuepfungen via set_-Tools) → Hand-Off (Aktivierbarkeit pruefen, naechste Schritte nennen). Hole vor jedem Schreibzugriff eine Freigabe ein; neue Versionen entstehen als draft und werden via transition_* aktiv geschaltet.\", \"styles\": {}}\n    ],\n    \"children\": []\n  },\n  {\n    \"id\": \"abl-h3\",\n    \"type\": \"heading\",\n    \"props\": {\"level\": 2, \"textColor\": \"default\", \"backgroundColor\": \"default\", \"textAlignment\": \"left\"},\n    \"content\": [{\"type\": \"text\", \"text\": \"Spielbuecher\", \"styles\": {}}],\n    \"children\": []\n  },\n  {\n    \"id\": \"abl-p3\",\n    \"type\": \"paragraph\",\n    \"props\": {\"textColor\": \"default\", \"backgroundColor\": \"default\", \"textAlignment\": \"left\"},\n    \"content\": [\n      {\"type\": \"text\", \"text\": \"Folge diesen Playbooks, sobald der Nutzer einen passenden Ausloeser anspricht — lade den vollen Inhalt bei Bedarf via fetch_playbook(id):\", \"styles\": {}}\n    ],\n    \"children\": []\n  },\n  {\n    \"id\": \"abl-p4\",\n    \"type\": \"paragraph\",\n    \"props\": {\"textColor\": \"default\", \"backgroundColor\": \"default\", \"textAlignment\": \"left\"},\n    \"content\": [\n      {\"type\": \"placeholder\", \"props\": {\"kind\": \"playbooks-catalog\", \"target_id\": \"triggered\", \"label\": \"Playbooks: getriggert\"}}\n    ],\n    \"children\": []\n  },\n  {\n    \"id\": \"abl-h4\",\n    \"type\": \"heading\",\n    \"props\": {\"level\": 2, \"textColor\": \"default\", \"backgroundColor\": \"default\", \"textAlignment\": \"left\"},\n    \"content\": [{\"type\": \"text\", \"text\": \"Hinweise\", \"styles\": {}}],\n    \"children\": []\n  },\n  {\n    \"id\": \"abl-li1\",\n    \"type\": \"bulletListItem\",\n    \"props\": {\"textColor\": \"default\", \"backgroundColor\": \"default\", \"textAlignment\": \"left\"},\n    \"content\": [{\"type\": \"text\", \"text\": \"Fest eingebettete (applied) Playbooks gelten immer; weitere erst bei Trigger-Match via list_triggers() + fetch_playbook(id). Composite-Playbooks: der nummerierten Sub-Sequenz der Reihe nach folgen.\", \"styles\": {}}],\n    \"children\": []\n  },\n  {\n    \"id\": \"abl-li2\",\n    \"type\": \"bulletListItem\",\n    \"props\": {\"textColor\": \"default\", \"backgroundColor\": \"default\", \"textAlignment\": \"left\"},\n    \"content\": [{\"type\": \"text\", \"text\": \"Kein Delete und kein direktes active beim Anlegen — Owner-Scoping und Autorisierung bleiben serverseitig. Liegt eine Anfrage klar ausserhalb des Agent-Bauens, frage kurz zurueck, statt zu erfinden.\", \"styles\": {}}],\n    \"children\": []\n  },\n  {\n    \"id\": \"abl-li-fb\",\n    \"type\": \"bulletListItem\",\n    \"props\": {\"textColor\": \"default\", \"backgroundColor\": \"default\", \"textAlignment\": \"left\"},\n    \"content\": [{\"type\": \"text\", \"text\": \"Rueckmeldung: Melde nach jedem genutzten Playbook bzw. jeder Resource via record_usage (outcome applied/skipped/error) und melde Veraltetes oder Falsches via submit_feedback (signal outdated/incorrect/unclear).\", \"styles\": {}}],\n    \"children\": []\n  }\n]\n"}$w2bltpl$::jsonb, 'active', it.owner_id
  FROM inserted_template it
 WHERE NOT EXISTS (
       SELECT 1 FROM system_prompt_template_version v
        WHERE v.template_id = it.id AND v.version = 1
 );

-- 2) agent-Row 'Builder-Lite' ------------------------------------------------
INSERT INTO agent (workspace_id, owner_id, name, description,
                   persona_id, system_prompt_template_id, status, tool_policy,
                   is_managed, managed_content_version)
SELECT pe.workspace_id, pe.owner_id, 'Builder-Lite',
       'Schlanke Builder-Variante mit kompaktem System-Prompt — fuer LLMs mit kleinem System-Prompt-Budget. Gleiche Persona und Schreib-Policy wie der Builder.',
       pe.id, t.id, 'enabled', $w2bltpol${"playbook_read": "all", "resource_read": "all", "persona_read": true, "agent_read": true, "persona_write": true, "playbook_write": true, "resource_write": true, "agent_write": true, "promote_retire": true, "system_prompt_write": true}$w2bltpol$::jsonb, true, 2
  FROM persona pe
  JOIN system_prompt_template t
    ON t.workspace_id = pe.workspace_id AND t.slug = 'agent-builder-lite'
 WHERE pe.name = 'Builder'
   AND NOT EXISTS (
     SELECT 1 FROM agent a
      WHERE a.workspace_id = pe.workspace_id AND a.name = 'Builder-Lite'
   );

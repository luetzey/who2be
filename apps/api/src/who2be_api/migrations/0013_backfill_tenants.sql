-- Migration 0013 — Backfill bestehender Daten in die Tenant-Hierarchie (TASK-300)
-- Pro distinct owner_id ueber persona/playbook/api_token wird einmalig eine
-- Personal-Organization (kind='personal') angelegt, mit dem User als
-- org_member-owner, einem default-Workspace "Personal" und dem User als
-- workspace_member-admin. Anschliessend werden die workspace_id-Spalten auf
-- persona/playbook/api_token gefuellt.
--
-- Konvention fuer Personal-Orgs: `slug = owner_id::text`. Damit bleibt die
-- Zuordnung User -> Personal-Org allein ueber den Slug rekonstruierbar, ohne
-- eine extra Mapping-Tabelle einzufuehren. Company-Orgs (kind='company')
-- werden spaeter mit menschenlesbaren Slugs angelegt.
--
-- Idempotenz: alle INSERTs nutzen ON CONFLICT DO NOTHING gegen die jeweiligen
-- Unique-Constraints; die UPDATEs treffen nur Zeilen mit workspace_id IS NULL.
-- Ein zweiter Lauf der Migration ist daher ein No-op (wird im Migration-Runner
-- ohnehin uebersprungen, dies ist die Defense gegen versehentliches Re-Apply).
--
-- Hinweis: SET NOT NULL + UNIQUE(workspace_id, id) + Composite-FK-Switch auf
-- persona_playbook leben in 0014_finalize_workspace_id (Sub-Task 2.1a-2),
-- damit der zugehoerige Repository-Refactor in derselben Sub-Task landet.

INSERT INTO organization (name, slug, kind)
SELECT 'Personal', owner_id::text, 'personal'
FROM (
    SELECT DISTINCT owner_id FROM persona
    UNION
    SELECT DISTINCT owner_id FROM playbook
    UNION
    SELECT DISTINCT owner_id FROM api_token
) AS owners
ON CONFLICT (kind, slug) DO NOTHING;

INSERT INTO org_member (org_id, user_id, role)
SELECT o.id, o.slug::uuid, 'owner'
FROM organization o
WHERE o.kind = 'personal'
ON CONFLICT (org_id, user_id) DO NOTHING;

INSERT INTO workspace (org_id, name, slug)
SELECT o.id, 'Personal', 'personal'
FROM organization o
WHERE o.kind = 'personal'
ON CONFLICT (org_id, slug) DO NOTHING;

INSERT INTO workspace_member (workspace_id, user_id, role)
SELECT w.id, o.slug::uuid, 'admin'
FROM workspace w
JOIN organization o ON o.id = w.org_id
WHERE o.kind = 'personal' AND w.slug = 'personal'
ON CONFLICT (workspace_id, user_id) DO NOTHING;

UPDATE persona p
SET workspace_id = w.id
FROM workspace w
JOIN organization o ON o.id = w.org_id
WHERE o.kind = 'personal'
  AND o.slug = p.owner_id::text
  AND w.slug = 'personal'
  AND p.workspace_id IS NULL;

UPDATE playbook pb
SET workspace_id = w.id
FROM workspace w
JOIN organization o ON o.id = w.org_id
WHERE o.kind = 'personal'
  AND o.slug = pb.owner_id::text
  AND w.slug = 'personal'
  AND pb.workspace_id IS NULL;

UPDATE api_token t
SET workspace_id = w.id
FROM workspace w
JOIN organization o ON o.id = w.org_id
WHERE o.kind = 'personal'
  AND o.slug = t.owner_id::text
  AND w.slug = 'personal'
  AND t.workspace_id IS NULL;

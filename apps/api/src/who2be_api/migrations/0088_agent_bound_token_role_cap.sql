-- Migration 0088 — agent-gebundene Tokens auf `editor` deckeln (Bestand)
-- Plan: .claude/plan/2026-09-26-0900_kontoweite-routen-human-gate.md
--
-- Ab dieser Aenderung erhaelt ein an einen Agenten gebundener API-Token
-- hoechstens die Rolle `editor`; beide Mint-Pfade (`token_service.create` und
-- `oauth_service._issue`) setzen das ueber `cap_agent_bound_role` durch. Die
-- Rolle `admin` an einem Maschinen-Token verschafft ihm eine Reichweite, die
-- seine Pro-Agent-Policy nicht begrenzt — sie ist im Token gepinnt und steht
-- neben der Policy, statt von ihr eingeschraenkt zu werden.
--
-- Diese Migration zieht den Bestand nach. Ohne sie gaelte die neue Grenze nur
-- fuer kuenftige Tokens, waehrend die vorhandenen weiterlaufen: der Deckel waere
-- eine Aussage ueber die Zukunft und keine ueber den Zustand.
--
-- Seit Migration 0048 ist jeder AKTIVE Token agent-gebunden (CHECK
-- `agent_id IS NOT NULL OR revoked_at IS NOT NULL`). Die betroffene Menge ist
-- damit genau „aktive Tokens mit role = 'admin'". Widerrufene Zeilen bleiben
-- unberuehrt: sie sind ungueltig, und ihre historische Rolle ist Teil des
-- Audit-Trails.
--
-- BETRIEBSHINWEIS
-- ---------------
-- Die Herabstufung ist wirksam, sobald sie laeuft — ein betroffener Token
-- verliert sofort die Wirkung seiner Admin-Rolle. Das ist kein STILLER Verlust:
-- jede Zeile hinterlaesst einen `audit_log`-Eintrag `token.role_capped` mit der
-- alten Rolle, dem Workspace und dem gebundenen Agenten. Wer nach dem Deploy
-- wissen will, ob und welche Tokens betroffen waren:
--
--     SELECT created_at, workspace_id, target, detail
--     FROM audit_log
--     WHERE action = 'token.role_capped'
--     ORDER BY created_at;
--
-- Faellt eine Integration danach mit 403 aus, ist die Abhilfe NICHT ein neues
-- admin-Token (das gibt es nicht mehr), sondern eine der beiden: die Aktion
-- gehoert einer angemeldeten Person, oder die benoetigte Berechtigung gehoert
-- als Capability in die Tool-Policy des Agenten.
--
-- `actor_id` bleibt NULL: die Herabstufung ist ein System-Ereignis des Deploys,
-- kein Vorgang eines Nutzers. Die Spalte ist dafuer nullable (0044).
--
-- Idempotent: nach dem ersten Lauf findet das UPDATE keine Zeile mehr, und der
-- INSERT haengt an dessen RETURNING — ein zweiter Lauf schreibt also auch kein
-- zweites Audit-Ereignis.

WITH capped AS (
    UPDATE api_token
    SET role = 'editor'
    WHERE role = 'admin'
      AND revoked_at IS NULL
      AND agent_id IS NOT NULL
    RETURNING id, workspace_id, agent_id
)
INSERT INTO audit_log (workspace_id, actor_id, action, target, detail)
SELECT
    capped.workspace_id,
    NULL,
    'token.role_capped',
    capped.id::text,
    jsonb_build_object(
        'from_role', 'admin',
        'to_role', 'editor',
        'agent_id', capped.agent_id::text,
        'via', 'migration_0088'
    )
FROM capped;

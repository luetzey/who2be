-- Migration 0048 — API-Token zwingend agent-gebunden (secure by default)
--
-- Ungebundene Tokens (`agent_id IS NULL`) tragen keine Tool-Policy und umgehen
-- damit das Read-Scoping eines Agenten — in der Least-Privilege-Welt ist das ein
-- Schlupfloch (ein solcher Token sieht den ganzen Workspace). Ab hier MUSS jeder
-- aktive Token an einen Agenten gebunden sein. Die App-Schicht erzwingt das fuer
-- neue Tokens (TokenCreate.agent_id required); diese Migration raeumt den Bestand
-- und haertet die DB nach.
--
-- Drei idempotente Schritte:
--
-- 1. Bestehende ungebundene Tokens widerrufen (kein Loeschen — die Row + Audit/
--    last_used-Historie bleibt, der Token ist nur ungueltig).
-- 2. FK `api_token.agent_id` von ON DELETE SET NULL (0046) auf ON DELETE CASCADE
--    umstellen. Sonst erzeugt ein Agent-Delete (hartes DELETE) wieder einen
--    ungebundenen Super-Token. Der Audit-Trail lebt separat in `audit_log`
--    (token.issued/revoked), nicht in `api_token` — kein Audit-Verlust.
-- 3. CHECK als zweite Verteidigungslinie: ein Token ist entweder agent-gebunden
--    ODER widerrufen. Erlaubt die in Schritt 1 widerrufenen Altzeilen (NULL +
--    revoked), verbietet aber jeden neuen aktiven ungebundenen Token — auch bei
--    direktem SQL-Insert ausserhalb des Service. Bewusst KEIN `SET NOT NULL` auf
--    `agent_id`, das wuerde an den revoked Altzeilen scheitern.

UPDATE api_token
SET revoked_at = now()
WHERE agent_id IS NULL
  AND revoked_at IS NULL;

ALTER TABLE api_token DROP CONSTRAINT IF EXISTS api_token_agent_id_fkey;

ALTER TABLE api_token
    ADD CONSTRAINT api_token_agent_id_fkey
    FOREIGN KEY (agent_id) REFERENCES agent (id) ON DELETE CASCADE;

ALTER TABLE api_token DROP CONSTRAINT IF EXISTS api_token_agent_bound_or_revoked;

ALTER TABLE api_token
    ADD CONSTRAINT api_token_agent_bound_or_revoked
    CHECK (agent_id IS NOT NULL OR revoked_at IS NOT NULL);

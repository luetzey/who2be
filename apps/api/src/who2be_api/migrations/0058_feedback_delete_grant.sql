-- Migration 0058 — Feedback-Hard-Delete fuer die Laufzeitrolle (ADR-0038-Folge)
--
-- Admin/Editor duerfen einzelne Feedback-Eintraege hart loeschen (Kurations-
-- Handlung, nicht agent-facing — kein MCP-Tool). agent_feedback war seit 0053
-- bewusst append-only (nur SELECT, INSERT fuer who2be_app). Fuer den Delete-
-- Pfad braucht die Laufzeitrolle zusaetzlich das DELETE-Recht auf
-- agent_feedback. Die feedback_resolution-Kinder raeumt der FK ON DELETE
-- CASCADE (Migration 0054) — eine Referential Action laeuft mit den Rechten
-- des Tabellen-Owners, ein DELETE-Grant auf der Kindtabelle ist also nicht
-- noetig. Idempotent (pg_roles-Guard, GRANT ist ohnehin wiederholbar).

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'who2be_app') THEN
        GRANT DELETE ON agent_feedback TO who2be_app;
    END IF;
END
$$;

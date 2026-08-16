-- Migration 0080 — Zugriffslog haerten: Modell-Snapshot + Append-only auch
-- gegen FK-Cascade (Security-Review Phase 2, H4/H5; ADR-0047-Nachtrag)
-- Plan: .claude/plan/2026-08-13-1200_agent-workarea-knowledge-base.md
--
-- H4 — Modell-Snapshot am Log-Eintrag: Die Compliance-Frage „welche Elemente
-- gingen je an einen EXTERNEN Anbieter" wurde bisher ueber einen JOIN auf die
-- AKTUELLE `agent`-Konfiguration beantwortet. Damit faelscht jede spaetere
-- Aenderung der Modell-Config die Historie rueckwirkend: ein Agent, der ein
-- Jahr lang auf einem externen Anbieter lief, sieht nach dem Umstellen auf
-- 'local' so aus, als waere nie etwas abgeflossen. Analog zu
-- `sensitivity_at_access` snapshottet der Server deshalb die Modell-Config
-- ZUM ZUGRIFFSZEITPUNKT. Nullable, weil (a) Altzeilen sie nicht haben und
-- (b) ein Agent ohne gepflegte Config legitim NULL traegt.
--
-- H5 — Append-only auch gegen Cascade: 0079 hatte
-- `agent_id ... REFERENCES agent (id) ON DELETE CASCADE`. Der Cascade laeuft
-- mit OWNER-Rechten, also greift der Grant-Entzug (nur SELECT/INSERT fuer
-- who2be_app) nicht: ein simpler Agent-Delete loeschte die Protokollzeilen
-- desselben Agenten gleich mit — das Log war ueber einen ganz normalen
-- API-Aufruf loeschbar. Der FK wird auf NO ACTION umgestellt; damit
-- SCHEITERT ein Agent-Delete, solange Log-Zeilen existieren. Das ist die
-- gewollte Konsequenz (das Compliance-Log ueberlebt den Agenten); der
-- Service faengt die ForeignKeyViolation und antwortet 409 mit Hinweis auf
-- den Retention-/Purge-Pfad.
--
-- Purge bleibt moeglich: `core/purge.py` laeuft als Owner und loescht die
-- Log-Zeilen des Workspaces/der Org jetzt EXPLIZIT, bevor die
-- Organization-CASCADE greift (der legitime Loeschpfad, DSGVO-Erasure).
--
-- Idempotenz: ALTER via ADD COLUMN IF NOT EXISTS; der FK via
-- DROP CONSTRAINT IF EXISTS + ADD CONSTRAINT (ein zweiter Lauf ersetzt ihn
-- durch denselben). RLS-neutral — Policy und Grants aus 0079 bleiben
-- unveraendert gueltig; der pg_roles-Guard schuetzt On-Prem/Dev ohne
-- who2be_app (Muster 0066/0070/0079).

-- H4: Server-Snapshot der Agent-Modell-Config zum Zugriffszeitpunkt.
ALTER TABLE agent_access_log
    ADD COLUMN IF NOT EXISTS model_provider_at_access text,
    ADD COLUMN IF NOT EXISTS model_name_at_access     text;

-- H5: FK ohne Cascade — der Agent-Delete darf das Protokoll nicht mitnehmen.
DO $$
BEGIN
    ALTER TABLE agent_access_log
        DROP CONSTRAINT IF EXISTS agent_access_log_agent_id_fkey;
    ALTER TABLE agent_access_log
        ADD CONSTRAINT agent_access_log_agent_id_fkey
        FOREIGN KEY (agent_id) REFERENCES agent (id) ON DELETE NO ACTION;
END
$$;

-- Grants unveraendert append-only (Wiederholung aus 0079 ist bewusst: eine
-- frisch aufgesetzte DB soll den Endzustand auch dann tragen, wenn spaeter
-- jemand an 0079 dreht).
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'who2be_app') THEN
        GRANT SELECT, INSERT ON agent_access_log TO who2be_app;
    END IF;
END
$$;

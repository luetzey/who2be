-- Migration 0101 — Herkunft eines Nutzungs-Ereignisses: `usage_event.source`
-- (ADR-0053 Abschnitt 3.4, Lernschleife Phase D, Paket D3)
--
-- Der Server zeichnet ab D3 selbst auf, welche Persona-, Playbook- und
-- Resource-Version ein agent-gebundener Aufrufer abgerufen hat (F-W5), und
-- schreibt dafuer `source = 'server'` mit `outcome = NULL` (eine Zeile je
-- Auslieferung, Owner-Weiche N2 = a). `record_usage` bleibt und meldet nur
-- noch das Ergebnis (`applied · skipped · error`) mit `source = 'agent_report'`.
--
-- Auswertung (`repositories/feedback_repository.py`): Nutzungen zaehlen nur
-- `source = 'server'`, Ergebnisse nur `source = 'agent_report'` — ohne diese
-- Trennung zaehlte jede Nutzung doppelt.
--
-- Bestand: alle vorhandenen Zeilen stammen aus `record_usage` und erhalten
-- ueber den Default `agent_report`. `ADD COLUMN ... DEFAULT <Konstante>` ist in
-- PostgreSQL ein reiner Katalog-Eintrag (kein Tabellen-Rewrite).
--
-- Grants unveraendert (0053: SELECT, INSERT fuer `who2be_app`); RLS bleibt.
--
-- Rueckweg (5.1, als eigene Vorwaerts-Migration): Spalte droppen; die
-- Aggregation zaehlt dann wieder alle Zeilen.
--
-- Idempotent: ADD COLUMN IF NOT EXISTS; CHECK via DROP IF EXISTS + ADD.

ALTER TABLE usage_event
    ADD COLUMN IF NOT EXISTS source text NOT NULL DEFAULT 'agent_report';

ALTER TABLE usage_event DROP CONSTRAINT IF EXISTS usage_event_source_check;
ALTER TABLE usage_event ADD CONSTRAINT usage_event_source_check
    CHECK (source IN ('agent_report', 'server'));

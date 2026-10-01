-- Migration 0095 — Freigabematrix Art x Herkunft (ADR-0053 Abschnitt 4,
-- Lernschleife Phase C, Paket C2a)
--
-- Eine JSONB-Spalte pro Workspace, Muster `workspace.memory_guard` (0067):
-- `{}` (Default) deserialisiert zu `MemoryAutoPolicy()` = alle Zellen aus
-- (Weiche M3). Ein Agent mit `memory_mode=auto` wirkt damit wie `suggest`,
-- bis ein Admin die einzige schaltbare Zelle (`user_fact` x `user_stated`)
-- einschaltet. Kein CHECK: Validierung liegt in Pydantic, geschrieben wird
-- nur ueber den admin-gated, human-only PUT `/memory-auto-policy`, der jede
-- Aenderung im `audit_log` festhaelt (4.3). Nie-Zellen ignoriert der Server
-- beim Schreiben UND beim Auswerten.
--
-- Rueckweg (5.1, als eigene Vorwaerts-Migration): Spalte droppen;
-- `memory_mode=auto` wirkt dann wieder ungestaffelt.
--
-- Idempotent via IF NOT EXISTS; RLS/Grants der workspace-Tabelle bestehen.

ALTER TABLE workspace
    ADD COLUMN IF NOT EXISTS memory_auto_policy jsonb NOT NULL DEFAULT '{}'::jsonb;

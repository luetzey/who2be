-- Migration 0067 — Workspace-Konfiguration des Memory-Injection-Waechters
-- (ADR-0044-Addendum, Plan .claude/plan/2026-07-19-1030_memory-guard-config.md)
--
-- Eine JSONB-Spalte pro Workspace: `{}` (Default) deserialisiert zur
-- Standard-Konfiguration (mode='standard', keine Phrasen) — Konvention wie
-- `agent.tool_policy` (0046). Kein CHECK: Validierung liegt in Pydantic
-- (`MemoryGuardConfig`), geschrieben wird nur ueber den admin-gated
-- PUT-Endpunkt (Agent-Tokens hart gesperrt).
--
-- Idempotent via IF NOT EXISTS; RLS/Grants der workspace-Tabelle bestehen.

ALTER TABLE workspace
    ADD COLUMN IF NOT EXISTS memory_guard jsonb NOT NULL DEFAULT '{}'::jsonb;

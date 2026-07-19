# Plan: Injection-Wächter konfigurierbar (pro Workspace, Stufe B)

- Datum: 2026-07-19
- Branch: `claude/autonomous-code-agent-setup-iz6ydx` (neu ab main, nach #328)
- Entscheidungen (User): **Stufe B** (Modus + literale Allow-/Block-Phrasen,
  KEINE freien Regex) und **Komplett-Aus gilt auch für auto-Agenten**
  (maximale Owner-Freiheit, Warnhinweis in der UI).

## Modell

`MemoryGuardConfig` (who2be_models.memory, JSONB `workspace.memory_guard`,
`{}` = Defaults — Konvention wie `agent.tool_policy`):

- `mode`: `standard` (Built-in-Filter, Default) | `custom` (Built-in +
  Phrasen-Regeln) | `off` (kein Injection-Filter; Importance/Dedup/Cap/
  Rate-Limit bleiben IMMER aktiv — der Guard betrifft nur den
  Injection-Filter).
- `allow_phrases` (max 50 × 2–100 Zeichen): übersteuern Built-in-Treffer —
  aber NUR, wenn der Regex-Treffer vollständig INNERHALB eines
  Phrasen-Vorkommens liegt (z. B. Treffer „jailbreak" in erlaubtem
  „Jailbreak-Detection"). Verhindert den trivialen Bypass „Allow-Phrase
  irgendwo anhängen".
- `block_phrases` (max 50 × 2–100 Zeichen): zusätzliche workspace-eigene
  Verbotsbegriffe (case-insensitive Substring).

Literale Phrasen statt Regex: kein ReDoS, keine Validierungs-Sandbox
(bewusste Ablehnung von Stufe C).

## Backend

1. Models + Export; Migration 0067 (`workspace.memory_guard jsonb NOT NULL
   DEFAULT '{}'`).
2. `PgMemoryRepository.get_guard_config/set_guard_config` (workspace-Zeile).
3. `MemoryService.save`: Guard-Verdikt gemäß Modus (off → Filter komplett
   aus, auch für auto-Agenten — User-Entscheidung; custom →
   Allow-Suppression + Block-Phrasen; standard → wie bisher). Prüft fact
   UND context.
4. REST (human-only + **admin**-Gate — Agent-Tokens hart 403, ein Agent darf
   seinen eigenen Wächter nie umkonfigurieren):
   - `GET /v1/workspaces/{ws}/memory-guard` → `MemoryGuardConfig`
   - `PUT /v1/workspaces/{ws}/memory-guard` → `MemoryGuardConfig`
5. OpenAPI-Golden regen; `security-reviewer` über Service+Router.

## Web (Sub-Agent)

`WorkspaceSettingsPage`: Sektion „Memory-Wächter" (nur admin sichtbar/
editierbar): Modus-Select mit Beschreibungen + deutlicher Warnung bei
„aus" (explizit: gilt auch für Agenten im Automatisch-Modus),
Chip-Editoren für Allow-/Block-Phrasen, Client-Methoden + Typen, i18n
de/en, Tests (fetch-Stub-Muster).

## Tests (Backend)

- Modus-Matrix: standard blockt Angriff; custom + Allow-Phrase, die den
  Treffer abdeckt → 201; Allow-Phrase, die den Treffer NICHT abdeckt →
  weiter 422 (Bypass-Test!); Block-Phrase → 422; off → Angriffstext 201,
  auch bei auto-Agent; Importance/Dedup/Cap bleiben bei off aktiv.
- Endpunkt-Gates: admin 200, editor 403, Agent-Token 403; `{}` → Defaults.

## Doku

ADR-0044-Addendum (Guard-Konfiguration, Bypass-feste Allow-Semantik,
bewusste Stufe-C-Ablehnung), DECISIONS, STATE, VVT unberührt (keine
personenbezogenen Daten in der Config).

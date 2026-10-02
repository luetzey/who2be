# Lernschleife C3b-1: REST für Vorschläge, Historie, Rollback, /me/memories

Karte: t_fd8f6c64 · Status: in Arbeit · Basis: origin/main 1959de89
(C3a #785 = 1d477562 enthalten). Schnitt laut PM-Entscheidung vom 2026-10-02:
Not-Aus → t_23808644 (C3b-2), `GET /memories`/counts/batch/members-Löschen →
t_238d818f (C3c), MCP `propose_memory_change` → C4 (t_889762ed).

## Completion-Condition

- Jede C3a-Service-Methode hat einen Endpunkt in `routers/memory.py`
  (propose, list_proposals, decide_proposal, history, rollback, confirm,
  reactivate, list_my_memories, triage_my, update_my, delete_my).
- Router-Tests je Endpunkt: Erfolg, Rechte (viewer/editor/admin, Agent-Token
  gesperrt bzw. human-only), Fehlergrund.
- Admin sieht über keinen Endpunkt Inhalt eines fremden Nutzergedächtnisses
  (3.1.1, Owner-Entscheidung 2026-10-01 3a).
- Rot-Proben für die kritischen Zusicherungen belegt.
- OpenAPI-Export ohne Drift, Changelog-Fragment, DoD aus CONTRIBUTING.md grün.

## Vorentschiedene Weichen

- Pfade nach ADR-0053 6.4/6.4.1; `/me/memories/{id}/…` spiegelt die
  Agentengedächtnis-Pfade. Agent-Pfad `POST /agent-memory-proposals`
  (Muster `/agent-memories`, `ctx.agent_id`, Schreib-Rate wie `save_memory`).
- Autorisierung bleibt im Service (Muster des Routers), Router ist dünn.
- `GET /me/memories` ohne `q`/`cursor`/`limit` (6.4.1): der Service kennt sie
  nicht, Ausbau gehört zu C3c.
- Kein Eingriff in Service/Repository/Modelle (Out of Scope C3a-Datenmodell).

## Schritte

1. [x] Router-Endpunkte ergänzen.
2. [x] Router-Tests `apps/api/tests/test_memory_proposal_api.py` (6 Tests).
3. [x] Rot-Proben: 6/6 rot (R1 decide ohne Personenprüfung, R2 /me ohne
   human-only, R3 Agentengedächtnis ab viewer, R4 Propose nimmt sofort an,
   R5 Vorschlagsliste ohne Besitzerbindung in der Repo-SQL, R6 /me
   workspace-weit). Quelltext danach unverändert (`git diff` leer).
4. [x] `scripts/export_openapi.py`, Changelog-Fragment, Golden-Dateien
   (`gate_inventory.json` mit Begründung je Route, `openapi_surface.json`),
   Mandantentrennungs-Probe um alle 16 neuen Routen ergänzt
   (`_memory_extras` legt aktive/Nutzer-Einträge, Vorschlag, Ereignisse an).
5. [x] DoD lokal: ruff/format/mypy grün, pytest 2774 passed / Coverage 93,21 %
   (≥85), Skip-Budget 0/0, Lizenz-Gate grün, Wirkungs-Prüfung ohne Befund.
   Einzige Rote: 8× `test_org_transfer` — auch auf main ohne diese Änderung
   rot (lokale DB, siehe Befunde). Commit, Push, PR, Review.

## Befunde

- Lokale DB trägt einen veralteten Migrationseintrag
  `0091_self_account_function.sql` (heute 0093) → `test_org_transfer` lokal
  rot, unabhängig von dieser Karte (CI nutzt frische DB).
- Rot-Proben-Falle: Backup per `shutil.move` zurück + gleich lange Mutation in
  derselben Sekunde → stale `.pyc` (mtime+Größe gleich). Wiederherstellen
  durch Neuschreiben + `__pycache__` leeren.

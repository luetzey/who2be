# Plan: Einzel-Element Delete + Export (Persona / Playbook / Resource)

Datum: 2026-06-05
Branch: `claude/tender-archimedes-AhQnt`
Status: in Arbeit

## Kontext & Lücke

Heute gibt es **keinen** echten Lösch-Pfad für die Kernelemente Persona /
Playbook / Resource — nur den Status-Workflow (`draft→review→active→inactive`,
"Retire"). Hart löschbar ist bislang nur der **Agent**
(`DELETE …/agents/{id}`, `agent_service.delete` → `agent_repository.delete`),
sowie Workspace/Org/Account (Kaskade bzw. Soft-Delete mit 30-Tage-Frist).

Export existiert nur als **DSGVO-Gesamtexport** (`GET /v1/gdpr/export`,
`GdprExportService`) — kein Einzel-Element-Export.

## Produkt-Entscheidungen (vom User bestätigt, 2026-06-05)

1. **Hard-Delete sofort** für Persona/Playbook/Resource (analog Agent — DB-Zeile
   inkl. aller Versionen weg, kein Undo).
2. **Bei bestehenden Referenzen: 409 blockieren** (kein Cascade, kein
   Null-Setzen). Antwort listet die Verwender; Nutzer muss Referenzen erst
   lösen. Nutzt die vorhandenen `/usages`-Bausteine.
3. **Einzel-Export als JSON _und_ Markdown** (Format per `?format=`).

## Referenz-Matrix (was blockiert ein Delete → 409)

| Element  | Blockiert durch (Quelle)                                            |
|----------|--------------------------------------------------------------------|
| Persona  | `agent.persona_id` (Agenten, die die Persona nutzen)               |
| Playbook | `persona_playbook` (Personas) **+** `playbook_composition` (Eltern-Composites) |
| Resource | `playbook_resource_link` (Playbooks) **+** `resource_composition` (Eltern-Composites) |

> Eigene "ausgehende" Links des zu löschenden Elements (z. B. die Playbooks, die
> _eine Persona_ selbst verlinkt) blockieren **nicht** — sie verschwinden mit dem
> Element (FK-Cascade innerhalb des Aggregats). Blockierend sind nur **eingehende**
> Referenzen anderer Aggregate.

## Architektur-Leitplanken (verbindlich)

- **RLS/tenant_scope:** Inhalts-Tabellen (`persona`/`playbook`/`resource` + deren
  `*_version` + Link-Tabellen) liegen unter RLS. Delete-Repo-Methoden **exakt
  dem Muster der bestehenden `insert`/`update`-Methoden derselben Repository-
  Klasse folgen** (`self._pool.acquire()` + `conn.transaction()`,
  workspace-scoped WHERE). Nicht erfinden — vorhandenes Muster spiegeln.
- **RBAC:** Delete verlangt `require_role(ctx, WorkspaceRole.editor)` (konsistent
  mit `agent_service.delete`). Export ist Lesen → kein `require_role`
  (Workspace-Mitgliedschaft via `get_current_workspace` genügt; Viewer dürfen
  exportieren).
- **FK-Cascade _innerhalb_ des Aggregats:** Migrations unter
  `apps/api/src/who2be_api/migrations/` prüfen — löschen `persona`/`playbook`/
  `resource` ihre `*_version`- und _ausgehenden_ Link-Zeilen via
  `ON DELETE CASCADE`? Falls **ja**: einfacher `DELETE FROM <table> WHERE id AND
  workspace_id`. Falls **nein**: Cascade-Löschung in einer Transaktion in
  korrekter Reihenfolge ODER neue Migration `0046_*` mit den fehlenden
  `ON DELETE CASCADE`. Nächste freie Nummer: **0046** (höchste vorhandene: 0045).
- **MCP bleibt unberührt:** ADR-0030 ("Kein delete über MCP") gilt weiter. Kein
  neues MCP-Tool — weder Delete noch Export.
- **Rate-Limit:** Delete `@limiter.limit(write_limit)`. Export wie ein
  Read/Write-Mischpfad — `write_limit` (durchläuft Versionen), analog GDPR-Export.

---

## WP-A — Backend: Hard-Delete (Persona/Playbook/Resource)

**Dateien (je Entity analog):**
- `repositories/{persona,playbook,resource}_repository.py`: neue Methode
  `delete(self, workspace_id, <id>) -> bool` (Muster: `agent_repository.delete`,
  Z. 194 — `DELETE … WHERE id=$1 AND workspace_id=$2`, Rückgabe ob >0 Zeilen;
  aber tenant_scope/acquire-Muster der **eigenen** Klasse verwenden). Protocol
  der Repo-Klasse erweitern.
- `repositories/usage_repository.py`: Referenz-Checks ergänzen:
  - `list_persona_usages(workspace_id, persona_id) -> list[PersonaUsage]`
    (Quelle `agent` WHERE `persona_id`).
  - `list_playbook_usages` bereits da (Personas) — **zusätzlich** Eltern-
    Composites aus `playbook_composition` einsammeln (parent-Playbook-Namen).
  - `list_resource_usages` bereits da (Playbooks) — **zusätzlich** Eltern-
    Composites aus `resource_composition`.
  - Exakte Tabellen-/Spaltennamen der Composition-Tabellen vor dem Schreiben
    verifizieren (siehe `playbook_composition_repository.py`,
    `resource_composition` im Repo).
- `services/{persona,playbook,resource}_service.py`: Methode `delete(ctx, id)`:
  1. `require_role(ctx, WorkspaceRole.editor)`
  2. Existenz prüfen (sonst 404, gleiche `_not_found()`-Konvention wie im Service).
  3. Referenzen via Usage-Repo sammeln; **wenn nicht leer → 409** mit Klartext-
     Detail + maschinenlesbarer Verwender-Liste (Muster: `_not_activatable` in
     `agent_service`, das `detail`-Format mit Aufzählung).
  4. `repo.delete(...)`; `False` ⇒ 404 (Race).
- `routers/{personas,playbooks,resources}.py`: Endpoint
  `@router.delete("/{<id>}", status_code=204)` + `@limiter.limit(write_limit)`,
  Signatur analog `delete_agent` (Router Z. 121-125). Gibt `Response(204)` zurück.
- `packages/models/`: neues Model `PersonaUsage` (Felder `agent_id`,
  `agent_name`) analog `PlaybookUsage`/`ResourceUsage`. Falls für 409 ein
  strukturierter Body gewünscht: optional `DeleteBlockedDetail`
  (`message: str`, `blocked_by: {...}`) — sonst Klartext-`detail` genügt.
  Export-Wrapper-Model (WP-B) hier mitdefinieren, falls typisiert.

**Tests** (`apps/api/tests/test_*_delete.py`, je Entity):
- 204 bei erfolgreichem Delete; danach 404 beim Get.
- 404 bei unbekannter ID.
- 403 (Viewer) — RBAC-Gate.
- 409 wenn referenziert (Persona←Agent; Playbook←Persona/Composite;
  Resource←Playbook/Composite); Body enthält die Verwender.
- Verifizieren, dass `*_version`-/ausgehende-Link-Zeilen mitverschwinden
  (kein Waisen-Datensatz).

## WP-B — Backend: Einzel-Export (JSON + Markdown)

**Service:** `services/entity_export_service.py` (neu) ODER pro-Entity-Methode.
Bevorzugt **ein** `EntityExportService(pool)` mit
`export_json(workspace_id, org_id, entity, id) -> dict` (Identitäts-Zeile + alle
Versionen, `_clean()`-Muster aus `GdprExportService._versioned`, aber auf **eine**
ID gefiltert; `tenant_scope` betreten) und
`export_markdown(...) -> str` (rendert den Body der **aktiven** Version, sonst
neueste Version; Frontmatter mit `name`, `tags`/`type`/`status`). Markdown-Body
über den **vorhandenen** Render-Pfad beziehen:
- Persona: `GET …/personas/{id}/rendered` (Render-Service).
- Playbook: `PlaybookService.render` (`…/playbooks/{id}/rendered`).
- Resource: vorhandener Resource-Render.
Render-Logik **wiederverwenden**, nicht duplizieren.

**Router:** je Entity
`@router.get("/{<id>}/export")` mit
`format: Literal["json","markdown"] = "json"` (Query). Setzt
`Content-Disposition: attachment; filename="who2be-{entity}-{id}.{json|md}"`.
- `format=json` → JSON-Body (dict), `media_type=application/json`.
- `format=markdown` → `Response(content=…, media_type="text/markdown")`.
- 404 wenn Entity fehlt.
Muster für Header/Attachment: `routers/gdpr.py` (Content-Disposition) und
`routers/agents.py` Render-Endpoint.

**Tests** (`apps/api/tests/test_*_export.py`):
- JSON: korrekte Struktur, enthält alle Versionen, keine internen Spalten
  (`workspace_id` entfernt), Attachment-Header.
- Markdown: `text/markdown`, Attachment-Header, Body enthält gerenderten Inhalt.
- 404 bei unbekannter ID; Viewer **darf** exportieren (kein 403).

## WP-C — Frontend: Delete-Buttons (Persona/Playbook/Resource)

**Dateien:**
- `features/{personas,playbooks,resources}/components/Delete{Persona,Playbook,Resource}Button.tsx`
  — Muster **exakt** `features/agents/components/DeleteAgentButton.tsx`
  (Trash2-Icon, Confirm-Dialog via `@/components/ui/*`, Loading-State, Navigation
  nach Erfolg zur Liste). **Nur** Primitives aus `@/components/ui/*` (ESLint-Gate).
- Einbau in die jeweilige **DetailPage** in einer "Danger Zone"/Aktionszeile
  (vgl. `WorkspaceSettingsPage` Danger Zone). Sichtbar wie der Agent-Delete.
- **409-Handling:** Fängt 409 ab und zeigt die Verwender (Personas/Playbooks/
  Agenten/Composites), die das Löschen blockieren — z. B. via `ErrorAlert` mit
  der Liste aus dem Response-Body. Kein blindes Retry.
- `api/client.ts`: `deletePersona(id)`, `deletePlaybook(id)`, `deleteResource(id)`
  → `DELETE …/{entity}/{id}` (Muster `deleteAgent`).
- i18n (de/en): Button-Label, Confirm-Text, 409-Blockiert-Meldung. Bestehende
  i18n-Struktur spiegeln.

**Tests** (`*.test.tsx`, Vitest): Render Button, Confirm öffnet Dialog, ruft
Client, Erfolg → Navigation, 409 → Blockier-Liste sichtbar.

## WP-D — Frontend: Export-Buttons (JSON + Markdown)

**Dateien:**
- Export-Aktion auf jeder DetailPage (Persona/Playbook/Resource) —
  Muster `AccountPage` `DataExportSection`/`onExport` (Blob-Download:
  `api.export…()` → `Blob` → `URL.createObjectURL` → `<a download>`).
  Zwei Optionen JSON / Markdown (Dropdown via `@/components/ui/*` oder zwei
  Buttons). Dateiname `who2be-{entity}-{name|id}.{json|md}`.
- `api/client.ts`: `exportPersona(id, format)` etc. →
  `GET …/{entity}/{id}/export?format=…`. JSON als Objekt/Blob, Markdown als Text.
- i18n (de/en): "Exportieren", "Als JSON", "Als Markdown".

**Tests** (Vitest): Klick ruft Client mit richtigem Format; Download-Anchor
erzeugt.

## WP-E — Doku / ADR

- **Neuer ADR** `docs/adr/ADR-00XX-single-element-delete-export.md` (nächste
  freie Nummer im `docs/adr/`-Verzeichnis ermitteln): Hard-Delete-Entscheidung,
  409-Blockier-Semantik (eingehende Referenzen), Einzel-Export JSON+Markdown,
  bewusst **kein** MCP-Delete/-Export (verweist ADR-0030).
- `CLAUDE.md` "Aktueller Stand" um den neuen Block ergänzen (durch Orchestrator
  am Ende, um Konflikte zu vermeiden).
- Falls relevant: `docs/security-findings*.md` Hinweis auf Destructive-Endpoint
  + RBAC-Gate.

---

## Reihenfolge / Parallelität

- **Stream 1 (Backend):** WP-A + WP-B + WP-E-ADR — eine Agenten-Spur
  (gemeinsame Router/Service-Dateien, daher seriell in _einem_ Agenten).
- **Stream 2 (Frontend):** WP-C + WP-D — eigene Spur (`apps/web/**`, disjunkt zu
  Backend). Entwickelt gegen den **hier spezifizierten Vertrag**; Tests mocken
  den Client (kein Live-Backend nötig).
- Streams **parallel** (disjunkte Verzeichnisse). Danach: Security-Review
  (`security-reviewer`) der Delete-Endpunkte, Voll-Verifikation, CLAUDE.md-Update,
  Commit/Push/PR durch den Orchestrator.

## Definition of Done

- **Python:** `uv run ruff check .` · `uv run ruff format --check .` ·
  `uv run mypy .` · `uv run pytest -q` — alle grün.
- **Web:** `npm run lint` · `npx tsc --noEmit` · `npm test` · `npm run build` —
  alle grün (in `apps/web/`).
- 6 neue Endpunkte (3× DELETE, 3× GET export) + Frontend-Buttons + Tests.
- Keine MCP-Änderung. Security-Review ohne offene Hochrisiko-Findings.

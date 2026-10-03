# Lernschleife C5a (Web): Warteschlange „Zur Freigabe“ (S1′)

Karte t_10a996a6 · Basis origin/main 9aba9cf8
Normen, in Rangfolge: Spec `gedaechtnisverwaltung-design-spec-2026-10.md` §2, §3, §5, §9, §11.2, §13.1/13.2/13.7, §15
→ Delta `lernschleife-design-spec-phase-c-delta-2026-10.md` S1 → Spec 2026-09-28 §1, §3 S1.

## Fertig heißt

- Nav-Eintrag „Gedächtnis“ (`/memory`, `Brain`, Gruppe Betrieb nach Feedback); `/memory` leitet auf `?tab=approval`.
- Seite mit `PageHeader`, ohne Tab-Leiste (die kommt mit C5b, Spec §11.2 „Zwischenstände“).
- S1′: zurückgehaltene Einträge oben, einzeln und ohne Checkbox; Gruppe „Dein Nutzergedächtnis“; je Agent ein Block mit
  „Alle {{count}} von {{agent}} freigeben“ (Dialog, Batch-Filter + `expected_count`, 409 → neue Zahl); Vorschläge
  (Ändern/Löschen) mit Wort-Diff und `decide`, ohne Checkbox; Auswahl ≤ 100 + Stapelleiste (Batch `ids`), Teilfehler an der Zeile.
- Suche (`q`, 300 ms) und Agent-Filter (`?agent=`), URL-synchron.
- Zustände: Laden, Fehler mit Retry, 403, leer (editor/viewer/Gedächtnis überall aus), Filter ohne Treffer, viele (Cursor 50, zurückgehaltene bis 200).
- Texte DE/EN; `legacyAuto` sagt jetzt „in „Zur Freigabe““ (Hinweis aus dem C6-Review).

## Entscheidungen (aus dem Repo belegt)

- **Dateizählung** wie Spec §11.2: Produktionsdateien ohne Locale-Naben und Tests. `api/client.ts` fehlt in der Spec-Liste,
  wird aber gebraucht (`request` ist nicht exportiert) → Spec-Ausweg: `HoldReason` wandert in `MemoryRow`.
  Produktiv: `api/types.ts`, `api/client.ts`, `app/routes.tsx`, `components/layout/AppShell.tsx`,
  `features/memory/pages/MemoryPage.tsx`, `features/memory/components/ApprovalQueue.tsx`, `components/memory/MemoryRow.tsx`,
  `features/memory/hooks/useMemoryApi.ts` = 8.
- **Lernvorschläge** stehen nicht in S1 (Delta S1). Der Server schließt sie bei `status=pending` aus; der Client filtert
  `kind=lesson` zusätzlich, und `MemoryRow` bietet für `lesson` kein Freigeben an (DB-CHECK: nie `active`).
- **Fremdes Nutzergedächtnis** (ADR 3.1.1): Der Server liefert es nie, auch nicht für admin. Der Client verwirft zusätzlich
  jede `scope=user`-Zeile, deren `subject_user_id` nicht der eigenen `user_id` entspricht (Defense in Depth); er fordert nie `group_by=subject_user_id` an.
- **Vorschläge**: `MemoryProposalRead` liefert den alten Fakt nicht (L5-Wunsch offen). Der alte Fakt kommt aus
  `GET /agents/{id}/memories` (Agentenvorschläge zielen immer aufs eigene Gedächtnis, `propose`) bzw. `GET /me/memories`.
  Fehlt er, steht nur der neue Text da, ohne Diff.
- **Agentennamen** aus `listAgents()` (MemoryRead hat keinen `agent_name`).
- **Verlauf-Button und Chevron** fehlen bis C5c (Spec §5.2).

## Bewusst nicht in C5a (Folgekarten)

- Dashboard-Banner: Linkziel `/memory?tab=approval` + Zählerquelle → Folgekarte (Karte AK 1).
- Tastaturkürzel j/k/x/a/r/e/h mit `?`-Hilfe → Folgekarte. Grund: 8-Dateien-Deckel und Laufzeit; ohne Kürzel ist alles per Tab/Enter bedienbar (2.1.1 erfüllt).

## Tests (je mit Rot-Probe)

1. Lernvorschlag: kein „Freigeben“/„Aktivieren“ (MemoryRow mit `kind=lesson`; Queue rendert ihn nicht).
2. Vorschlag „Änderung übernehmen“ → `POST /memory-proposals/{id}/decide` mit `{accept:true}`.
3. admin: eine fremde `scope=user`-Zeile in der Antwort wird nicht gerendert, kein `subject_user_id`-Request.
4. Zurückgehaltene haben keine Checkbox; Gruppenfreigabe sendet `expected_count`, 409 → Dialog bleibt mit neuer Zahl.
5. Teilfehler: fehlgeschlagene Zeile bleibt ausgewählt und zeigt den Grund.
6. a11y (axe) für MemoryPage/ApprovalQueue; AppShell-Navtest um „Gedächtnis“ ergänzt.

## Verifikation (apps/web, Node 22)

`npm run lint`, `npx tsc -b`, `npm run i18n:check`, `npm run test:coverage`, `npm run build`, `npm run license:check`;
CI `all-green` gegen den Head-SHA; Screenshots 1280/390.

## Stand

- [ ] Typen + Client
- [ ] Hook, Row, Queue, Page, Route, Nav
- [ ] Locales
- [ ] Tests + Rot-Proben
- [ ] DoD, Screenshots, PR

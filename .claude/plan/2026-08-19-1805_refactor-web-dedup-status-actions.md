# Refactoring-Lauf: Web-Duplikat-Cluster Status-/Entity-Aktionen

_Playbook: Refactoring-Lauf (Repo) · Branch: `claude/autonomous-code-agent-role-ycu6ab` · 2026-08-19_

Verhaltens-erhaltender Struktur-Umbau. Kein oeffentliches Verhalten aendert
sich; deklarierte Mikro-Abweichungen stehen in §5.

## 1. Baseline (gemessen 2026-08-19)

| Metrik | Wert |
| --- | --- |
| Duplikatsrate gesamt (jscpd, min-tokens 70) | 2,94 % · 177 Clones · 3196 Zeilen |
| Duplikat-Zeilen nur Code (ohne Seed-JSON) | 2073 |
| Python-Komplexitaet (radon, Grade ≥ C) | 6 Funktionen, max C(16) `sync_managed_builder_content` |
| Web-Tests (Vitest, lokal = CI) | 991 passed · Coverage 86,34 / 80,25 / 82,54 / 87,28 · 147 s |
| Python-Tests lokal (ohne DB — kein Docker/Postgres in dieser Umgebung) | 1315 passed, 428 skipped, 17 Env-Errors · 51 s · Coverage lokal 63 % (CI-Referenz: 1698 Tests, ~91 %) |

## 2. Hotspot-Inventar (Churn × Groesse/Komplexitaet)

Zielquadrant (hoch/hoch), Web-Cluster — **dieser Lauf**:

| Kandidat | Beleg |
| --- | --- |
| `StatusActionBar.tsx` ×4 (personas/playbooks/resources/tools, je ~126 LOC, 503 gesamt) | jscpd: 86+71+37+11 Dup-Zeilen; Diffs nur Entity-Prop, API-Call, i18n-Keys |
| `lib/status.ts` ×4 (je ~50 LOC) | identische State-Machine `ALLOWED_TRANSITIONS`/`canTransition`; `statusLabel` divergiert (s. Bug B-1) |
| `Delete*Button.tsx` ×4 (personas/playbooks/resources/tools, je ~120 LOC) | jscpd: 67 Zeilen je Paar |
| `Export*Button.tsx` ×4 | jscpd: 13 Zeilen je Paar |
| `Duplicate*Button.tsx` ×3 (agents/personas/system-prompts) | jscpd: 14–15 Zeilen je Paar |
| `features/dashboard/lib/statusLabel.ts` | woertliche Kopie von `components/version/versionStatus.ts::statusLabel` |

Geteilte Zielstruktur existiert bereits: `components/version/versionStatus.ts`
(statusLabel/statusBadgeVariant) — die Feature-Kopien sind Alt-Duplikate eines
vorhandenen Shared-Moduls. CLAUDE.md: „Geteiltes nach `@/components/` oder
`@/hooks/` hochziehen."

**Bewusst ausgelassen** (Entscheidung, kein Uebersehen):

- `SystemPromptStatusActionBar.tsx` — 158/204 Diff-Zeilen zur naechsten
  Variante, eigener Workflow; Vereinheitlichung waere Umbau, kein Dedup.
- Seed-JSON-Sidecars DE/EN (`repositories/*.json`) — Daten, erwartete Paare.
- WorkArea-/KB-Dateien (`wa_tables.py` 897 LOC, `engine.py` 864 LOC etc.) —
  jung (3–6 Commits), frisch refaktoriert (Stufen 1–3, 2026-08-19).
- `workspace_repository.py` (Churn 18, 1089 LOC, C(16)) und Service-Duplikate
  `persona_service ↔ resource_service ↔ playbook_service` (72+29+26 Dup-Zeilen)
  — Sicherheitsnetz ist DB-gebunden und laeuft nur in CI; in dieser Umgebung
  (kein Docker/Postgres) nicht lokal verifizierbar → Folgelauf in einer
  Umgebung mit DB, nicht ungesichert anfassen.
- Detail-Page-Strukturduplikate (`ResourceDetailPage ↔ ToolDetailPage`, 87
  Zeilen) — groesserer Seitenumbau, eigener Lauf nach diesem.
- MCP `tools/kb.py ↔ tools/tables.py` (30 Zeilen) — klein, Folgelauf.
- Komplex-aber-stabil (Grade C, niedriger Churn): `verify_supabase_jwt`,
  `VersionStatusService._transition`, `PersonaService.render` — stabil, kein
  Umbau ohne Anlass.

## 3. Design-Weiche (drei Optionen)

Die per-Feature-Duplikate tragen Alt-Kommentare „bewusst dupliziert wegen
Cross-Feature-Lint-Regel". Die Regel verbietet aber nur Feature→Feature-Deep-
Imports; `@/components/` ist der sanktionierte geteilte Ort, und
`components/version/` praktiziert das bereits.

- **A — Hochziehen nach `components/version/`** (StatusActionBar als
  parametrisierte Komponente + State-Machine in `versionStatus.ts`):
  beseitigt ~1000 Dup-Zeilen, folgt CLAUDE.md-Konvention, ein Testort.
  Trade-off: Feature-Seiten haengen an einer Shared-Komponente (bewusste
  Kopplung an eine stabile Versions-UI-Insel).
- **B — Duplikate behalten, nur Drift synchronisieren:** minimales Risiko,
  aber der naechste Content-Typ kopiert wieder ~350 Zeilen; die Drift ist
  bereits eingetreten (Bug B-1, i18n-Key-Wildwuchs).
- **C — Nur State-Machine teilen, Bars pro Feature lassen:** halbiert den
  Gewinn, laesst die groessten Clones (86 Zeilen/Paar) stehen.

**Empfehlung: A** — die Repo-Konvention hat die Alt-Entscheidung ueberholt;
`components/version/versionStatus.ts` ist der praezedente Beleg. Wird im PR
zur Review gestellt (Check-in); DECISIONS.md-Eintrag folgt mit dem Merge.

## 4. Wellen & Scope-Vertrag

### Welle 1 — Status-State-Machine + StatusActionBar (≤ 20 Dateien)

Anfassen:

- `components/version/versionStatus.ts` (erweitern: `VERSION_STATUSES`,
  `ALLOWED_TRANSITIONS`, `canTransition`)
- `components/version/StatusActionBar.tsx` (neu; Props: `onTransition`
  -Callback, i18n via `common:statusBar.*`) + ein konsolidierter Test
- Loeschen: `features/{personas,playbooks,resources,tools}/components/StatusActionBar.tsx`
  + deren 4 Tests, `features/{personas,playbooks,resources,tools}/lib/status.ts`,
  `features/dashboard/lib/statusLabel.ts`
- Umstellen: `PersonaDetailPage.tsx`, `PlaybookDetailPage.tsx`,
  `ResourceDetailPage.tsx`, `ToolDetailPage.tsx`, `DashboardPage.tsx`
- `i18n/locales/de.json` + `en.json`: `common.statusBar.*` neu, per-Feature
  `statusBar`-/`actions`-Duplikat-Keys entfernen (nur die, die dadurch
  ungenutzt werden)
- Ausnahme B-1: `statusLabel` fuer Playbooks bleibt vorerst lokal
  (hartkodierte Labels = Ist-Verhalten; Fix laeuft als eigenes Issue)

### Welle 2 — Delete-/Export-/Duplicate-Buttons (≤ 20 Dateien)

Anfassen:

- `components/version/` (oder passender: `components/entity/`):
  `EntityDeleteButton`, `EntityExportButton`, `EntityDuplicateButton` (je neu,
  parametrisiert) + konsolidierte Tests
- Loeschen: die per-Feature-Kopien (Delete ×4, Export ×4, Duplicate ×2–3)
  + deren Tests
- Umstellen: die 4 Detail-Pages (bereits in Welle 1 angefasst — datei-disjunkt
  zu Welle 1 ist hier nachrangig gegenueber „eine Transformation pro Commit";
  Wellen laufen sequenziell im selben Branch, je Welle ein Commit mit gruener
  Suite)

### Nicht anfassen (harte Liste)

- `apps/api/**`, `apps/mcp/**`, `packages/**` (kein Python in diesem Lauf)
- `features/system-prompts/**` (eigener Workflow, s. §2)
- `features/{agents,auth,billing,dashboard,feedback,legal,settings,workarea}/**`
  ausser explizit gelistete Dateien (`DashboardPage.tsx`)
- `api/types.ts`, `api/client.ts`, `app/routes.tsx`, `styles/globals.css`
- Alle Konfigs (eslint/tsconfig/vite/CI), alle Coverage-Floors
- Seed-JSON, Migrationen, Doku ausser STATE/DECISIONS-Pflege am Ende

### Messbare Completion-Condition (/goal)

1. `npm run lint` + `npx tsc --noEmit` + `npm run test:coverage` +
   `npm run build` gruen (lokal = CI-Kommandos), Coverage ≥ Floors
   (80/79/75/80), keine geloeschten/abgeschwaechten Tests.
2. jscpd (gleiche Parameter) zeigt fuer die Cluster StatusActionBar +
   Delete/Export/Duplicate 0 Clone-Paare; Code-Dup-Zeilen sinken um ≥ 800.
3. Diff enthaelt ausschliesslich Scope-Listen-Dateien (Gegenprobe vor PR).
4. PR offen (Draft) mit Metrik-Tabelle; Bugs als Issues verlinkt.

## 5. Deklarierte Mikro-Abweichungen (im PR benannt)

- EN-String-Konsolidierung: `personas` „Promote not possible" →
  einheitlich „Cannot promote" (Mehrheitsfassung; DE ueberall identisch).
- Sonst keine sichtbaren Aenderungen; B-1 (Playbook-Status-Labels
  hartkodiert deutsch) wird NICHT in diesem Lauf gefixt.

## 6. Funde ausserhalb des Scopes (→ Issues)

- **B-1 (Bug):** `features/playbooks/lib/status.ts::statusLabel` hartkodiert
  deutsche Labels; im EN-Locale zeigt die Playbook-UI deutsche Status.
- **T-1 (Test-Hygiene):** `apps/api/tests/test_resource_slug_children_duplicate.py`
  errort ohne erreichbares Postgres (ConnectionRefused) statt zu skippen wie
  die uebrige DB-Suite.

## 7. Status

- [x] Phase 1 Hotspot-Inventar + Baseline
- [x] Phase 2 Sicherheitsnetz: Web-Suite vollstaendig lokal, je Kopie ein Test
- [x] Phase 3 Plan + Scope-Vertrag (dieses Dokument)
- [ ] Welle 1 umgesetzt, Suite gruen, Commit
- [ ] Welle 2 umgesetzt, Suite gruen, Commit
- [ ] Phase 5 Konsolidierung: volle DoD, Metrik-Tabelle, Diff-Gegenprobe, PR + Issues, STATE/DECISIONS

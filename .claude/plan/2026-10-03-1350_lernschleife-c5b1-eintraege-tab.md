# Plan: Lernschleife C5b-1 – Tab „Einträge“ auf /memory

Karte t_3d6356e5 · Basis origin/main 3d0955f3 · Spec gedaechtnisverwaltung-design-spec-2026-10.md §4, §6.1–6.5, §6.7, §9, §11.2, §13.3, §14, §15
Schnitt: PM-Entscheidung A (2026-10-03). Agent-Seite = C5b-2 (t_7fbb5c2b), Detail-Sheet/Verlauf/Rollback/Not-Aus = C5c (t_7da03826).

## Completion-Condition

- `/memory?tab=entries` zeigt für editor+ die Liste über `GET /memories` (scope=agent) mit Facetten aus `GET /memories/counts`, Suche, Sortierung newest|oldest, Cursor-Seiten.
- Stapel über `POST /memories/batch` (ids), Ergebnis je Eintrag an der Zeile; Filter-Stapel nur mit `expected_count`, 409 → Dialog bleibt mit neuer Zahl.
- „Bestätigen“ und „Wieder aktivieren“ als Zeilenaktion; keine toten Knöpfe.
- Viewer: kein Tab „Einträge“, `?tab=entries` fällt still auf `approval` zurück; alle Listen-Aufrufe tragen `scope=user`.
- Vitest, Lint, tsc, i18n-Check grün; scroll-guard um /memory?tab=entries erweitert und grün (Desktop + mobile Projekte); Screenshots 1280/390 hell+dunkel mit scrollWidth ≤ clientWidth; Rot-Probe je Zusicherung.

## Dateien (Zählregel PM: alles außer dieser Plan-Datei, Grenze 12)

1. `apps/web/src/features/memory/pages/MemoryPage.tsx` – Tab-Leiste (?tab-Sync, Rechte), Zähler, Einträge-Tab-Verdrahtung
2. `apps/web/src/components/memory/MemoryList.tsx` (neu) – Liste, Zeile, Stapelleiste, Filter-Stapel-Dialog
3. `apps/web/src/components/memory/MemoryFacets.tsx` (neu) – Facettenspalte ≥ lg, Filter-Sheet < lg, Chips
4. `apps/web/src/features/memory/hooks/useMemoryApi.ts` – `useMemoryEntries`, URL↔Filter, gemeinsame Grund-Texte
5. `apps/web/src/features/memory/components/ApprovalQueue.tsx` – nutzt die gemeinsamen Grund-Texte (keine zweite Kopie)
6. `apps/web/src/api/client.ts` – `confirmAgentMemory`, `reactivateAgentMemory`
7./8. `apps/web/src/i18n/locales/{de,en}.json`
9. `apps/web/src/features/memory/pages/MemoryPage.test.tsx` – Einträge-Tests
10. `apps/web/src/api/client.contract.test.ts` – neue Pfade im Drift-Check
11. `apps/web/e2e/scroll-guard.spec.ts` – /memory?tab=entries
12. `changelog.d/t-3d6356e5-memory-entries-tab.added.md`

Kein `MemoryEntriesTab.tsx`: die Tab-Verdrahtung ist klein und liegt in `MemoryPage.tsx`; so bleibt Platz für die Grund-Texte ohne Duplikat.

## Vorentschiedene Weichen (mit Beleg)

- **Facetten = Einzelauswahl je Gruppe** statt Mehrfachauswahl (Spec §6.2). Beleg: `MemoryFilter` (packages/models/src/who2be_models/memory.py:626) und `memory_filter()` (routers/memory.py:301) nehmen je Feld genau einen Wert. Mehrfachauswahl bräuchte `status[]` usw. in der API → Folgepunkt für @pm. Umsetzung: Radiogruppe je Facette mit „Alle“ als erstem Wert.
- **„Abgelehnt“ ist in der Standardansicht enthalten** (Spec §6.2 will es standardmäßig aus). Ohne Mehrfach-/Ausschlussfilter könnte der Client abgelehnte Zeilen nur selbst ausblenden; dann stimmten Liste, Gesamtzahl und Facettenzahlen nicht mehr überein (Spec §4: Zähler nie aus der geladenen Teilmenge). Zeile zeigt Status als Punkt + Wort. Folgepunkt wie oben.
- **Sortierung nur Neueste/Älteste** – `MemoryListSort` kennt nur newest|oldest; die Karte nennt genau diese zwei.
- **Filter-Stapel**: „Alle {{count}} bestätigen“ erscheint nur bei aktivem Zustand „Unbestätigt“ (die Menge ist dann genau die bestätigbare); Dialog sendet `filter` + `expected_count`, 409 → neue Zahl, erneute Bestätigung (Muster C5a GroupApproveDialog).
- **Status „Zu Fall geworden“** bleibt bis D2 aus der Facette (Spec §6.2).
- **„bestätigt von {{name}}“** entfällt: `MemoryRead` trägt nur `confirmed_by` (UUID), keinen Namen.
- Tabwechsel per Klick setzt die Filter zurück (nur `tab` bleibt); Deep-Links mit Filtern bleiben gültig.

## Schritte

1. client.ts + Contract-Test (confirm/reactivate) – [x]
2. useMemoryApi: URL↔Filter, `useMemoryEntries` (Liste + counts parallel, Cursor, reload), `useReasonText` hierher – [x]
3. MemoryFacets – [x]
4. MemoryList (Zeile, Aktionen, Stapel, Teilfehler, Filter-Stapel) – [x]
5. MemoryPage Tab-Leiste + Zähler + Viewer-Fallback – [x]
6. i18n de/en – [x]
7. Tests inkl. Rot-Proben – [x]
8. scroll-guard + Screenshots 1280/390 hell/dunkel – [x]
9. Changelog, DoD-Kommandos (CONTRIBUTING) – [x]
10. Push, danach PR (getrennt) – [x]

## Review-Runde 1 → Nacharbeit (Reviewer-Kommentar 709, PM-Entscheidungen)

1. e2e-mobile rot (tablet-ipad-gen-7, scroll-guard C5b-1): gemessen wurde mitten im Slide-in (`w2b-anim-sheet-right`, x≈810 bei 810 px). Fix: auf `getAnimations().finished` warten, Box per `toPass` in Endlage prüfen (x, rechte und untere Kante). Lokal gegen eigenen Vite-Proxy auf Stack w2b327: alte Fassung 3/3 rot (1191 > 811), neue Fassung 8/8 grün auf allen vier Profilen; Rot-Probe Sheet `w-[1000px]` → rot (x = −190). – [x]
2. Screenshots 1280/390 hell+dunkel inkl. Filter-Sheet bei 390, je mit scrollWidth = clientWidth (1280/1280, 390/390), als Artefakt (nicht im Repo). – [x]
3. Zurückgehaltene pending-Zeilen (holdCauseOf ≠ null): kein „Freigeben“ mehr, stattdessen Link „In der Warteschlange entscheiden“ → `?tab=approval&agent=<id>` (PM: Variante a). Test + Rot-Probe (Bedingung entfernt → rot). – [x]
4. Tab-Zähler „Einträge“ = dieselbe Menge wie die ungefilterte Liste (inkl. rejected), Test + Rot-Probe. Abweichungen von Spec §6.2 im PR-Body; API-Folgepunkt legt @pm an. – [x]
5. Nit `text-destructive-text`: Die Klasse existiert nicht; `text-destructive` liest bereits `--destructive-text` (globals.css:26, Audit A6) = das Text-Token aus §6.5. Kommentar im Code. – [x]
Nebenbei aus den Screenshots: Stapelleiste lag 1 rem über der Sidebar (16rem statt w-60 = 15rem), in MemoryList und ApprovalQueue korrigiert; „1240 Einträge zeigen“ → mit Tausenderpunkt.

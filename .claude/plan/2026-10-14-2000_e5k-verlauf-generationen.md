# E5k: Verlauf (Generationen) im Tab „Weiterentwicklung“

Karte t_8f9416d1 · Spec `phase-e-web-neuschnitt-2026-10.md` §3.6, §7.1 Zeile E5k · Weiche N2 a (Dossier-Block `generations`, E1 #957).

## Fertig heißt

editor/admin sehen im Tab `?tab=evolution` unter „Reviews“ den Abschnitt „Verlauf“: eine Zeitleiste der
Aktivierungen der Bausteine (neueste oben, 5 sichtbar, „Ältere Generationen zeigen“ +10). viewer sieht ihn nicht.

## Leitplanken (PM-Kommentar 2026-10-14)

1. Eine Quelle: Reihenfolge, `from_version`/`to_version`, `verdict`, `measure_ids` (leer = direkt geändert),
   `shared_agent_count`, Zustand und Termin der Änderung (`DossierMeasure.state`/`follow_up_at`) kommen vom
   Server. Lokal bleibt nur der Kalendertag „fällig?“ (`followUpStatusOf`, wie E5g). Kein Sortieren,
   kein Verknüpfen über `entity_id`.
2. IDs: Links nur auf Änderungen, die der Server im selben Dossier dieses Agenten liefert (`measures`) und deren
   `id`/`session_id` UUIDs sind; `encodeURIComponent`. Antwort mit fremder `agent_id` wird verworfen.
3. Begrenzt: eine Anfrage `getDossier(agentId)` beim Öffnen, je Klick höchstens eine weitere mit
   `generations_next_cursor`. Seite = `DOSSIER_GENERATIONS_LIMIT` = 15 (Server). Keine Anfrage je Generation.
4. Je Regel eine Mutation, axe je Zustand (laden, leer, Fehler, Liste) in eigenem `it()`.

## Bewusst nicht

- „Rückmeldungen je 100 Nutzungen a → b“ (§3.6 optional): bräuchte je Generation `getFollowUp` (N+1) oder
  lokales Zusammensetzen aus `elements.versions` (zweite Quelle). Entfällt ohne Platzhalter.
- Fortlaufende Nummer (Spec: keine).

## Dateien (7 ≤ 8)

1. `apps/web/src/features/evolution/components/EvolutionTimeline.tsx` (neu, Spec-Pfad; der Tab importiert
   `features/evolution/lib` schon, das Cross-Feature-Gate gilt nur zwischen Features)
2. `apps/web/src/features/evolution/components/EvolutionTimeline.test.tsx` (neu)
3. `apps/web/src/components/evolution/AgentEvolutionTab.tsx` (einbinden)
4. `apps/web/src/components/evolution/AgentEvolutionTab.test.tsx` (Mock `getDossier`, viewer fragt nicht)
5. `apps/web/src/i18n/locales/de.json`
6. `apps/web/src/i18n/locales/en.json`
7. `changelog.d/t-8f9416d1-evolution-timeline.added.md`

N2 a: `api/types.ts` hat `DossierGeneration` schon (E1), daher keine Änderung dort.

## Verifikation

`npm run lint`, `npx tsc -b`, `npm run test:coverage`, `npm run build`, `npm run i18n:check`,
`uv run python scripts/changelog_fragments.py check`; Fotos 1280/390 hell/dunkel editor + viewer mit measure.json.

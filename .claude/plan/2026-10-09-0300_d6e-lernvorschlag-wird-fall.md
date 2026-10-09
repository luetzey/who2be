# D6e – Lernvorschlag wird Fall (convert) im Gedächtnis-Sheet (Karte t_d6ba751d)

Basis: origin/main 6aa50df4 (D6d gemergt). Spec: Delta Phase D, S6 (Einstiege,
„Zitat statt Vorbelegung der Felder“, Absenden, Erfolg, Fehler
`memory_not_convertible`), „Gedächtnis-Anschluss“, Barrierefreiheit
(Zitat-Block), Zuschnitt D6e. API: `POST /agents/{agent_id}/memories/{id}/convert`
(Body `CaseConvertRequest` = Fall-Felder ohne `agent_id`, Antwort `CaseRead`).

## Dateien (Budget 8)
1. apps/web/src/api/client.ts (`convertMemory`, `promoteFeedback`)
2. apps/web/src/components/memory/MemoryDetailSheet.tsx
3. apps/web/src/components/memory/MemoryDetailSheet.test.tsx
4. apps/web/src/components/cases/ReportCaseForm.tsx
5. apps/web/src/components/cases/ReportCaseForm.test.tsx
6. apps/web/src/i18n/locales/de.json
7. apps/web/src/i18n/locales/en.json
8. changelog.d/t-d6ba751d-memory-convert.added.md

## Schritte
1. `ReportCaseFlow` bekommt `origin?: ReportCaseOrigin` (lesson | feedback |
   pattern) und `onCreated?(created)`. Mit `origin` steht über den Feldern der
   Block „Ausgangspunkt“: `figure` > `blockquote` (Zitat, gekürzt auf 3 Zeilen
   unter `md`, „Mehr anzeigen“) + `figcaption` mit Quelle und Datum. Felder
   bleiben leer; „In ‚Erwartet‘ übernehmen“ (`ghost`, 44 px) mit
   `aria-describedby` auf das Zitat kopiert den Text ins Feld „Erwartet“.
2. Absendeweg je Herkunft: lesson → `convertMemory` (ohne `agent_id`),
   feedback → `promoteFeedback`, pattern → `createCase`. Knopf „Fall anlegen“
   bei lesson/feedback, sonst „Fall melden“ (Spec S6 „Absenden“).
   `memory_not_convertible` → Spec-Text, Eingaben bleiben.
3. Neuer Auslöser `CaseFromOriginDialog`: immer Dialog (unter `sm` ohnehin
   Vollbild). Die Melden-Seite `/feedback/cases/new` bleibt beim
   Standard-Einstieg; für convert bräuchte sie Route und State (Budget), das
   Sheet bleibt dafür offen, wie die Spec es für den Erfolg verlangt.
4. `MemoryDetailSheet`: Aktion `default` „Fall daraus machen“ vor „Ablehnen“,
   nur bei `kind=lesson`, `status=pending`, Rolle ab editor. Nach Erfolg
   bleibt das Sheet offen, der Eintrag steht auf `converted` mit
   `converted_case_id`, Verlauf und Liste laden neu, Link „Zum Fall“ bekommt
   den Fokus. Keine Zeilenaktion in `MemoryRow`.
5. Tests: Sichtbarkeit je Rolle/Art/Status, Reihenfolge vor „Ablehnen“,
   Übernehmen-Knopf, Erfolg, Fehler, Varianten feedback/pattern, Client-Pfade,
   axe. Merkposten D6a (Grenze „Getan“ 4 000) ist seit D6c auf main getestet
   (ReportCaseForm.test.tsx), Rot-Probe hier nur zur Bestätigung.

## Verifikation
`npx tsc -b`, `npx vitest run`, `npm run lint`, `npm run i18n:check`;
Screenshots 1280/390 hell/dunkel + measure.json.

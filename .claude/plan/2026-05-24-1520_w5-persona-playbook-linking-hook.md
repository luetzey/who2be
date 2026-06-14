# W5 — Persona↔Playbook-Verknuepfung im Persona-Detail

> Task: [TASK-269](https://www.notion.so/36abe5372ab88143bcded1f40817e9a6) ·
> Milestone: MS-1 · Branch: `claude/pensive-euler-UAAsq`.

## Ziel / Completion-Condition

- Persona-Detail zeigt die per `GET /v1/personas/{id}/playbooks` verknuepften
  Playbooks und erlaubt eine Multi-Select-Aenderung; Speichern setzt die
  Liste atomar via `PUT /v1/personas/{id}/playbooks`.
- Die Logik wandert aus dem `PersonaDetailPage.tsx`-Container in einen
  Hook `usePersonaPlaybooks(personaId)` — Page bleibt dumm, Hook kapselt
  Loading-/Save-Status + Toggle-API.
- Vitest deckt **Save-Flow** ab: zwei Playbooks verfuegbar, einer
  vorher verknuepft, User toggelt, klickt Speichern, PUT-Body enthaelt
  die neue ID-Liste.

**Transkript-Check:** `npm run lint`, `npx tsc --noEmit`, `npm test` gruen.

## Guardrails

- Disjunkt zu W3/W4: nur `PersonaDetailPage.tsx` und der neue Hook.
  Keine API-Client-Aenderung (Endpoints existieren bereits seit W1-Setup).
- TS strict, kein `any`.

## Aktueller Stand

- `PersonaDetailPage.tsx` enthaelt bereits den kompletten Linking-Code
  inline:
  - Lokaler State `allPlaybooks` (via `api.listPlaybooks()`) und
    `linkedIds` (via `api.listPersonaPlaybooks`).
  - `toggleLink` + `handleSaveLinks` (ruft `api.setPersonaPlaybooks`).
  - Wird im selben `Promise.all` mit Persona/Versions geladen.
- API-Client hat `listPersonaPlaybooks` + `setPersonaPlaybooks` bereits.
- Kein bestehender Hook fuer dieses Aggregat.

## Schritte

1. **`hooks/usePersonaPlaybooks.ts`** neu — Hook mit Signatur
   `usePersonaPlaybooks(personaId: string | undefined)`. Innenleben:
   - `playbooks: Playbook[]` (alle verfuegbaren),
   - `linkedIds: string[]` (vorab gemerkter Soll-Stand fuer den Save),
   - `loading: boolean`, `error: string | null`, `saving: boolean`,
     `status: string | null`,
   - `toggle(id: string): void`, `save(): Promise<void>`,
     `reset(): void` (rollback auf Server-Stand).
   - Lade-Logik via `Promise.all([listPlaybooks(), listPersonaPlaybooks(id)])`
     im `useEffect`. Bei undefined-id: idle.
   - `save` ruft `setPersonaPlaybooks(id, linkedIds)` und setzt `status`.
2. **`PersonaDetailPage.tsx`** entschlackt:
   - State `allPlaybooks` + `linkedIds` + `toggleLink` + `handleSaveLinks`
     raus.
   - `Promise.all` reduziert sich auf Persona + Versions.
   - Linking-Block ruft den Hook und rendert die Liste/Toggles/Save-
     Button daraus.
   - Bestehende Statusmeldungen ("Verknuepfungen gespeichert.") bleiben
     erhalten, kommen jetzt aus dem Hook-`status`.
3. **`pages/PersonaDetailPage.test.tsx`** erweitern — bestehender Version-
   Bump-Test bleibt; neuer Test `'verknuepft Playbooks via PUT'`:
   - Mocks fuer Persona, Versions, `GET /v1/playbooks` (zwei Items),
     `GET /v1/personas/p1/playbooks` (eines vorher verknuepft).
   - User toggelt den zweiten Eintrag (per Checkbox), klickt
     "Verknuepfungen speichern".
   - Erwartung: PUT auf `/v1/personas/p1/playbooks` mit beiden IDs im
     Body.
4. **Verify:** `npm run lint && npx tsc --noEmit && npm test`.

## Betroffene Dateien

- NEU `apps/web/src/hooks/usePersonaPlaybooks.ts`
- AENDERN `apps/web/src/pages/PersonaDetailPage.tsx`
- AENDERN `apps/web/src/pages/PersonaDetailPage.test.tsx`

## Risiken

- Der bestehende Version-Bump-Test mockt aktuell `GET /v1/personas/p1/playbooks`
  und `GET /v1/playbooks` mit `[]`. Bleibt nach dem Refactor weiter
  gueltig — der Hook setzt die Mocks genauso ab. Sicherstellen, dass die
  Mock-Signaturen weiter angesprochen werden.
- `loading`-State im Hook darf das Detail-Rendering nicht blockieren:
  Persona-Detail kann angezeigt werden, selbst wenn das Playbook-Listing
  noch laedt — separater `loading`-Indikator unter der Persona-Section.

## Doku-Log

Nach Verify: Notes-Eintrag auf Projektseite + Pointer. Task -> Review.

# W3 — Persona-Editor + Versionsliste

> Task: [TASK-267](https://www.notion.so/36abe5372ab881ab9785d664ce70b1db) ·
> Milestone: MS-1 · Branch: `claude/pensive-euler-UAAsq`.

## Ziel / Completion-Condition

- `/personas` listet vorhandene Personas mit Link auf Detail + Link auf
  `/personas/new`.
- `/personas/new` legt eine neue Persona an, redirected nach Erfolg auf
  `/personas/:id`.
- `/personas/:id` zeigt aktuelle Version, Editor (PUT erzeugt neue Version)
  und Read-only-Versionsliste — bleibt bestehend, wird nur entschlackt.
- Vitest deckt **Create-Flow** (POST /v1/personas → Redirect) und
  **Version-Bump-Flow** (PUT → neue Versionszahl in der Liste) ab.

**Transkript-Check:** `npm run lint`, `npx tsc --noEmit`, `npm test` gruen.

## Guardrails

- Disjunkt zu W4 (Playbooks) und W5 (Persona↔Playbook-Hook). **W5-Code in
  PersonaDetailPage bleibt drin** (er existiert bereits) — wird in W5 in
  einen Hook `usePersonaPlaybooks` extrahiert. Hier nicht anfassen, damit
  W5 sauber landen kann.
- TS strict, kein `any`, funktionale Komponenten + Hooks.

## Aktueller Stand

- `PersonasPage.tsx`: zeigt Liste + **inline Create-Formular** (Name,
  Description, System-Prompt). Soll: Create-Formular raus, Link auf
  `/personas/new`.
- `PersonaDetailPage.tsx`: Edit-Formular + Version-Liste + Playbook-Linking
  bereits vorhanden — bleibt unveraendert.
- `usePersonas.ts`: liefert `tokens, loading, error, reload` analog
  `useTokens`. Brauchbar wie er ist.
- `PersonasPage.test.tsx`: rendert die Liste mit einer Persona — Test
  muss nur ggf. den Provider mitwrappen (W1 hat das schon).

## Schritte

1. **`pages/PersonaNewPage.tsx`** anlegen — Formular (Name, Description,
   System-Prompt, Traits-Liste komma-separiert), `api.createPersona` →
   `navigate(`/personas/${created.id}`)`. Fehler ueber `role="alert"`.
2. **`pages/PersonasPage.tsx`** umbauen — Create-Formular entfernen,
   stattdessen Link "Neue Persona" auf `/personas/new`. Liste bleibt.
   Nav-Link "API-Tokens" zur W2-Seite (`/settings/tokens`) ergaenzen
   (klein, gehoert zur PersonasPage-Header-Nav).
3. **`App.tsx`** — Route `/personas/new` hinter `RequireAuth` einhaengen.
   **Wichtig:** vor `/personas/:id` definieren, damit der String-Match
   `:id` nicht "new" frisst (React Router v6 matched strikt, aber zur
   Sicherheit Reihenfolge).
4. **`pages/PersonasPage.test.tsx`** anpassen — alter Test wirft mit dem
   geaenderten Markup ggf. nicht. Behalten + sicherstellen, dass die
   Persona angezeigt wird; alten Form-Anteil aus dem Test droppen.
5. **`pages/PersonaNewPage.test.tsx`** neu — Create-Flow: User fuellt
   das Formular, klickt "Anlegen", `fetch` wird mit POST + JSON-Body
   aufgerufen, anschliessend Redirect.
6. **`pages/PersonaDetailPage.test.tsx`** neu — Version-Bump-Flow:
   initiale Liste hat 1 Version, User aendert System-Prompt, klickt
   Speichern, der PUT-Aufruf laeuft, die anschliessende Liste hat 2
   Versionen. Mock-Strategie: `fetch`-Sequence (getPersona, listVersions,
   listPlaybooks, listPersonaPlaybooks, **PUT**, getPersona-2,
   listVersions-2, ...).
7. **Verify-Lauf:** `npm run lint && npx tsc --noEmit && npm test`.

## Betroffene Dateien

- NEU `apps/web/src/pages/PersonaNewPage.tsx`
- NEU `apps/web/src/pages/PersonaNewPage.test.tsx`
- NEU `apps/web/src/pages/PersonaDetailPage.test.tsx`
- AENDERN `apps/web/src/pages/PersonasPage.tsx`
- AENDERN `apps/web/src/pages/PersonasPage.test.tsx`
- AENDERN `apps/web/src/App.tsx`

## Risiken

- Der bestehende `PersonaDetailPage` enthaelt schon W5-Code (Playbook-Linking).
  W3 lasse ich diesen Teil unangetastet — extrahieren in `usePersonaPlaybooks`
  ist W5-Job. Mein Detail-Page-Test mockt die noetigen Endpoints mit (sonst
  haengt der Test im `Promise.all`).
- Routenreihenfolge `/personas/new` vor `/personas/:id`. React Router v6
  matched die spezifischste Route automatisch — Reihenfolge ist nicht
  semantisch noetig, aber zur Klarheit aufsteigend von spezifisch zu
  generisch.

## Doku-Log

Nach Verify: Notes-Eintrag + Pointer. Task -> Review.

# W4 — Playbook-Editor + Tag-/Trigger-Felder + Versionsliste

> Task: [TASK-268](https://www.notion.so/36abe5372ab881a9a08fe8899fe398a1) ·
> Milestone: MS-1 · Branch: `claude/pensive-euler-UAAsq`.

## Ziel / Completion-Condition

- `/playbooks` listet vorhandene Playbooks, zeigt Tag-Chips und
  Trigger-Auszug; **Filtert client-seitig** nach Tag und Trigger.
- `/playbooks/new` legt ein Playbook an (Name, Typ, Beschreibung, Body,
  Tags, Triggers) und redirected nach Erfolg auf `/playbooks/:id`.
- `/playbooks/:id` zeigt aktuelle Version + Editor (PUT erzeugt neue
  Version) + Read-only-Versionsliste — bleibt bestehend, nur Tag-Chip-
  Darstellung als kleine Verbesserung.
- Vitest deckt **Create-Flow** und **Version-Bump-Flow** ab.

**Transkript-Check:** `npm run lint`, `npx tsc --noEmit`, `npm test` gruen.

## Guardrails

- Disjunkt zu W3 (Personae) und W5 (Persona↔Playbook-Hook).
- Server-seitiger Filter wandert raus aus `usePlaybooks` — Roadmap MS-1
  schreibt **client-seitig**; server-seitiger Filter wird in MS-4 B3
  separat (MCP-Smoke gegen Hetzner) verifiziert.
- Tag-Chips = minimal: Anzeige als kleine `<span>`-Liste in Liste +
  Detail. Keine eigene Tag-Komponente, keine Autocompletion. Eingabe
  bleibt kommagetrennt — "Funktion vor Schoenheit" / "minimal-funktional".
- TS strict, kein `any`.

## Aktueller Stand

- `usePlaybooks(tag, trigger)` ruft `listPlaybooks({ tag, trigger })` —
  server-seitig.
- `PlaybooksPage.tsx`: Filter-Inputs + inline Create-Formular.
- `PlaybookDetailPage.tsx`: Edit + Versions sind bereits vollstaendig.
- Keine Tests fuer Playbook-Seiten (nur PersonasPage, PersonaDetail,
  PersonaNew, SettingsTokens, LoginPage, App, useAuthToken, api/client).

## Schritte

1. **`hooks/usePlaybooks.ts`** — auf parameterlos umstellen (`useTokens`-
   analog). Liefert `playbooks, loading, error, reload`. Filter raus.
2. **`pages/PlaybookNewPage.tsx`** anlegen — Formular (Name, Typ,
   Beschreibung, Body, Tags kommagetrennt, Triggers), `api.createPlaybook`
   -> `navigate(`/playbooks/${created.id}`)`.
3. **`pages/PlaybooksPage.tsx`** umbauen:
   - Inline-Create-Form raus.
   - Client-seitiger Filter (Tag-substring + Trigger-substring,
     case-insensitive) ueber `useMemo`.
   - Liste pro Eintrag: Name (Link), Typ, `v<n>`, Tag-Chips.
   - Header-Nav: `Neues Playbook`, `Zu den Personae`, `API-Tokens`.
4. **`pages/PlaybookDetailPage.tsx`** — minimaler Touch: aktuelle Tags
   zusaetzlich als Chip-Liste anzeigen (Lesehinweis ueber dem Edit-Feld).
   Sonst unveraendert.
5. **`App.tsx`** — Route `/playbooks/new` vor `/playbooks/:id`.
6. **Tests:**
   - `pages/PlaybookNewPage.test.tsx` — Create-Flow: POST /v1/playbooks +
     Navigate auf Detail.
   - `pages/PlaybookDetailPage.test.tsx` — Version-Bump: initial v1, User
     aendert Body, klickt Speichern, danach v2 in Liste sichtbar.
     Mock-Strategie analog `PersonaDetailPage.test.tsx`.
7. **Verify:** `npm run lint && npx tsc --noEmit && npm test`.

## Betroffene Dateien

- AENDERN `apps/web/src/hooks/usePlaybooks.ts`
- AENDERN `apps/web/src/pages/PlaybooksPage.tsx`
- AENDERN `apps/web/src/pages/PlaybookDetailPage.tsx` (nur Tag-Chip-Anzeige)
- AENDERN `apps/web/src/App.tsx`
- NEU `apps/web/src/pages/PlaybookNewPage.tsx`
- NEU `apps/web/src/pages/PlaybookNewPage.test.tsx`
- NEU `apps/web/src/pages/PlaybookDetailPage.test.tsx`

## Risiken

- `usePlaybooks(tag, trigger)`-Aufrufer pruefen: nur `PlaybooksPage` —
  passt, wird im gleichen Schritt umgestellt. Bei spaeterer Wiederverwendung
  von `usePlaybooks` (z.B. in `PersonaDetailPage`s Playbook-Linker)
  pruefen — heute nur `listPlaybooks()` direkt im Detail-Page-Hook,
  also nicht betroffen.
- Routen-Reihenfolge `/playbooks/new` vor `/playbooks/:id` — analog W3.

## Doku-Log

Nach Verify: Notes-Eintrag auf Projektseite + Pointer. Task -> Review.

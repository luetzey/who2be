# W2 — Token-Verwaltungsseite

> Task: [TASK-266](https://www.notion.so/36abe5372ab881ccaea5fc71a5621a1a) ·
> Milestone: MS-1 · Branch: `claude/pensive-euler-UAAsq`.

## Ziel / Completion-Condition

`/settings/tokens` listet eigene API-Tokens (Name, Erstellt-am, Last-Used,
Revoked-Status), erlaubt Anlage und Revoke. Beim Anlegen wird der Klartext-
Token genau einmal in einem Copy-Banner gezeigt; danach ist er nicht mehr
abrufbar. Dieselbe Seite bietet zusaetzlich einen `w2b_`-Token-Override-
Setter (Brueckenstueck aus W1 fuer Headless-Use-Cases).

**Transkript-Check:** `npm run lint`, `npx tsc --noEmit`, `npm test` gruen
inkl. mindestens einem Render-/Submit-Test fuer `SettingsTokensPage`.

## Guardrails

- TS strict, kein `any`, funktionale Komponenten + Hooks; Token-Werte nicht
  in localStorage.
- Disjunkt zu W3/W4/W5: keine Aenderungen an `PersonasPage.tsx`,
  `PlaybookDetailPage.tsx`, `usePersonas.ts`, `usePlaybooks.ts`.
- Out-of-Scope: Token-Edit (Name aendern), bulk-Operationen, Suche/Filter,
  Pagination — die Seite zeigt eine flache Liste.

## Aktueller Stand

- API steht: `POST /v1/tokens` -> `TokenCreated` (mit Klartext), `GET /v1/tokens`
  -> `list[TokenRead]`, `DELETE /v1/tokens/{id}` -> 204/404.
- `TokenRead`-Felder: `id`, `name`, `created_at`, `last_used_at | null`,
  `revoked_at | null`.
- `TokenCreated` = `TokenRead` + `token: str` (Klartext, einmalig).
- `AuthTokenContext` aus W1 verfuegbar (`setOverrideToken(token | null)`).

## Schritte

1. **`api/types.ts`** — `Token`, `TokenCreated`, `TokenInput`-Interfaces
   spiegeln (TypeScript-Spiegel der Pydantic-Modelle, handgepflegt — kein
   Generator).
2. **`api/client.ts`** — `listTokens`, `createToken`, `revokeToken` an die
   `Api`-Interface anhaengen.
3. **`api/client.test.ts`** — kleiner Test fuer `revokeToken` (DELETE-Methode +
   204-Pfad bleibt korrekt; analog der bestehenden `getPersona`-Tests).
4. **`hooks/useTokens.ts`** — analog `usePersonas`: `tokens`, `loading`,
   `error`, `reload`. Keine Mutationen im Hook — die Page ruft `api.createToken`
   und `api.revokeToken` direkt auf und reloadet.
5. **`pages/SettingsTokensPage.tsx`** — Sektionen:
   - **Tokens-Liste**: Name, Status (aktiv / widerrufen am ...), Last-Used,
     Revoke-Button (deaktiviert bei `revoked_at !== null`).
   - **Neuen Token anlegen**: Name-Input + Submit. Bei Erfolg: Copy-Banner
     mit Klartext + "In Zwischenablage kopieren"-Button (`navigator.clipboard`,
     Fallback: Select-All textarea). Banner verschwindet erst, wenn der User
     ihn explizit schliesst.
   - **`w2b_`-Token aktivieren** (W1-Bruecke): Input + "Aktivieren"-Button
     ruft `setOverrideToken(value)`, "Override entfernen"-Button ruft
     `setOverrideToken(null)`. Status-Zeile zeigt "kein Override / Override
     aktiv (endet auf ...XYZ)".
6. **`App.tsx`** — Route `/settings/tokens` hinter `RequireAuth` einhaengen.
7. **Tests** — `pages/SettingsTokensPage.test.tsx`:
   - (a) Rendert geladene Tokens (1 mockt `fetch` mit `TokenRead[]`).
   - (b) Submit eines neuen Token-Namens triggert `POST` und zeigt den
     Klartext im Banner.
8. **Navigation:** **kein** Touch an PersonasPage/PlaybooksPage. Stattdessen
   nur in den Disjunktheits-Bereich von W2 schreiben — die Settings-Seite
   ist per URL erreichbar; W3 wird sie in die Persona-Header-Nav verlinken.

## Betroffene Dateien

- NEU `apps/web/src/pages/SettingsTokensPage.tsx`
- NEU `apps/web/src/pages/SettingsTokensPage.test.tsx`
- NEU `apps/web/src/hooks/useTokens.ts`
- AENDERN `apps/web/src/api/types.ts`
- AENDERN `apps/web/src/api/client.ts`
- AENDERN `apps/web/src/api/client.test.ts`
- AENDERN `apps/web/src/App.tsx`

## Risiken

- `navigator.clipboard` ist in jsdom nicht vorhanden — Test darf den
  Klartext nur ueber das DOM-Element verifizieren, nicht ueber Clipboard-API.
- Revoke-Bestaetigungs-Modal: nicht gebaut (Funktion vor Schoenheit). Bei
  Fehlklick muss der User halt einen neuen Token anlegen — die alten Tokens
  bleiben im UI als "widerrufen" markiert.

## Doku-Log

Nach Verify: Notes-Eintrag auf Projektseite + Pointer hierhin. Task -> Review.

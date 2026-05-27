# Frontend-Smoke-Checkliste

> Manueller Durchlauf am Ende einer Phase oder vor einem Release.
> Dauer: ~10–15 min. Erwartet wird: 0 Konsolen-Fehler, 0 sichtbare
> Layout-Regressionen, alle Toasts erscheinen, alle Form-Errors sind
> lesbar. Bei einem Treffer **abbrechen und Bug-Issue anlegen**.

## Vorbereitung

- [ ] `cd apps/web && npm run build && npm run preview` (Prod-Build) **oder**
      `npm run dev` (DEV-Build, fuer Catalog-Check noetig).
- [ ] Browser-DevTools offen, Konsole im Blick.
- [ ] Test-Account vorhanden (`luetzey@gmail.com` o. Aequivalent).

## A · Auth-Flow

- [ ] `/login` mit falschem Passwort → Inline-Error sichtbar, Submit-Button
      wird nicht gesperrt.
- [ ] `/login` mit korrekten Daten → Redirect auf `/`.
- [ ] Refresh nach Login → Session bleibt erhalten (kein erneuter
      Login-Redirect).

## B · 7 Pages × 2 Themes

Fuer jede Page einmal im **Light**- und einmal im **Dark**-Theme
durchlaufen. Theme via Header-Toggle umschalten (light/dark/system).

| # | Page | Pfad | Light | Dark | Acceptance |
|---|---|---|---|---|---|
| 1 | PersonasPage | `/` | ☐ | ☐ | Liste laedt; leere Liste zeigt `EmptyState`. |
| 2 | PersonaNewPage | `/personas/new` | ☐ | ☐ | Form-Felder lesbar, Submit deaktiviert bei leerem Pflichtfeld. |
| 3 | PersonaDetailPage | `/personas/:id` | ☐ | ☐ | Detail-Form + Playbook-Linker laden; Version-Liste sichtbar. |
| 4 | PlaybooksPage | `/playbooks` | ☐ | ☐ | Liste laedt; `EmptyState` bei leerer Liste. |
| 5 | PlaybookNewPage | `/playbooks/new` | ☐ | ☐ | Form-Felder lesbar; Tags/Triggers als Komma-Listen akzeptiert. |
| 6 | PlaybookDetailPage | `/playbooks/:id` | ☐ | ☐ | Detail-Form + Version-Liste; Markdown-Body editierbar. |
| 7 | SettingsTokensPage | `/settings/tokens` | ☐ | ☐ | Token-Tabelle laedt; „Override aktiv"-Hinweis korrekt. |

**Theme-Persistenz:** nach Toggle einmal Browser-Refresh — Theme bleibt
gewaehlt. `localStorage.theme` ist gesetzt.

## C · Toast-Flows

Alle Mutations-Confirmations laufen ueber `notify` (`lib/feedback.ts`)
und erscheinen als Sonner-Toast oben rechts. **Inline-`<Alert role="status">`
darf nur** auf der TokensPage erscheinen (Klartext-Reveal).

- [ ] Persona-Detail speichern → Toast: „Gespeichert — neue Version erstellt."
- [ ] Playbook-Detail speichern → Toast: „Gespeichert — neue Version erstellt."
- [ ] Persona-Playbooks toggeln + speichern → Toast: „Verknuepfungen gespeichert."
- [ ] Neuen Token anlegen → Toast: „Token „X" angelegt. Klartext jetzt einmalig kopieren."
- [ ] **Klartext-Reveal bleibt Inline-Alert** (`role="status"`) auf TokensPage.
- [ ] Token mit ungueltigem Scope → Toast: Error-Variante (rot).

## D · Form-Errors (zod-Validierung)

- [ ] PersonaNewPage: leeres `name`-Feld submitten → Feld-Fehler sichtbar,
      kein API-Call (Network-Tab pruefen).
- [ ] PlaybookNewPage: leeres `body`-Feld submitten → Feld-Fehler sichtbar.
- [ ] PersonaDetailPage: `description` leeren + speichern → Feld-Fehler
      sichtbar, **kein** Toast.
- [ ] PlaybookDetailPage: dito.

## E · Override-Token-Flow (Settings/Tokens)

- [ ] Neuen Token mit Scope `personas:read` anlegen → Klartext einmalig
      sichtbar (Inline-Alert).
- [ ] Klartext kopieren, dann „Override" aktivieren → Header zeigt
      „Override aktiv".
- [ ] Refresh → Override bleibt erhalten (in-memory Provider-State
      ueberlebt Page-Wechsel, **nicht** Browser-Reload — Acceptance:
      Override muss nach Reload erneut aktiviert werden).
- [ ] „Override deaktivieren" → Header-Hinweis verschwindet.
- [ ] Token revoken → Toast (Erfolg oder Fehler), Tabelle aktualisiert
      `revoked_at`.

## F · Navigation + AppShell

- [ ] Header zeigt 3 Nav-Items: Personas / Playbooks / Tokens.
- [ ] Aktives Item ist visuell hervorgehoben (current page).
- [ ] Theme-Toggle ist im Header rechts sichtbar.
- [ ] Sign-out im Header → Redirect `/login`, `localStorage.session`
      entfernt.

## G · Component-Catalog (DEV-only)

- [ ] `npm run dev` → `/_catalog` laedt, zeigt alle Primitives, Layout-
      und Data-Showcases.
- [ ] `npm run build && npm run preview` → `/_catalog` ist **404**
      (Tree-Shaking entfernt den Chunk).

## H · Anti-Pattern-Greps (CLI)

```
cd apps/web
grep -r "from '@/components/layout/AppShell'" src/features    # leer (Phase 2)
grep -rE "(<Toaster)" src/                                    # genau 1 Treffer in AppLayout.tsx
grep -rE "(useEffect|useState|useApi)\b" src/features/**/pages # nur Routing-Glue (useParams/useNavigate)
grep -r "<label" src/features src/components/{layout,data}    # leer (jsx-a11y + ESLint-Forbid)
```

## I · Verifikation-Gates

```
cd apps/web
npm run lint
npx tsc --noEmit
npm test
npm run build
```

Alle vier gruen.

---

**Run-Protokoll** (datieren + abhaken + Bugs verlinken):

| Datum | Runner | Build | Befund |
|---|---|---|---|
| YYYY-MM-DD | @user | prod | — |

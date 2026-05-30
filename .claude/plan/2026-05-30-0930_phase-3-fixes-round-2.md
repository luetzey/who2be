# Phase-3-Fixplan (Runde 2) — Tooltip-UI / BlockNote-Theme / Trigger-Pills / Invitation-Auth

Status: Draft — Review erbeten, dann parallel an Cloud-Agenten geben.
Live-Repro: 2026-05-30 nach Phase-3-Fixes-Runde-1 (PR #63–#67) — User-
Feedback inkl. Screenshot vom Slash-Overlay.

## Outcome

Editor-Forms sind ruhig und wirklich nutzbar: Hilfetexte schweben hinter
kleinen Info-Buttons (Tooltips), nicht mehr als Block-Spalten im Layout.
BlockNote rendert Slash-Menu, Listen, Divider und Heading-Skala konsistent
und schoen (Mantine-Theme korrekt geladen + scoped Overrides). Trigger
sind Pills statt Komma-String. Invitation-Magic-Link landet ohne Umweg
ueber `/login` im richtigen Workspace, und falls noch kein Passwort
gesetzt ist, im neuen `SetPasswordPage`.

DoD pro Track: `npm run lint`, `npx tsc --noEmit`, `npm test -- --run`,
`npm run build` plus (wo Backend dran ist) `uv run ruff check . && uv run mypy . && uv run pytest -q`.
Manueller Smoke gegen `docker compose` siehe pro Track.

## Out of scope

- Editor-Wechsel weg von BlockNote (ADR-0022 steht).
- Backend-Schema-Refactor fuer `triggers` (bleibt nullable string,
  Frontend wickelt CSV ↔ Array intern; spaeter koennen wir migrieren).
- Mail-/SMTP-Refactor (GoTrue-Invite-Mailer bleibt aus Phase 3-D).

---

## Track 1 — Hilfetexte als Info-Tooltip statt Inline-Block

### Ursache / Symptom

`FormSection.description` rendert einen Absatz unter dem Titel; in
`PersonaEditorForm.tsx:99` steht zusaetzlich ein `<details><summary>Beispiel anzeigen</summary>…</details>`,
in `PlaybookEditorForm.tsx` mehrere lange `description` + `footer`
Strings. Resultat: viel Erklaer-Text im Hauptlayout, Form wirkt
ueberladen.

### Aenderungen

1. **Neues UI-Primitive `InfoTooltip`** in `@/components/ui/info-tooltip.tsx`
   (basiert auf Radix-Tooltip — schon als Transitive-Dep vorhanden via
   shadcn). Trigger ist ein kleiner Icon-Button (`Info`-Icon, `size="sm"`,
   `variant="ghost"`); Content ist Markdown-fähiger Text (zumindest Bold
   + Codeblock + Listen). A11y: `aria-label="Hilfe einblenden"`, Content
   bekommt `role="tooltip"` automatisch via Radix.
2. **`FormSection` erweitern** (`@/components/layout/FormSection.tsx`):
   neue optionale `help` prop (string oder ReactNode). Wenn gesetzt,
   rendert sie neben dem Titel den `InfoTooltip`. `description`-Slot
   bleibt — wird aber nur noch fuer "ein Satz oder weniger" verwendet;
   alles, was heute mehrzeilig ist (Tipps, Beispiele, Footer), wandert
   in `help`.
3. **Editor-Forms migrieren**:
   - `apps/web/src/features/personas/components/PersonaEditorForm.tsx`:
     `<details>Beispiel anzeigen</details>` (Zeilen 98–106) raus,
     Inhalt in `help` der "Profil"-Section. `PROFILE_EXAMPLE_SNIPPET`
     bleibt als String-Konstante, wird aber im Tooltip als `<pre>`
     gerendert.
   - `apps/web/src/features/playbooks/components/PlaybookEditorForm.tsx`:
     `currentHint` (Typ-Beschreibung), Tag-Hinweis ("Beispiel: …"),
     Trigger-Hinweis ("Komma-Liste …", wird mit Track 3 obsolet),
     Inhalt-Section `description`+`footer` → `help`.
   - `apps/web/src/features/resources/pages/ResourceNewPage.tsx`,
     `ResourceDetailPage.tsx`: Falls dort lange Description-Strings
     stehen, ebenfalls hinter `help` migrieren.
4. **Catalog-Showcase** (`apps/web/src/app/catalog/showcases/`):
   neue Demo-Seite `info-tooltip.tsx`, registrieren in `CatalogPage`.
5. **Tests**:
   - `info-tooltip.test.tsx`: Tooltip oeffnet auf Hover/Focus, schliesst
     mit Escape, Content im DOM nur wenn offen (Performance).
   - `info-tooltip.a11y.test.tsx`: axe-clean, korrekte ARIA.
   - `PersonaEditorForm.test.tsx`: keine `details/summary`-Knoten mehr,
     Hilfe-Tooltip ist auffindbar via Role.

### Risiko

Niedrig. UI-Refactor, kein Daten-Flow. Konflikt mit Track 3 in
`PlaybookEditorForm.tsx` — Track 3 zuerst.

---

## Track 2 — Slash-Menu / BlockNote-Theme komplett richtig stylen

### Ursache / Symptom (Screenshot vorhanden)

- Slash-Overlay: alle Texte gleiche Schriftgroesse (Section-Label,
  Item-Title, Item-Description, Shortcut sehen identisch aus).
- Teilweise kein Hintergrund (transparente Items).
- Popover scrollt horizontal nach rechts.
- Items wirken ohne Spacing/Border.

Root-Cause-Vermutung **#1 (sehr wahrscheinlich)**: Wir importieren
`@blocknote/mantine/style.css` **nirgendwo**. `grep -rn "blocknote.*style"`
liefert null Treffer in `apps/web/src/`. Damit fehlen ALLE Default-
Styles von BlockNotes Mantine-Theme — unser Override in `globals.css`
ist bewusst nur scoped, der baseline-Theme muss zuerst rein.

Root-Cause-Vermutung **#2**: Die scoped `.bn-container h1/h2/h3`-Regeln
(globals.css:279–307) treffen via Cascade auch das Slash-Menu, weil
das Menue Mantine-Tokens nutzt; fehlende Item-Strukturklassen
(`.bn-suggestion-menu-item-title`, `-subtext`, `-shortcut`) bleiben
nackt.

### Aenderungen

1. **CSS-Import** in `apps/web/src/main.tsx` (oder zentral neben dem
   Tailwind-Import in `index.css`):
   `import '@blocknote/mantine/style.css'`.
   *Vorher: pruefen ob Mantine seinerseits einen `@import url("@mantine/core/styles.css")`
   triggert; falls ja, beide Imports vor Tailwind-Layer einhaengen,
   damit unsere Tokens die Mantine-Defaults ueberschreiben koennen.*
2. **Slash-Menu-Item-Layout** in `globals.css` §BlockNote-Insel:
   - `.bn-suggestion-menu-item` → Grid mit `auto 1fr auto` (Icon |
     Title+Subtext | Shortcut), Gap `var(--spacing)*3`, `padding: 0.5rem 0.75rem`.
   - `.bn-suggestion-menu-item-title` → `text-sm` + `font-medium`.
   - `.bn-suggestion-menu-item-subtext` → `text-xs` +
     `text-muted-foreground` (Token).
   - `.bn-suggestion-menu-item-shortcut` (oder Mantine-Aequivalent) →
     `text-xs` monospace + `text-muted-foreground`.
   - `.bn-suggestion-menu` → `max-width: min(28rem, calc(100vw - 2rem))`,
     `max-height: min(60vh, 480px)`, `overflow-y: auto`,
     `overflow-x: hidden`, `width: 22rem` (Default-Min).
3. **Section-Header im Slash-Menu** (Mantine: `.mantine-Combobox-group-label`
   oder `.bn-suggestion-menu-section-header` — Klasse im DevTools
   verifizieren): `text-[10px]` + `uppercase` + `tracking-wide` +
   `text-muted-foreground` + `border-b` + `padding: 0.5rem 0.75rem`.
4. **Dark-Theme** explizit pruefen: alle Popover-Hintergruende ueber
   `var(--popover)`/`var(--popover-foreground)` setzen — heute steht
   das nur am Root, Item-Hover via `var(--accent)` ist schon drin.
5. **Tests / Storybook**:
   - `BlockNoteEditor.test.tsx` erweitert: nach "/" und 100ms
     `screen.findByRole('menu')` und Snapshot der Klassen-Liste, damit
     wir merken, wenn Mantine in einem Update Klassen umbenennt.
   - Manueller Browser-Smoke (Chrome aktuell, Dark + Light): Slash an
     allen vier Editor-Stellen — Profil, System-Prompt, Playbook-Body,
     Resource-Body.

### Risiko

Mittel. CSS-Refactor mit globalem Import; Mantine-Default-Theme kann
mit Tailwind-Preflight clashen (z. B. Mantine setzt seine eigenen
`button`-Resets). Im Zweifel `@layer base` vor Tailwind ordnen,
nicht danach.

---

## Track 3 — Triggers als Pills

### Ursache / Symptom

`PlaybookEditorForm.tsx:197` rendert `triggers` als `Input` mit
Placeholder `'z. B. "passwort vergessen", "reset link"'`. User pflegt
Komma-String mit Anführungszeichen — niemand erkennt, was eine Einheit ist.

### Aenderungen

1. **Wiederverwenden**: `@/components/ui/tag-input.tsx` existiert
   bereits (siehe Tag-Feld in derselben Form), unterstuetzt Pills +
   Enter/Komma. Nichts neu zu bauen.
2. **PlaybookEditorForm** umstellen:
   - `triggers`-Field auf `TagInput value={...} onChange={...}`.
   - Form-Modell (`usePlaybookForm.ts` Zeile 27/97/127): `triggers`
     bleibt `z.string()` im Form-State **nur fuer den Wire-Roundtrip**,
     aber die UI haelt intern `string[]`. Beim Submit: join mit `, `.
     Beim Laden: split per `splitTriggers` (existiert schon).
   - Alternative (sauberer): `z.array(z.string())` im Form-Modell,
     Adapter zur API hebt `null` weg. Entscheidet der Implementor.
3. **Hilfe-Text** wandert in den `InfoTooltip` aus Track 1 (Komma-
   Hinweis ist nach Pills hinfaellig — wird ersetzt durch "Enter zum
   Anlegen, Klick zum Entfernen").
4. **PlaybookDetailPage.tsx** + `PlaybooksPage.tsx`: Render der Trigger
   im Read-View ebenfalls als kleine Pills statt Komma-String
   (Konsistenz; Daten-Lookup unveraendert).
5. **Tests**:
   - `PlaybookEditorForm.test.tsx`: Trigger anlegen + entfernen,
     Submit-Payload trifft die API mit erwartetem String.
   - `PlaybookDetailPage.test.tsx`: Render der Pills.

### Risiko

Niedrig. Konflikt mit Track 1 in `PlaybookEditorForm.tsx` — Track 3
**zuerst** mergen, dann Track 1 rebasen.

---

## Track 4 — BlockNote-Read-Render: Listen, Divider, Inline-Marks

### Ursache / Symptom

Im Read-/Edit-View zeigt der Editor zwar Headlines, aber:
- Bullet/Numbered Lists kommen ohne Bullet/Nummer (Tailwind-Preflight
  resettet `ul/ol`).
- Divider (`type: divider`) ist unsichtbar.
- Inline Codeblock und Links blass.

### Aenderungen

1. **CSS in `globals.css`** §BlockNote-Insel ergaenzen — scoped unter
   `.bn-container`/`.bn-block-content`:
   - `ul` → `list-style: disc; padding-left: 1.5rem;`
   - `ol` → `list-style: decimal; padding-left: 1.5rem;`
   - `li > p` → `margin: 0` (BlockNote rendert pro `li` ein `<p>`).
   - `hr` (Divider) → sichtbarer Trennstrich via
     `border-top: 1px solid var(--border); margin: 1rem 0;`
   - Inline `code` → `bg-muted/50` + `text-xs` + `rounded`.
2. **Pruefen**, ob BlockNote-Read-Only-Modus eigene Klassen setzt
   (`.bn-editor[contenteditable="false"]`?). Wenn ja, Selektor
   doppelt fuehren (Edit + Read), damit beides gleich aussieht.
3. **Tests**:
   - `BlockNoteEditor.test.tsx`: Snapshot zeigt, dass eine
     Bullet-Liste mit drei Items im DOM 3 `<li>` rendert (Vorhanden-
     Test, nicht Pixel-Snapshot).
   - Manueller Smoke: Persona-Profil mit Liste + Divider speichern,
     reloaden, beide sichtbar.

### Risiko

Mittel — Konflikt mit Track 2 in `globals.css`. Track 4 NACH Track 2
mergen, oder beide zu einem PR zusammenfassen (siehe Reihenfolge-
Empfehlung unten).

---

## Track 5 — Invitation-Auth-Flow wirklich ende-zu-ende fixen

### Ursache / Symptom

User: Klick auf Magic-Link → URL bekommt den Hash, aber UI zeigt
Login-Maske. Es gibt keine Moeglichkeit, sich einzuloggen (kein Passwort).

Root-Cause: `apps/web/src/lib/supabase.ts` setzt
`persistSession: false, autoRefreshToken: false`. Damit consumed
`supabase-js` zwar den URL-Hash (clearing), kann die geparste Session
aber nirgends ablegen — `getSession()` liefert null beim naechsten
Tick. Unser `SessionProvider` ruft `getSession()` korrekt im
`useEffect` (Track 5 / PR #64 hat das eingefuehrt), aber `null`
landet, weil der Storage fehlt.

Zusaetzlich: selbst wenn Session vorhanden, hat der frisch eingeladene
User noch kein Passwort. `me.has_password === false` muesste sofort auf
`SetPasswordPage` umleiten — der Code dafuer ist in
`InvitationAcceptPage.tsx:89` da, aber nutzlos, solange die Session
nicht ankommt.

### Aenderungen

1. **`apps/web/src/lib/supabase.ts`**:
   - `persistSession: true` (zwingend, sonst geht detect-in-URL
     verloren).
   - `storage`: Custom-Adapter, der **`sessionStorage`** benutzt
     (Tab-Lifetime, kein Reload-Sackgasse, kein dauerhaftes
     Token-Persisting im localStorage).
   - `autoRefreshToken: true` (sonst kippt der Token mitten in einer
     Session).
   - `detectSessionInUrl: true` (default, aber explizit setzen).
   - `flowType: 'implicit'` lassen (GoTrue Invite ist implicit; PKCE
     wuerde anderen Hash-Aufbau brauchen).
   - Kommentar: warum sessionStorage statt localStorage — Tab-bezogene
     Session = nach Schliessen weg, MFA/Re-Login bewusst erzwingen,
     nichts persistent auf Disk.
2. **`apps/web/src/auth/SessionProvider.tsx`** Doppel-Bootstrap
   absichern:
   - Wenn `bootstrap()` beim ersten Mount eine Session liefert,
     `onAuthStateChange` darf den `me`-Fetch nicht ein zweites Mal
     starten. Heuristik: vergleiche `nextSession?.access_token`
     mit dem aktuellen — gleich = skip.
   - StrictMode-Doppel-Mount tolerieren (heute ueber `cancelled`-Flag
     ok, mit Hash-Consumption-Race aber wackelig — `bootstrap` muss
     idempotent sein).
3. **`InvitationAcceptPage.tsx`**:
   - Zusaetzlicher Branch: wenn Session da, aber `me === null` (z. B.
     `/v1/me` noch nicht zurueck) — Loading-State statt
     `Navigate('/login')`. Heute fehlt das, der `useEffect`-Auto-
     Accept laeuft nicht und es entsteht eine sichtbare Lade-Luecke.
   - Microcopy fuers Magic-Link-Bootstrap: "Login wird abgeschlossen…"
     statt der heutigen "Du wirst angemeldet…".
4. **`SetPasswordPage.tsx`**:
   - Wenn `next` auf eine Invitation-Accept-URL zeigt, nach
     erfolgreichem `updateUser` direkt dorthin redirecten — heute
     macht es das (`navigate(next ?? '/')`), aber wir wollen
     sicherstellen, dass `via=magic` im next erhalten bleibt
     (Invitation-Page springt sonst nicht in den Auto-Accept).
5. **Backend** unveraendert — `has_password` ist in `me.py`/me_repository
   schon richtig.
6. **Tests**:
   - `SessionProvider.test.tsx`: Bootstrap mit Hash-Session
     (`mockSupabase.auth.getSession` liefert eine Session), `setMe`
     und `setSession` werden in einem Render-Tick beobachtbar.
   - `InvitationAcceptPage.test.tsx` Regression: Session vorhanden,
     `me === null` → kein Login-Redirect, sondern Loading-Marker.
   - **E2E (manuell)**: Admin laedt zweiten User `invitee@…` ein,
     Inkognito-Tab klickt Mail-Link, kommt auf
     `/onboarding/set-password`, vergibt Passwort, landet im
     eingeladenen Workspace.

### Risiko

Hoch — Auth-Path. Bricht im worst case Login fuer alle User. Vor Merge
auf separater Branch mit Playwright-Probe absichern; manuell beide
Pfade (Email/Passwort-Login UND Magic-Link) testen.

---

## Followup (Backlog, nicht im Slot 1)

- **Test-Isolation**: Web-Test-Suite ist flaky (siehe Live-Smoke
  2026-05-30, mal `InvitationAcceptPage`, mal `PlaybookDetailPage`).
  Ursache: mehrere Test-Files setzen `vi.stubGlobal('fetch', …)` und
  teilen Worker-State. Fix: `vitest --pool=forks` ODER MSW als
  zentraler Fetch-Mock. Eigener PR `fix/test-isolation-global-fetch`,
  nach Runde-2-Tracks.

---

## Vorgeschlagene Reihenfolge

- **Slot 1 (3 parallel)**: Track 5 (Auth), Track 3 (Triggers-Pills),
  Track 2 (Slash-Menu-CSS).
- **Slot 2 (2 parallel, nach Slot 1)**: Track 1 (Tooltips, rebased auf
  Track 3), Track 4 (Listen/Divider, rebased auf Track 2). Beide
  conflict-Files sind dann frisch.

Jeder Track ein eigener PR (`fix/…` bzw. `feat/…`), Branches landen
ueber Review auf `main`.

## Notion-Follow-up

Nach Merge: Eintrag in PROJ-19 `## Notes` mit Pointer auf diese
Plan-Datei und Liste der PRs.

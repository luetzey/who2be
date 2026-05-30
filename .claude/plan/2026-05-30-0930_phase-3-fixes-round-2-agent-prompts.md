# Agent-Prompts — Phase-3-Fixes Runde 2 (zum parallelen Starten)

Plan: `.claude/plan/2026-05-30-0930_phase-3-fixes-round-2.md`

## Parallelitaets-Regel

- **Slot 1 (parallel startbar):** Track 5 + Track 3 + Track 2.
- **Slot 2 (nach Slot-1-Merge):** Track 1 (rebase auf Track 3),
  Track 4 (rebase auf Track 2).
- Hintergrund: Track 1 und Track 3 aendern beide `PlaybookEditorForm.tsx`.
  Track 2 und Track 4 aendern beide `globals.css` §BlockNote-Insel.

---

## Track 5 — Invitation-Auth-Flow ende-zu-ende (Slot 1, hoechste Prio)

````
Du bist Coder. Folge dem Coder-Bootstrap in CLAUDE.md (Notion-Persona +
Playbooks). Lies vor jeder Aenderung den Plan
`.claude/plan/2026-05-30-0930_phase-3-fixes-round-2.md`, Abschnitt **Track 5**.

Ziel: Magic-Link-Invitation funktioniert ende-zu-ende. User klickt
Mail-Link -> Session wird etabliert -> `has_password=false` -> automatisch
`SetPasswordPage` -> Passwort gesetzt -> Auto-Accept der Einladung ->
Dashboard. Kein Umweg ueber `/login`.

Root-Cause (Diagnose, zur Orientierung): `apps/web/src/lib/supabase.ts`
hat `persistSession: false` — `supabase-js` parsed den URL-Hash, hat aber
keinen Storage, also kommt die Session in `getSession()` als `null` an.
PR #64 hat den Listener korrekt eingefuehrt, aber er hat nie was zum
listenen.

Scope:
- `apps/web/src/lib/supabase.ts`
  * `persistSession: true`, `autoRefreshToken: true`, `detectSessionInUrl: true`.
  * Custom `storage`-Adapter, der `sessionStorage` nutzt (NICHT
    `localStorage`). Kommentar: Tab-Lifetime-Session statt Disk-Persist.
  * `flowType` weiterhin implicit (default), nicht auf PKCE wechseln.
- `apps/web/src/auth/SessionProvider.tsx`
  * `onAuthStateChange` darf das `/v1/me`-Refetch nicht doppelt feuern,
    wenn `bootstrap()` schon eine Session geliefert hat (Token-Vergleich
    oder Idempotenz-Flag).
  * Atomare `setMe → setSession`-Reihenfolge aus PR #55 NICHT brechen.
- `apps/web/src/features/auth/pages/InvitationAcceptPage.tsx`
  * Neuer Zwischenzustand: `session !== null && me === null` → Loading-
    Marker (z. B. `LoadingState` aus `components/data`), KEIN
    Login-Redirect. Login-Redirect bleibt nur fuer `session === null`.
  * Microcopy beim Magic-Link-Flow: "Login wird abgeschlossen…" statt
    "Du wirst angemeldet…" (Unterscheidung Bootstrap vs. Accept).
- `apps/web/src/features/auth/pages/SetPasswordPage.tsx`
  * Pruefen, dass `next` inkl. `via=magic` an `navigate(next)` weiter-
    gereicht wird (Auto-Accept braucht den Marker).
- Tests:
  - `apps/web/src/auth/SessionProvider.test.tsx`: Bootstrap mit
    Hash-Session — Mock `supabase.auth.getSession` liefert eine
    Session, beobachten: `setMe + setSession` im selben Tick, keine
    Doppel-Refetches via `onAuthStateChange`.
  - `apps/web/src/features/auth/pages/InvitationAcceptPage.test.tsx`:
    neuer Case `session vorhanden, me === null` → Loading sichtbar,
    kein Login-Redirect.
  - Playwright-Smoke (in `.claude/plan/`-Notiz dokumentieren, nicht
    committen): Inkognito klickt Mail-Link → Set-Password → Dashboard.

Acceptance:
- E2E manuell: Admin laedt zweiten User ein, Klick aufs Mail-Link,
  setzt Passwort, landet im richtigen Workspace.
- Token landet **niemals** im `localStorage` (DevTools-Check).
- Email/Passwort-Login (bestehender Pfad) funktioniert weiter.

DoD:
- `uv run ruff check . && uv run mypy . && uv run pytest -q`
- (in `apps/web/`) `npm run lint && npx tsc --noEmit && npm test -- --run && npm run build`

Branch: `fix/invitation-auth-storage`
Commits: Conventional Commits, deutsche Imperative.
PR-Body: Summary, Test plan, Plan-Datei-Link, Hinweis auf E2E.
````

---

## Track 3 — Triggers als Pills (Slot 1, klein)

````
Du bist Coder. Folge dem Coder-Bootstrap in CLAUDE.md. Lies den Plan
`.claude/plan/2026-05-30-0930_phase-3-fixes-round-2.md`, Abschnitt **Track 3**.

Ziel: Trigger werden in der Playbook-Form als Pills gepflegt (Enter =
Anlegen, Klick = Entfernen) — keine Komma-Strings mit Anfuehrungszeichen
mehr. Read-View zeigt die Trigger ebenfalls als kleine Pills.

Scope:
- `apps/web/src/features/playbooks/components/PlaybookEditorForm.tsx`
  * `triggers`-Field auf `<TagInput …>` umstellen
    (`@/components/ui/tag-input`).
  * Hilfe-Microcopy unter dem Feld auf "Enter zum Anlegen, Klick zum
    Entfernen" kuerzen (der lange Komma-Hinweis fliegt raus —
    Track 1 wandert die restliche Erklaerung in einen Tooltip).
- `apps/web/src/features/playbooks/hooks/usePlaybookForm.ts`
  * Form-Modell: entweder `triggers: z.array(z.string())` mit
    Adapter zur API (cleaner) ODER weiterhin `z.string()` mit
    internem `string[]`-State im Form. Implementor entscheidet
    pragmatisch.
  * `splitTriggers` weiterverwenden fuer den Read-Pfad
    (Backend liefert nullable string).
- `apps/web/src/features/playbooks/pages/PlaybookDetailPage.tsx`
  * Trigger im Read-View als Pill-Liste (kleines `Badge`-Cluster).
- `apps/web/src/features/playbooks/pages/PlaybooksPage.tsx`
  * Trigger-Filter funktioniert weiter (`toLowerCase().includes`-
    Logik bleibt; arbeitet auf dem gestrippten String).
- Tests:
  - `PlaybookEditorForm.test.tsx`: Pill anlegen + entfernen, Submit-
    Payload prueft den erwarteten API-Wert.
  - `PlaybookDetailPage.test.tsx`: Pill-Render statt Komma-Text.

Acceptance:
- Anfuehrungszeichen verschwinden komplett aus der UI.
- Bestehende Playbooks mit Komma-Triggers laden korrekt als Pills.
- Speichern erzeugt eine valide Backend-Payload (kein Whitespace-
  Schluder, Trim wirkt).

DoD: `npm run lint`, `npx tsc --noEmit`, `npm test -- --run`,
`npm run build`. Backend nicht angefasst — kein Python-Gate noetig.

Branch: `feat/playbook-triggers-pills`

Konflikt-Hinweis: Ich beruehre `PlaybookEditorForm.tsx`. Track 1
beruehrt dieselbe Datei (Tooltips). Mein PR mergt zuerst; Track 1
rebased.
````

---

## Track 2 — Slash-Menu / BlockNote-Theme richtig stylen (Slot 1)

````
Du bist Coder. Folge dem Coder-Bootstrap in CLAUDE.md. Lies den Plan
`.claude/plan/2026-05-30-0930_phase-3-fixes-round-2.md`, Abschnitt **Track 2**.

Ziel: Slash-Menu sieht aus wie ein vernuenftiges Popover: getypte
Schriftgroessen (Section-Label klein, Title medium, Subtext klein, 
Shortcut monospace klein), saubere Surface, kein horizontales 
Scrollen, klare Max-Width/Height. Dark + Light gleich solide.

WICHTIG: vor jeder CSS-Aenderung sicherstellen, dass
`@blocknote/mantine/style.css` an EINER Stelle importiert ist (heute
nirgends — `grep -rn "blocknote.*style" apps/web/src` liefert leer).
Ohne die Mantine-Baseline kein Layout fuer Slash-Items.

Scope:
- `apps/web/src/main.tsx` (oder `index.css` direkt ueber
  `@import "tailwindcss"`):
  * `import '@blocknote/mantine/style.css'` ergaenzen, **vor** dem
    Tailwind-Import / `@layer base`, damit Tokens und scoped
    Overrides die Defaults schlagen.
- `apps/web/src/styles/globals.css` §BlockNote-Insel:
  * `.bn-suggestion-menu` → `max-width: min(28rem, calc(100vw - 2rem))`,
    `width: 22rem`, `max-height: min(60vh, 480px)`, `overflow-y: auto`,
    `overflow-x: hidden`.
  * `.bn-suggestion-menu-item` → Grid `auto 1fr auto`, Gap, Padding
    konsistent mit den Tokens.
  * `.bn-suggestion-menu-item-title` → `text-sm font-medium
    text-popover-foreground`.
  * `.bn-suggestion-menu-item-subtext` → `text-xs text-muted-foreground`.
  * `.bn-suggestion-menu-item-shortcut` (im DevTools die exakte Klasse
    bestaetigen — Mantine 7 nennt es ggf. `…-secondary-text`) →
    `text-xs font-mono text-muted-foreground`.
  * Section-Header (Mantine: `.mantine-Combobox-group-label`)
    pruefen + stylen: `text-[10px] uppercase tracking-wide
    text-muted-foreground border-b`.
- `apps/web/src/components/editor/BlockNoteEditor.test.tsx`
  * Test: nach Tippen von `/` ist `screen.findByRole('menu')` da;
    Snapshot der Klassen-Hierarchie (Existenz-Check, kein Pixel),
    damit ein Mantine-Update sofort auffaellt.

Acceptance:
- Slash-Menu rendert in allen vier Editor-Spots (Persona-Profil,
  Persona-System-Prompt, Playbook-Body, Resource-Body) konsistent.
- Kein horizontaler Scroll mehr.
- Dark- und Light-Theme: Surface, Border, Hover sichtbar getrennt.
- Tab-Reihenfolge (Keyboard-Auswahl) bleibt intakt.

DoD: `npm run lint && npx tsc --noEmit && npm test -- --run && npm run build`.
Manueller Browser-Smoke (Chrome, beide Themes) — Screenshot Vergleich
zum heutigen Stand im PR.

Branch: `fix/blocknote-slash-menu-theme`

Konflikt-Hinweis: Ich beruehre `globals.css`. Track 4 (Listen/Divider)
beruehrt dieselbe Datei. Mein PR mergt zuerst; Track 4 rebased.
````

---

## Track 1 — Hilfe-Tooltips statt Inline-Erklaerungen (Slot 2, nach Track 3)

````
Du bist Coder. Folge dem Coder-Bootstrap in CLAUDE.md. Lies den Plan
`.claude/plan/2026-05-30-0930_phase-3-fixes-round-2.md`, Abschnitt **Track 1**.

WICHTIG: Erst starten, wenn Track 3 (`feat/playbook-triggers-pills`)
auf main gemergt ist — gleiche Datei `PlaybookEditorForm.tsx`. Rebase
auf den aktuellen main, bevor du anfaengst.

Ziel: Editor-Forms wirken ruhig. Lange Beschreibungen, Tipps und
Beispiele leben hinter kleinen Info-Icon-Buttons (Tooltip on
Hover/Focus). Inline `<details>` und seitenlange
`FormSection.description`-Absaetze sind raus.

Scope:
- Neu: `apps/web/src/components/ui/info-tooltip.tsx` + Test +
  a11y-Test. Basis Radix-Tooltip (im shadcn-Ecosystem); Trigger ist
  ein Icon-Button mit `Info` (lucide), `aria-label="Hilfe einblenden"`.
  Content darf ReactNode sein.
- `apps/web/src/components/layout/FormSection.tsx`:
  * Neue optionale `help`-prop (ReactNode). Wenn gesetzt, rendert sie
    den `InfoTooltip` neben dem Titel.
  * `description` bleibt — wird auf "ein Satz Max" eingeschraenkt.
    Tests sichern den Layout-Kontrakt.
- Editor-Forms migrieren:
  * `apps/web/src/features/personas/components/PersonaEditorForm.tsx`:
    `<details>Beispiel anzeigen</details>` raus,
    `PROFILE_EXAMPLE_SNIPPET` als `<pre>` in den Tooltip der
    "Profil"-Section. Section-Footers / Beispiele in `help`.
  * `apps/web/src/features/playbooks/components/PlaybookEditorForm.tsx`:
    `currentHint` (Typ-Hinweis), Tag-Hinweis, Trigger-Hinweis-Reste
    in Tooltips wandern; `description`/`footer` straffen.
  * `apps/web/src/features/resources/pages/ResourceNewPage.tsx`,
    `ResourceDetailPage.tsx`: lange Description-Texte ebenfalls
    hinter `help`.
- Catalog: `apps/web/src/app/catalog/showcases/info-tooltip.tsx` +
  Registrierung in `CatalogPage.tsx`.
- Tests:
  - `info-tooltip.test.tsx`: Hover/Focus/Escape, Portal-Render-Position.
  - `info-tooltip.a11y.test.tsx`: axe-clean, ARIA.
  - `PersonaEditorForm.test.tsx`: keine `details/summary`-Nodes mehr;
    Help-Tooltip im DOM auffindbar.
  - `PlaybookEditorForm.test.tsx`: Help-Tooltip in den Sections.

Acceptance:
- Keine `<details>`/`<summary>` in Editor-Forms.
- Help-Tooltip zugaenglich per Maus, Touch (Long-Press), Tastatur
  (Focus + Escape).
- Layout-Hoehe der Forms sichtbar reduziert (eyeball-check / Screenshot
  im PR).

DoD: `npm run lint && npx tsc --noEmit && npm test -- --run && npm run build`.

Branch: `fix/editor-form-help-tooltips`
````

---

## Track 4 — BlockNote-Read-Render: Listen, Divider, Inline-Marks (Slot 2, nach Track 2)

````
Du bist Coder. Folge dem Coder-Bootstrap in CLAUDE.md. Lies den Plan
`.claude/plan/2026-05-30-0930_phase-3-fixes-round-2.md`, Abschnitt **Track 4**.

WICHTIG: Erst starten, wenn Track 2 (`fix/blocknote-slash-menu-theme`)
auf main ist — gleiche Datei `globals.css`. Rebase auf main vor Beginn,
damit der Mantine-CSS-Import-Pfad und die Slash-Menu-Selektoren da sind.

Ziel: Im Editor (Read und Edit) rendern Bullet-/Numbered-Lists mit
Bulletpoints/Nummern, Divider als sichtbarer Trennstrich, Inline-Code
mit Surface-Tinte.

Scope:
- `apps/web/src/styles/globals.css` §BlockNote-Insel:
  * `.bn-container ul, .bn-block-content ul` →
    `list-style: disc; padding-left: 1.5rem;`
  * `.bn-container ol, .bn-block-content ol` →
    `list-style: decimal; padding-left: 1.5rem;`
  * `.bn-container li > p, .bn-block-content li > p` → `margin: 0;`
  * `.bn-container hr, .bn-block-content hr` →
    `border-top: 1px solid var(--border); margin: 1rem 0;`
  * `.bn-container code, .bn-block-content code` →
    `background: hsl(var(--muted) / 0.5); padding: 0.1em 0.3em;
    border-radius: 0.25rem; font-size: 0.85em;`
- Read-Only-Modus pruefen: BlockNote setzt im read-only-Modus eigene
  Klassen — Selektoren so fuehren, dass Edit + Read identisch sind.
- Tests:
  - `apps/web/src/components/editor/BlockNoteEditor.test.tsx`:
    Liste mit 3 Items rendert 3 `<li>`-Nodes (Existenz-Snapshot).
    Divider rendert ein `<hr>`.
  - Manueller Smoke: Persona-Profil mit Bullet-Liste + Divider
    speichern, reloaden, beide sichtbar — Screenshot vergleichen.

Acceptance:
- Bullet-Liste hat sichtbare Punkte.
- Numbered-Liste hat sichtbare Zahlen.
- Divider ist als horizontale Linie zu sehen.
- Inline-Code hat eine andere Surface als Body-Text.
- Light + Dark beide ok.

DoD: `npm run lint && npx tsc --noEmit && npm test -- --run && npm run build`.

Branch: `fix/blocknote-read-render`
````

---

## Followup-Hinweis

Test-Isolation-Flake (siehe Plan-Section "Followup") in einem eigenen
PR `fix/test-isolation-global-fetch` nach Runde-2-Abschluss. Nicht im
Slot 1 oder 2.

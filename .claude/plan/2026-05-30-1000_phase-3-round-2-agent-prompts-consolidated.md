# Agent-Prompts — Phase-3-Fixes Runde 2 (konsolidiert auf 3 parallele Agenten)

Plan: `.claude/plan/2026-05-30-0930_phase-3-fixes-round-2.md`
(volle Track-Begruendungen). Diese Datei buendelt die 5 Tracks zu
drei konfliktfreien Agenten, die **alle gleichzeitig** laufen koennen.

## Mapping Tracks → Agenten

| Agent | gebuendelt aus | begruendet warum |
|---|---|---|
| **A — Editor-Form-UX** | Track 1 (Tooltips) + Track 3 (Trigger-Pills) | Beide aendern `PlaybookEditorForm.tsx` → in einem PR statt zwei seriell |
| **B — BlockNote-Theme** | Track 2 (Slash-Menu) + Track 4 (Listen/Divider/Inline) | Beide leben in `globals.css §BlockNote-Insel` + brauchen den Mantine-CSS-Import |
| **C — Invitation-Auth** | Track 5 | Disjunkt zu A/B, isolierte Auth-Schicht |

**Datei-Schnittmenge zwischen A, B, C:** keine.
Branches koennen also komplett parallel arbeiten und in beliebiger
Reihenfolge mergen.

---

## Agent A — Editor-Form-UX (Tooltips + Trigger-Pills)

````
Du bist Coder. Folge dem Coder-Bootstrap in CLAUDE.md (Notion-Persona +
Playbooks). Lies vor jeder Aenderung den Plan
`.claude/plan/2026-05-30-0930_phase-3-fixes-round-2.md`, Abschnitte
**Track 1** und **Track 3** — du erledigst beide in einem PR.

Ziel: Editor-Forms sind ruhig und schnell zu pflegen.
1. Lange Beschreibungen, Tipps und Beispiele leben hinter kleinen
   Info-Icon-Buttons (Tooltip on Hover/Focus). Inline `<details>` und
   seitenlange `FormSection.description`-Absaetze sind raus.
2. Playbook-Trigger werden als Pills gepflegt (Enter = Anlegen, Klick
   = Entfernen) — keine Komma-Strings mit Anfuehrungszeichen mehr.
   Read-View zeigt Trigger ebenfalls als Pills.

Scope:
- Neu: `apps/web/src/components/ui/info-tooltip.tsx` (Wrapper um
  Radix-Tooltip; Trigger = Icon-Button mit `Info` aus lucide,
  `aria-label="Hilfe einblenden"`; Content darf ReactNode sein).
- `apps/web/src/components/layout/FormSection.tsx`
  * Optionale `help`-Prop (ReactNode); rendert `InfoTooltip` neben
    dem Titel. `description` bleibt — nur fuer "ein Satz Max".
- `apps/web/src/features/personas/components/PersonaEditorForm.tsx`
  * `<details>Beispiel anzeigen</details>` raus,
    `PROFILE_EXAMPLE_SNIPPET` als `<pre>` in den Tooltip der
    "Profil"-Section. Section-Footers/Beispiele in `help`.
- `apps/web/src/features/playbooks/components/PlaybookEditorForm.tsx`
  * Typ-Hinweis (`currentHint`), Tag-Hinweis, Trigger-Hinweis-Reste
    wandern in Tooltips.
  * `triggers`-Field auf `<TagInput …>` umstellen
    (`@/components/ui/tag-input` existiert schon).
  * Hilfe-Microcopy unter Trigger-Feld auf "Enter zum Anlegen, Klick
    zum Entfernen" kuerzen — Rest in Tooltip.
- `apps/web/src/features/playbooks/hooks/usePlaybookForm.ts`
  * Form-Modell: entweder `triggers: z.array(z.string())` mit
    Adapter zur API (sauberer) ODER weiterhin `z.string()` mit
    internem `string[]`-State (pragmatisch). `splitTriggers` bleibt
    fuer Read-Pfad.
- `apps/web/src/features/playbooks/pages/PlaybookDetailPage.tsx`
  * Trigger als Pill-Cluster (`Badge`) statt Komma-Text.
- `apps/web/src/features/playbooks/pages/PlaybooksPage.tsx`
  * Trigger-Filter (`toLowerCase().includes`) bleibt — arbeitet auf
    gestripptem String.
- `apps/web/src/features/resources/pages/ResourceNewPage.tsx`,
  `apps/web/src/features/resources/pages/ResourceDetailPage.tsx`
  * Lange Description-Texte hinter `help` migrieren, falls vorhanden.
- Catalog: `apps/web/src/app/catalog/showcases/info-tooltip.tsx` +
  Registrierung in `CatalogPage.tsx`.
- Tests:
  - `info-tooltip.test.tsx`: Hover/Focus/Escape, Portal-Render-Position.
  - `info-tooltip.a11y.test.tsx`: axe-clean, ARIA.
  - `PersonaEditorForm.test.tsx`: keine `details/summary` mehr;
    Help-Tooltip im DOM auffindbar.
  - `PlaybookEditorForm.test.tsx`: Pill anlegen + entfernen, Submit-
    Payload trifft erwarteten API-Wert; Help-Tooltips in Sections.
  - `PlaybookDetailPage.test.tsx`: Pill-Render statt Komma-Text.

Acceptance:
- Keine `<details>`/`<summary>` mehr in Editor-Forms.
- Help-Tooltip per Maus, Touch (Long-Press) und Tastatur (Focus +
  Escape) bedienbar.
- Anfuehrungszeichen verschwinden komplett aus Trigger-UI; bestehende
  Playbooks mit Komma-Triggers laden korrekt als Pills.
- Layout-Hoehe der Forms sichtbar reduziert (Screenshot-Vergleich
  im PR).

DoD: `npm run lint && npx tsc --noEmit && npm test -- --run && npm run build`.
Backend nicht angefasst — Python-Gates nicht noetig.

Branch: `feat/editor-form-ux`
Commits: Conventional Commits, deutsche Imperative.
PR-Body: Summary, Test plan, Plan-Datei-Link, Vorher/Nachher-Screenshot
einer Form.
````

---

## Agent B — BlockNote-Theme (Slash-Menu + Listen + Divider + Inline)

````
Du bist Coder. Folge dem Coder-Bootstrap in CLAUDE.md. Lies den Plan
`.claude/plan/2026-05-30-0930_phase-3-fixes-round-2.md`, Abschnitte
**Track 2** und **Track 4** — du erledigst beide in einem PR.

Ziel: BlockNote-Editor sieht ueberall sauber aus.
1. Slash-Menu wirkt wie ein vernuenftiges Popover (getypte
   Schriftgroessen: Section-Label klein, Title medium, Subtext klein,
   Shortcut monospace klein; saubere Surface; kein horizontales
   Scrollen; klare Max-Width/Height; Dark + Light gleich solide).
2. Listen (Bullet/Numbered) rendern mit Punkten/Nummern, Divider als
   sichtbarer Trennstrich, Inline-Code mit Surface-Tinte.

**Kritischer Vorbefund**: `@blocknote/mantine/style.css` ist heute
NIRGENDS importiert (`grep -rn "blocknote.*style" apps/web/src` →
leer). Ohne die Mantine-Baseline fehlen ALLE Default-Layout-Regeln
fuer Slash-Items und Block-Inhalte. **Erst Import, dann Overrides.**

Scope:
- `apps/web/src/main.tsx` (oder `index.css` direkt ueber
  `@import "tailwindcss"`):
  * `import '@blocknote/mantine/style.css'` ergaenzen, **vor** dem
    Tailwind-Import / `@layer base`, damit Tokens und scoped
    Overrides die Defaults schlagen.
- `apps/web/src/styles/globals.css` §BlockNote-Insel:
  * Slash-Menu:
    - `.bn-suggestion-menu` → `max-width: min(28rem, calc(100vw - 2rem))`,
      `width: 22rem`, `max-height: min(60vh, 480px)`,
      `overflow-y: auto`, `overflow-x: hidden`.
    - `.bn-suggestion-menu-item` → Grid `auto 1fr auto`, Gap/Padding.
    - `.bn-suggestion-menu-item-title` → `text-sm font-medium
      text-popover-foreground`.
    - `.bn-suggestion-menu-item-subtext` → `text-xs
      text-muted-foreground`.
    - Shortcut-Klasse im DevTools verifizieren (Mantine 7 ggf.
      `…-secondary-text`) → `text-xs font-mono text-muted-foreground`.
    - Section-Header (Mantine: `.mantine-Combobox-group-label` o.ae.)
      pruefen + stylen: `text-[10px] uppercase tracking-wide
      text-muted-foreground border-b`.
  * Block-Render (scoped unter `.bn-container`/`.bn-block-content`):
    - `ul` → `list-style: disc; padding-left: 1.5rem;`
    - `ol` → `list-style: decimal; padding-left: 1.5rem;`
    - `li > p` → `margin: 0;`
    - `hr` → `border-top: 1px solid var(--border); margin: 1rem 0;`
    - `code` → `background: hsl(var(--muted) / 0.5);
      padding: 0.1em 0.3em; border-radius: 0.25rem; font-size: 0.85em;`
  * Read-Only-Modus pruefen: BlockNote setzt im read-only-Modus eigene
    Klassen — Selektoren so fuehren, dass Edit + Read identisch sind.
- Tests:
  - `apps/web/src/components/editor/BlockNoteEditor.test.tsx`:
    * Nach Tippen von `/` ist `screen.findByRole('menu')` da;
      Snapshot der Klassen-Hierarchie (Existenz-Check), damit ein
      Mantine-Update sofort auffaellt.
    * Liste mit 3 Items rendert 3 `<li>`-Nodes; Divider rendert
      `<hr>`.

Acceptance:
- Slash-Menu rendert in allen vier Editor-Spots (Persona-Profil,
  Persona-System-Prompt, Playbook-Body, Resource-Body) konsistent.
- Kein horizontaler Scroll.
- Bullet-Liste hat Punkte; Numbered-Liste hat Zahlen; Divider als
  Linie; Inline-Code mit anderer Surface.
- Dark + Light beide ok — Surface, Border, Hover sauber getrennt.
- Tab-Reihenfolge (Keyboard-Navigation im Slash-Menu) intakt.

DoD: `npm run lint && npx tsc --noEmit && npm test -- --run && npm run build`.
Manueller Browser-Smoke (Chrome, beide Themes) — Screenshot-Vergleich
zum heutigen Stand im PR.

Branch: `fix/blocknote-theme`
````

---

## Agent C — Invitation-Auth-Flow ende-zu-ende

````
Du bist Coder. Folge dem Coder-Bootstrap in CLAUDE.md. Lies den Plan
`.claude/plan/2026-05-30-0930_phase-3-fixes-round-2.md`, Abschnitt
**Track 5**.

Ziel: Magic-Link-Invitation funktioniert ende-zu-ende. User klickt
Mail-Link → Session wird etabliert → `has_password=false` → automatisch
`SetPasswordPage` → Passwort gesetzt → Auto-Accept der Einladung →
Dashboard. Kein Umweg ueber `/login`.

**Root-Cause (Diagnose, zur Orientierung)**: `apps/web/src/lib/supabase.ts`
hat `persistSession: false` — `supabase-js` parsed den URL-Hash, hat aber
keinen Storage, also kommt die Session in `getSession()` als `null` an.
PR #64 hat den `onAuthStateChange`-Listener korrekt eingefuehrt, aber
er hat nie was zum listenen.

Scope:
- `apps/web/src/lib/supabase.ts`
  * `persistSession: true`, `autoRefreshToken: true`,
    `detectSessionInUrl: true`.
  * Custom `storage`-Adapter, der `sessionStorage` nutzt (NICHT
    `localStorage`). Kommentar: Tab-Lifetime-Session statt
    Disk-Persistierung.
  * `flowType` weiterhin implicit (default), nicht auf PKCE wechseln.
- `apps/web/src/auth/SessionProvider.tsx`
  * `onAuthStateChange` darf das `/v1/me`-Refetch nicht doppelt feuern,
    wenn `bootstrap()` schon eine Session geliefert hat (Token-Vergleich
    oder Idempotenz-Flag).
  * Atomare `setMe → setSession`-Reihenfolge aus PR #55 NICHT brechen.
- `apps/web/src/features/auth/pages/InvitationAcceptPage.tsx`
  * Neuer Zwischenzustand: `session !== null && me === null` →
    Loading-Marker (z. B. `LoadingState` aus `components/data`), KEIN
    Login-Redirect. Login-Redirect bleibt nur fuer `session === null`.
  * Microcopy beim Magic-Link-Flow: "Login wird abgeschlossen…" statt
    "Du wirst angemeldet…" (Unterscheidung Bootstrap vs. Accept).
- `apps/web/src/features/auth/pages/SetPasswordPage.tsx`
  * Pruefen, dass `next` inkl. `via=magic` an `navigate(next)`
    weitergereicht wird — Invitation-Page braucht den Marker, sonst
    springt der Auto-Accept nicht.
- Tests:
  - `apps/web/src/auth/SessionProvider.test.tsx`: Bootstrap mit
    Hash-Session — Mock `supabase.auth.getSession` liefert eine
    Session, beobachten: `setMe + setSession` im selben Tick, keine
    Doppel-Refetches via `onAuthStateChange`.
  - `apps/web/src/features/auth/pages/InvitationAcceptPage.test.tsx`:
    neuer Case `session vorhanden, me === null` → Loading sichtbar,
    kein Login-Redirect.
  - Playwright-Smoke-Notiz (in PR-Body, kein neuer Test): Inkognito
    klickt Mail-Link → Set-Password → Dashboard.

Acceptance:
- E2E manuell: Admin laedt zweiten User ein, Klick aufs Mail-Link,
  setzt Passwort, landet im richtigen Workspace.
- Token landet **niemals** im `localStorage` (DevTools-Check).
- Email/Passwort-Login (bestehender Pfad) funktioniert weiter.

DoD: `npm run lint && npx tsc --noEmit && npm test -- --run && npm run build`.
Backend nicht angefasst — Python-Gates nicht noetig (`me.has_password`
ist bereits da).

Branch: `fix/invitation-auth-storage`
````

---

## Followup (eigener PR nach Runde 2)

- **Test-Isolation-Flake**: Web-Suite ist flaky (`vi.stubGlobal('fetch')`
  bleedt zwischen Files). Fix: `vitest --pool=forks` oder MSW.
  Branch: `fix/test-isolation-global-fetch`.

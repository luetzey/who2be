TITEL: W3 Auth: Responsive-Audit von features/auth (9 Dateien)
LABELS: web, agent-ready, size/M
---
### Problem

W3 (Feature-Audit je Domäne) von **#431**, Paket `auth`. Die Domäne ist auf
`main` @ `87de64c` einzeln nachgemessen: **9 produktive `.tsx`** unter
`apps/web/src/features/auth/`, davon tragen **0** einen Breakpoint-Prefix.

```bash
find apps/web/src/features/auth -name '*.tsx' \
  ! -name '*.test.tsx' ! -name '*test-utils*' ! -path '*/test/*' | wc -l   # 9
find apps/web/src/features/auth -name '*.tsx' \
  ! -name '*.test.tsx' ! -name '*test-utils*' ! -path '*/test/*' \
  -exec grep -lE '\b(sm|md|lg|xl|2xl):' {} \;                             # (leer)
```

**`auth` ist seit dem 2026-09-15 ein eigenes Paket, nicht die Hälfte von
„öffentliche Seiten".** Zusammengefaltet mit `legal` wären es 9 + 8 = **17
Dateien** und damit das größte aller dreizehn W3-Pakete gewesen — während #431
im selben Body vor ungleich großen Paketen warnt. Dass beide „öffentlich" sind,
ist eine Eigenschaft der Route, keine Zuschnitt-Begründung: `auth` sind
Formulare mit Fehlerzuständen, MFA-Step-up und OAuth-Consent, `legal` sind
statische Rechtstexte. Sie teilen keine Komponente.

**Die Domäne ist die Eingangstür der Anwendung** — wer sich auf dem Handy nicht
anmelden kann, sieht von den anderen zwölf Domänen nichts.

> **Zählweise (Queue-Regeln 48/51):** `find`, nicht die Pathspec
> `'apps/web/src/**/*.tsx'` — die übergeht Wurzel-Dateien (386 gegen 383).
> Ausschluss dreiteilig, nicht nur `*.test.tsx`.

### Null Prefixe — und warum das hier gerade kein Befund ist

Acht der neun Dateien folgen **wortwörtlich dem dokumentierten Muster** aus
`docs/frontend/design-language.md` §10.2 („Marketing-Page (Auth, Brand)"):

```
<main class="flex min-h-screen items-center justify-center bg-muted/30 px-4 py-10">
  <Card class="w-full max-w-md shadow-modal border-transparent">
```

Das Muster ist **mobile-first ohne Prefix konstruiert**: `w-full` ist der
Phone-Fall, `max-w-md` (448 px) greift erst, wenn Platz da ist, und `px-4`
hält den Rand. Auf 320 px ergibt das 320 − 32 = 288 px Karte mit 16 px Rand je
Seite — genau derselbe Effektivwert, den W2 für den Dialog gewählt hat.
**Null Prefixe sind hier also Norm-Konformität, nicht Drift** (§4.4:
„Basis-Klassen ohne Prefix sind der Phone-Fall").

**Was dieses Paket deshalb prüft, ist nicht die Klassenliste, sondern der
Inhalt der Karten**: Formularfelder, Fehlermeldungen, OAuth-Buttons,
MFA-Eingabe, Consent-Scope-Listen. Genau dort sind die Kandidaten.

### Ist-Zustand (nachgemessen 2026-09-22 auf `main` @ `87de64c`)

| Datei | Breakpoints | Befund |
|---|---|---|
| `features/auth/pages/LoginPage.tsx` (328 Z.) | – | `:167` `flex min-h-screen items-center justify-center bg-muted/30 px-4 py-10`, `:168` `w-full max-w-md border-transparent shadow-modal` — **§10.2-Muster, erfüllt**. `:173` `text-3xl tracking-tight` (nach §5 die H1 der Marketing-Page). `:235` `flex items-center justify-between` **ohne `flex-wrap`** — Label links, „Passwort vergessen"-Link rechts (`:243`, `text-xs`); der zu prüfende Fall bei langen deutschen Labels auf 320 px. `:265` `flex items-center gap-2` (Checkbox + Label `:276`). `:287` `<Button size="sm">` (E-Mail erneut senden) — **§11-Hit-Target zu prüfen**. `:301` `flex items-center gap-3 text-xs` mit zwei `h-px flex-1`-Trennern (`:302`, `:304`) — der „oder"-Teiler; zu prüfen, ob er auf 320 px zusammenfällt. Enthält zusätzlich den **MFA-Step-up-Zweig** (`:183`–`:206`) mit eigenem Formular und `w-full`-Submit. |
| `features/auth/pages/SignupPage.tsx` (266 Z.) | – | `:110` §10.2-`<main>`, `:111` §10.2-Karte — **erfüllt**. `:243` `flex items-center gap-3 text-xs text-muted-foreground` (derselbe Teiler wie im Login). Zu prüfen: Passwort-Regeln-Hinweis und Fehlerzustände auf 320 px. |
| `features/auth/pages/OAuthConsentPage.tsx` (298 Z.) | – | `:167` §10.2-`<main>`, `:168` §10.2-Karte — **erfüllt**. **Der inhaltlich dichteste Fall der Domäne:** die Scope-Liste („diese App darf …") ist eine mehrzeilige Aufzählung mit technischen Bezeichnern; auf 320 px der wahrscheinlichste Überlauf-Kandidat. `min-w-0` kommt in der gesamten Domäne **null** Mal vor (gegengeprüft). |
| `features/auth/pages/InvitationAcceptPage.tsx` (171 Z.) | – | Zwei §10.2-Karten für zwei Zustände: `:102`/`:103` (Lade-/Fehlerfall) und `:137`/`:138` (Annahme) — beide **erfüllt**. Zu prüfen: Workspace-Name und Einladender-E-Mail im Fließtext auf 320 px. |
| `features/auth/pages/AuthCallbackPage.tsx` (103 Z.) | – | Zwei §10.2-Karten: `:63`/`:64` und `:88`/`:89` — **erfüllt**. Zu prüfen: Fehlermeldungen des OAuth-Rückwegs (können lange Provider-Texte enthalten). |
| `features/auth/pages/SetPasswordPage.tsx` (127 Z.) | – | `:62` §10.2-`<main>`, `:63` §10.2-Karte — **erfüllt**. Zu prüfen: Passwort-Regeln und Feldfehler auf 320 px. |
| `features/auth/pages/ResetPasswordPage.tsx` (115 Z.) | – | `:56` §10.2-`<main>`, `:57` §10.2-Karte — **erfüllt**. Zu prüfen wie oben. |
| `features/auth/pages/ComingSoonPage.tsx` (44 Z.) | – | `:19` §10.2-`<main>`, `:20` §10.2-Karte — **erfüllt**. Die dünnste Seite der Domäne. |
| `features/auth/components/OAuthButtons.tsx` (91 Z.) | – | `:68` `flex flex-col gap-2`, die beiden Provider-Buttons `:72`/`:82` tragen `w-full` — **erfüllt**, gestapelt und volle Breite. `:16`/`:24` Provider-Icons `h-4 w-4`. Zu prüfen: Hit-Target-Höhe der Buttons unterhalb `md`. |

**Breakpoint-Abdeckung: 0 von 9** — erklärt durch §10.2, siehe oben.

**Kein `grid-cols-*` in der gesamten Domäne** — einzeln gegengeprüft:

```bash
grep -rnE 'grid-cols-' --include='*.tsx' apps/web/src/features/auth \
  | grep -v '\.test\.tsx'                                                  # (leer)
```

**Was hier bereits stimmt und nicht wiederholt wird:** alle neun Karten folgen
§10.2; die OAuth-Buttons stapeln und füllen die Breite; die Dialog-/Popover-Caps
sitzen seit W2 im Primitive. **Das Login-Muster wird in §10.2 ausdrücklich als
Vorlage geführt** — dieses Paket bestätigt oder widerlegt das am gerenderten
Ergebnis, statt es zu übernehmen (Queue-Regel 22).

### Proposed solution

**Fertig heißt:** Jede der 9 Dateien ist bei 320 / 375 / 768 / 1024 px gegen
die sechspunktige Review-Checkliste aus `docs/frontend/design-language.md` §4.4
geprüft; **jeder Anmeldeweg ist auf 320 px vollständig durchführbar** — Login
mit und ohne MFA-Step-up, Signup, Passwort zurücksetzen, Einladung annehmen,
OAuth-Consent erteilen. Jeder gefundene Defekt ist behoben oder mit Begründung
als „kein Defekt" festgehalten. Kein horizontaler Body-Scroll auf den
Auth-Routen.

**Geerbt, nicht neu entschieden** (#431, W1/#500, W2/#513): Mobile-Schwelle ist
`md` (`hooks/useMediaQuery.ts:7`) · breakpoint-abhängiger State als
Render-Zeit-Vergleich, **kein `useEffect`** · Dialog-Inset und
Popover-/Dropdown-Caps sitzen im Primitive · `cn()` läuft über `tailwind-merge`.

#### Vorentschieden (Frage → Entscheidung → weil)

1. **Den neun prefixlosen Dateien Prefixe nachrüsten, weil null auffällig
   ist?** → **Nein** → weil `w-full max-w-md` + `px-4` das in §10.2
   dokumentierte, mobile-first konstruierte Muster **ist** und §4.4 die
   präfixlose Klasse ausdrücklich zum Phone-Fall erklärt. **Diese Entscheidung
   steht im Issue, damit sie nicht in der Umsetzung neu aufgerollt wird.**
2. **Weicht eine der neun Seiten vom §10.2-Muster ab?** → **Nein, alle neun
   Karten tragen es identisch** (einzeln verifiziert, Zeilen in der Tabelle) →
   damit ist ein Fund an einer Seite mit hoher Wahrscheinlichkeit ein Fund an
   allen. **Wer hier etwas ändert, ändert es am Muster-Ort, nicht neunmal
   einzeln** — und bei einer Änderung am Muster selbst wird §10.2 im selben PR
   nachgezogen (Doku als Definition of Done).
3. **`LoginPage.tsx:235` (`justify-between`, Label gegen „Passwort
   vergessen")** → **`flex-wrap`** → weil das dem Repo-Muster folgt
   (`PageHeader.tsx:37`) und ein abgeschnittener Wiederherstellungs-Link auf
   dem Handy den einzigen Ausweg aus einem vergessenen Passwort verdeckt.
4. **`LoginPage.tsx:287` `size="sm"` und die OAuth-Buttons** → **auf ≥ 40 px
   bringen, wenn die Messung darunter liegt** → weil §11 das A11y-Minimum
   setzt und §4.4 Checklistenpunkt 4 genau die `size="sm"`-Verdichtung nennt.
5. **OAuth-Consent-Scope-Liste** → **umbrechen lassen, nicht kürzen** → weil
   ein gekürzter Scope-Text eine Einwilligung unvollständig darstellt. Technisch:
   `min-w-0` am Flex-Kind plus `break-words`, nicht `truncate`.
6. **Tests wohin?** → **`*.test.tsx` neben die geänderte Datei**, nach dem
   Muster von W2/#513. **Achtung (#442 §Kollisionen):** acht Testdateien tragen
   seit #471 einen `syncStorageBackendForThisTab`-Eintrag im `vi.mock` — ein
   `vi.mock`-Factory-Objekt muss **jeden** Export führen, den der Produktivcode
   aufruft, sonst bricht die halbe Auth-Testsuite auf einmal.

### Acceptance criteria

- [ ] Auf 320, 375, 768 und 1024 px erzeugt keine Auth-Route horizontalen
      Body-Scroll.
- [ ] **Jeder Anmeldeweg ist auf 320 px vollständig durchführbar:** Login mit
      und ohne MFA-Step-up (`LoginPage.tsx:183-206`), Signup, Passwort setzen
      und zurücksetzen, Einladung annehmen, OAuth-Consent erteilen.
- [ ] `LoginPage.tsx:235` bricht auf 320 px um oder passt vollständig — der
      „Passwort vergessen"-Link bleibt sichtbar und erreichbar.
- [ ] **Hit-Targets unterhalb `md` ≥ 40 px** (§11 A11y-Minimum) — geprüft an
      den OAuth-Buttons (`OAuthButtons.tsx:72`/`:82`) und an
      `LoginPage.tsx:287` (`size="sm"`).
- [ ] **Die OAuth-Consent-Scope-Liste ist auf 320 px vollständig lesbar** —
      umgebrochen, nicht gekürzt und nicht überlaufend.
- [ ] Fehlermeldungen (Feldfehler, OAuth-Rückweg-Fehler, Passwort-Regeln)
      brechen auf 320 px um und verdecken kein Eingabefeld.
- [ ] Mehrspaltige Grids sind an einen Breakpoint gebunden. Gate, liefert
      **keine** Zeile (heute wie nachher — die Domäne hat kein `grid-cols-*`):
      ```bash
      grep -rnE '(^|[^:a-z-])grid-cols-[2-9]' --include='*.tsx' \
        apps/web/src/features/auth | grep -v '\.test\.tsx'
      ```
- [ ] **Alle 9 Dateien sind in der Ist-Tabelle mit Befund oder begründetem
      „kein Defekt" abgehakt** — keine ungeprüfte Datei. Für das §10.2-Muster
      gilt die Begründung aus Weiche 1, nicht ein pauschales „nichts zu tun".
- [ ] Wird das §10.2-Muster geändert, ist `docs/frontend/design-language.md`
      §10.2 **im selben PR** nachgezogen (Doku als Definition of Done).
- [ ] Jeder neue Testfall war **vor** der Änderung rot (Test-first, CLAUDE.md
      §Workflow); die Coverage-Thresholds aus `apps/web/vite.config.ts:49-53`
      halten (Branches-Floor **79**).

### Scope

Genau die 9 Dateien unter `apps/web/src/features/auth/`, ihre Testnachbarn,
bei einer Musteränderung `docs/frontend/design-language.md` §10.2, und
`CHANGELOG.md` (§Unreleased, ein Eintrag, **als letzter Commit** —
Sammelpunkt).

### Out of scope

`components/ui/*` und `components/layout/*` (W2 hat dort entschieden; eine
Änderung wirkt auf alle dreizehn Domänen und ist ein eigenes Paket) ·
**`features/legal`** (seit 2026-09-15 eigenes W3-Paket) ·
`SessionProvider`/Auth-Zustandslogik außerhalb von `features/auth` · jede
Änderung am MFA-Verfahren, an GoTrue-Konfiguration oder an
`/auth/v1/factors` (#442 §Kollisionen: **8 der 12 e2e-Tests hängen am
aal2-Helper `e2e/helpers/auth.ts:33`** — wer dort arbeitet, bricht im Zweifel
die halbe e2e-Suite) · jede andere Domäne unter `features/` · W4
(Playwright-Mobile-Profile, E2E-Helfer „kein horizontaler Body-Scroll") ·
echter Fullscreen-Dialog unter `sm` (#513 Weiche 3, verworfen) · ESLint-Regel
für nackte `grid-cols-*` (#438 Weiche 5, verworfen) · `apps/api`, `apps/mcp`,
`packages/**`.

### Verifikation

```bash
cd apps/web
npm run lint
npx tsc -b            # NICHT --noEmit: das prueft null Dateien (Solution-File)
npm run test:coverage
npm run build
```

**Grün heißt:** Exit 0 bei allen vieren; `test:coverage` nennt Dateizahl und
Testzahl (Queue-Regel 21), die Branches-Thresholds halten; das Grid-Gate aus
AK 7 gibt keine Zeile aus.

**Umgebung:** kein Docker-Daemon nötig (reines Web-Paket, Vitest ist DB-frei).
Das Paket fasst `apps/web/**` an und steht **nicht** auf der Doku-Allowlist
(`ci.yml:74`) — die schweren CI-Jobs laufen. **Ein roter `e2e`-Job nach einer
Änderung in dieser Domäne ist ernst zu nehmen**, siehe Out of scope.

### Verweise

Tracking: **#431** (W3, Checklisteneintrag „Auth (Login, Signup/Coming-soon,
Consent, Step-up)"; die Trennung von `legal` ist im Block vom 2026-09-15
hergeleitet). Norm: `docs/frontend/design-language.md` §4.4 (Mobile-first,
Prefix-Pflicht, sechspunktige Review-Checkliste Z. 222–233), **§10.2
(Marketing-Page-Muster — die Vorlage aller neun Auth-Karten)** und §11
(A11y-Minimum 40 px), CLAUDE.md §Frontend-Standards. Vorgänger: **#438** (W0),
**#500** (W1 — Schwelle `md`, `useEffect`-freies Muster; der
`WorkspaceSwitcher` wurde dort unterhalb `sm` überhaupt erst erreichbar),
**#513** (W2 — Dialog-Inset, Caps im Primitive, `tailwind-merge`).

**Kollision:** fasst `apps/web` an — nicht parallel zu einem anderen
`apps/web`-Paket im selben Arbeitsbaum, sondern nacheinander oder in getrennten
Worktrees (#442 §Wellen). **`auth` und `legal` liegen beide am
i18n-Sammelpunkt** (`apps/web/src/i18n/locales/{de,en}.json`) und teilen den
Vitest-Baum — je zwei gleichzeitig nur in getrennten Worktrees, i18n je Paket
auf **einen** Namespace. Die drei größten W3-Pakete (`playbooks` 16, `workarea`
14, `personas` 13) laufen nie zu zweit gleichzeitig.

### Component

Web UI (apps/web)

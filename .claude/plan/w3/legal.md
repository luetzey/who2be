TITEL: W3 Legal: Responsive-Audit von features/legal (8 Dateien)
LABELS: web, agent-ready, size/S
---
### Problem

W3 (Feature-Audit je Domäne) von **#431**, Paket `legal`. Die Domäne ist auf
`main` @ `87de64c` einzeln nachgemessen: **8 produktive `.tsx`** unter
`apps/web/src/features/legal/`, davon tragen **3** einen Breakpoint-Prefix.

```bash
find apps/web/src/features/legal -name '*.tsx' \
  ! -name '*.test.tsx' ! -name '*test-utils*' ! -path '*/test/*' | wc -l   # 8
find apps/web/src/features/legal -name '*.tsx' \
  ! -name '*.test.tsx' ! -name '*test-utils*' ! -path '*/test/*' \
  -exec grep -lE '\b(sm|md|lg|xl|2xl):' {} \;
# CookieConsentBanner.tsx, LegalLayout.tsx, TermsPage.tsx
```

**`legal` ist seit dem 2026-09-15 ein eigenes Paket, nicht die Hälfte von
„öffentliche Seiten".** Zusammengefaltet mit `auth` wären es 8 + 9 = **17
Dateien** und damit das größte aller dreizehn W3-Pakete gewesen — während #431
im selben Body vor ungleich großen Paketen warnt. Fachlich teilen die beiden
nichts: `legal` sind statische Rechtstexte über ein gemeinsames Artikel-Layout,
`auth` sind Formulare mit Fehlerzuständen und Step-up. **Ihr Audit ist ein
anderer Vorgang** — hier geht es um Lesbarkeit langer Fließtexte auf 320 px,
dort um Formularbedienung.

> **Zählweise (Queue-Regeln 48/51):** `find`, nicht die Pathspec
> `'apps/web/src/**/*.tsx'` — die übergeht Wurzel-Dateien (386 gegen 383).
> Ausschluss dreiteilig, nicht nur `*.test.tsx`.

### Ist-Zustand (nachgemessen 2026-09-22 auf `main` @ `87de64c`)

| Datei | Breakpoints | Befund |
|---|---|---|
| `features/legal/components/CookieConsentBanner.tsx` (58 Z.) | **ja** (1) | `:25` `pointer-events-none fixed inset-x-0 bottom-0 z-50 flex justify-center p-4` (fixierter Banner). `:29` `pointer-events-auto flex w-full max-w-2xl flex-col gap-4 p-4 shadow-modal sm:flex-row sm:items-center` — **erfüllt und vorbildlich**: unter `sm` stapelt der Banner (Text über Buttons), darüber steht er nebeneinander. `:47` `flex shrink-0 gap-2` mit zwei `size="sm"`-Buttons (`:48`, `:51`) — **der zu prüfende Punkt: `size="sm"` unterschreitet unterhalb `md` möglicherweise das 40-px-Hit-Target aus §11**, genau der Fall aus §4.4 Checklistenpunkt 4. |
| `features/legal/components/LegalLayout.tsx` (67 Z.) | **ja** (1) | `:26` `mx-auto flex w-full max-w-3xl flex-col gap-3 px-4 py-4 sm:px-6` — **erfüllt**, mobile-first. `:27` `flex items-center justify-between` **ohne `flex-wrap`** — die Kopfzeile des Rechtsbereichs; zu prüfender Fall auf 320 px, wenn links Logo/Titel und rechts Navigation/Sprachwahl stehen. |
| `features/legal/pages/TermsPage.tsx` (172 Z.) | **ja** (4) | Vier Definitionspaare `:84`, `:90`, `:96`, `:104`, alle `flex flex-col gap-1 sm:flex-row sm:gap-2` — **erfüllt und mobile-first**, sie stapeln auf dem Phone. **Das ist der Grund, warum diese Seite Prefixe trägt und die drei anderen nicht** (siehe unten). |
| `features/legal/components/LegalArticle.tsx` (53 Z.) | – | `:24` `<Container className="max-w-3xl">` — Lesebreite über das geteilte Primitive; `Container` trägt bereits `px-4 … sm:px-6` (`components/layout/Container.tsx:6`), `max-w-3xl` verengt nur nach oben. **Erfüllt.** `:25`–`:50` durchgehend `flex flex-col` — einspaltiges Prose-Layout, keine feste Breite. `:27` `text-3xl`, `:49` `text-xl` — Überschriftengrößen ohne responsive Abstufung; zu prüfen, ob `text-3xl` auf 320 px mit langen deutschen Komposita (z. B. „Auftragsverarbeitungsvertrag") umbricht statt überzulaufen. |
| `features/legal/pages/DpaPage.tsx` (86 Z.) | – | Reiner Inhalt über `LegalArticle`/`LegalSection` (`:3`, `:15`–`:84`). **Kein Klassen-Befund** — die Seite trägt kein eigenes Layout. Zu prüfen: lange URLs, E-Mail-Adressen und Auftragsverarbeiter-Tabellen im Fließtext auf 320 px (`break-words` kommt in der gesamten Domäne **null** Mal vor — gegengeprüft). |
| `features/legal/pages/ImpressumPage.tsx` (80 Z.) | – | Wie oben, über `LegalArticle` (`:14`–`:78`). **Kein Klassen-Befund.** Zu prüfen: Anschrift, Registernummer, lange Kontaktangaben auf 320 px. |
| `features/legal/pages/PrivacyPage.tsx` (95 Z.) | – | Wie oben, über `LegalArticle` (`:14`–`:93`). **Kein Klassen-Befund.** Die längste der vier Textseiten; zu prüfen: tief verschachtelte Listen und Dienstleister-Aufzählungen auf 320 px. |
| `features/legal/components/Placeholder.tsx` (20 Z.) | – | `:13` `mx-0.5 rounded-sm border border-dashed border-brand bg-brand/10 px-1 py-0.5 font-mono text-xs font-medium text-brand` — Inline-Chip für Platzhalter im Fließtext. **Kein Klassen-Befund**; zu prüfen, ob ein langer Chip-Inhalt im Cookie-Banner auf 320 px umbricht (`Placeholder` wird von `CookieConsentBanner.tsx:35` verwendet). |

**Breakpoint-Abdeckung: 3 von 8.**

**Die Prefix-Verteilung ist kein Defekt, sondern erklärbar** — und die Erklärung
gehört ins Issue, damit niemand die fehlenden fünf mechanisch „nachrüstet":
Prefixe tragen genau die drei Dateien mit **eigenem Layout** (Banner, Kopfzeile,
Definitionspaare in den AGB). Die vier reinen Textseiten und `Placeholder`
delegieren ihr Layout vollständig an `LegalArticle` → `Container`, und
`LegalArticle` ist durchgehend einspaltig. **Eine einspaltige Prose-Seite
braucht keinen Prefix** (§4.4 Mobile-first: die präfixlose Klasse ist der
Phone-Fall). `TermsPage` trägt vier, weil sie als einzige Textseite
Definitionspaare rendert — also als einzige ein zweispaltiges Konstrukt hat.

**Was hier bereits stimmt und nicht wiederholt wird:** der Cookie-Banner
stapelt unter `sm`; `LegalLayout` und `Container` federn ihr Padding ab; die
vier Definitionspaare in `TermsPage` sind mobile-first. Die Dialog-/Popover-Caps
sitzen seit W2 im Primitive.

### Proposed solution

**Fertig heißt:** Jede der 8 Dateien ist bei 320 / 375 / 768 / 1024 px gegen
die sechspunktige Review-Checkliste aus `docs/frontend/design-language.md` §4.4
geprüft; die vier Rechtstexte sind auf 320 px **vollständig lesbar** — kein
überlaufender Link, keine überlaufende Adresse, keine abgeschnittene
Überschrift. Jeder gefundene Defekt ist behoben oder mit Begründung als „kein
Defekt" festgehalten. Kein horizontaler Body-Scroll auf `/legal/*`.

**Warum das zählt:** Impressum und Datenschutzerklärung sind rechtlich
vorgeschrieben erreichbar. Eine Datenschutzerklärung, deren Text auf dem Handy
seitlich aus dem Viewport läuft, ist faktisch nicht zur Kenntnis zu nehmen —
das ist der einzige der dreizehn Audits mit einer Außenwirkung über die
Bedienbarkeit hinaus. **Kein Rechtsrat, nur die Einordnung, warum dieses
kleine Paket nicht hinten anstehen sollte.**

**Geerbt, nicht neu entschieden** (#431, W1/#500, W2/#513): Mobile-Schwelle ist
`md` (`hooks/useMediaQuery.ts:7`) · breakpoint-abhängiger State als
Render-Zeit-Vergleich, **kein `useEffect`** · Dialog-Inset und
Popover-/Dropdown-Caps sitzen im Primitive · `cn()` läuft über `tailwind-merge`.

#### Vorentschieden (Frage → Entscheidung → weil)

1. **Den fünf prefixlosen Dateien Prefixe nachrüsten?** → **Nein** → weil sie
   ihr Layout an `LegalArticle`/`Container` delegieren und einspaltig sind;
   §4.4 Mobile-first macht die präfixlose Klasse zum Phone-Fall. Ein Prefix
   ohne gemessenen Defekt wäre Ballast. **Diese Entscheidung steht im Issue,
   damit sie nicht in der Umsetzung neu aufgerollt wird.**
2. **Lange URLs/Adressen — `break-words`, `break-all` oder Kürzung?** →
   **`break-words` (`overflow-wrap: anywhere`) am Prose-Container in
   `LegalArticle`, nicht je Seite** → weil der Defekt, falls er auftritt, alle
   vier Textseiten gleichzeitig trifft und `LegalArticle` der gemeinsame Träger
   ist. `break-all` wird verworfen: es zerlegt auch normale Wörter und macht
   deutschen Fließtext unleserlich.
3. **`text-3xl` auf `LegalArticle.tsx:27` responsiv abstufen?** → **nur bei
   gemessenem Überlauf**, dann `text-2xl sm:text-3xl` → weil §4.4 keine
   Schriftgrößen-Skala vorschreibt und eine Abstufung ohne Defekt eine
   Designentscheidung wäre. Gemessen wird mit dem längsten realen Titel der
   vier Seiten, nicht mit einem konstruierten.
4. **Die zwei `size="sm"`-Buttons im Cookie-Banner (`:48`, `:51`)** → **auf
   Standardgröße unterhalb `md`, wenn die Messung < 40 px ergibt** → weil §11
   das A11y-Minimum setzt und der Banner die erste interaktive Fläche ist, die
   ein neuer Besucher auf dem Handy trifft. §4.4 Checklistenpunkt 4 nennt
   genau diese `size="sm"`-Verdichtung.
5. **`LegalLayout.tsx:27` (`justify-between` ohne `flex-wrap`)** →
   **`flex-wrap`** → weil das dem Repo-Muster folgt (`PageHeader.tsx:37`) und
   keine breakpoint-abhängige Render-Variante einführt.
6. **Tests wohin?** → **`*.test.tsx` neben die geänderte Datei**, nach dem
   Muster von W2/#513. Der Banner ist die am besten testbare Komponente der
   Domäne (Zustandswechsel akzeptiert/abgelehnt ist bereits belegt).

### Acceptance criteria

- [ ] Auf 320, 375, 768 und 1024 px erzeugt keine Route unter `/legal/*`
      horizontalen Body-Scroll.
- [ ] **Die vier Rechtstexte sind auf 320 px vollständig lesbar** — lange URLs,
      E-Mail-Adressen und Registerangaben brechen um statt überzulaufen;
      Überschriften werden nicht abgeschnitten.
- [ ] **Die beiden Buttons im Cookie-Banner erreichen unterhalb `md` ≥ 40 px
      Hit-Target** (§11 A11y-Minimum) — gemessen, nicht angenommen.
- [ ] `LegalLayout.tsx:27` bricht auf 320 px um oder passt vollständig.
- [ ] Der Cookie-Banner überdeckt auf 320 px keinen Bedienpfad dauerhaft und
      bleibt vollständig im Viewport (er ist `fixed`, `:25`).
- [ ] Mehrspaltige Grids sind an einen Breakpoint gebunden. Gate, liefert
      **keine** Zeile (heute wie nachher — die Domäne hat kein `grid-cols-*`):
      ```bash
      grep -rnE '(^|[^:a-z-])grid-cols-[2-9]' --include='*.tsx' \
        apps/web/src/features/legal | grep -v '\.test\.tsx'
      ```
- [ ] **Alle 8 Dateien sind in der Ist-Tabelle mit Befund oder begründetem
      „kein Defekt" abgehakt** — keine ungeprüfte Datei. Für die fünf
      prefixlosen gilt die Begründung aus Weiche 1, nicht ein pauschales
      „nichts zu tun".
- [ ] Jeder neue Testfall war **vor** der Änderung rot (Test-first, CLAUDE.md
      §Workflow); die Coverage-Thresholds aus `apps/web/vite.config.ts:49-53`
      halten (Branches-Floor **79**).

### Scope

Genau die 8 Dateien unter `apps/web/src/features/legal/`, ihre Testnachbarn,
und `CHANGELOG.md` (§Unreleased, ein Eintrag, **als letzter Commit** —
Sammelpunkt).

### Out of scope

`components/ui/*` und `components/layout/*` (inkl. `Container` — W2 hat dort
entschieden; eine Änderung wirkt auf alle dreizehn Domänen und ist ein eigenes
Paket) · **`features/auth`** (seit 2026-09-15 eigenes W3-Paket) · jede
inhaltliche Änderung an den Rechtstexten selbst (das ist keine Responsive-
Arbeit und braucht eine andere Zuständigkeit) · jede andere Domäne unter
`features/` · W4 (Playwright-Mobile-Profile, E2E-Helfer „kein horizontaler
Body-Scroll") · echter Fullscreen-Dialog unter `sm` (#513 Weiche 3, verworfen) ·
ESLint-Regel für nackte `grid-cols-*` (#438 Weiche 5, verworfen) · `apps/api`,
`apps/mcp`, `packages/**`.

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
AK 6 gibt keine Zeile aus.

**Umgebung:** kein Docker-Daemon nötig (reines Web-Paket, Vitest ist DB-frei).
Das Paket fasst `apps/web/**` an und steht **nicht** auf der Doku-Allowlist
(`ci.yml:74`) — die schweren CI-Jobs laufen.

### Verweise

Tracking: **#431** (W3, Checklisteneintrag „Legal (Impressum, Datenschutz,
AGB)"; die Trennung von `auth` ist im Block vom 2026-09-15 hergeleitet). Norm:
`docs/frontend/design-language.md` §4.4 (Mobile-first, Prefix-Pflicht,
sechspunktige Review-Checkliste Z. 222–233) und §11 (A11y-Minimum 40 px),
CLAUDE.md §Frontend-Standards. Vorgänger: **#438** (W0), **#500** (W1 —
Schwelle `md`, `useEffect`-freies Muster), **#513** (W2 — Dialog-Inset, Caps im
Primitive, `tailwind-merge`).

**Kollision:** fasst `apps/web` an — nicht parallel zu einem anderen
`apps/web`-Paket im selben Arbeitsbaum, sondern nacheinander oder in getrennten
Worktrees (#442 §Wellen). **`legal` und `auth` liegen beide am
i18n-Sammelpunkt** (`apps/web/src/i18n/locales/{de,en}.json`) und teilen den
Vitest-Baum — je zwei gleichzeitig nur in getrennten Worktrees, i18n je Paket
auf **einen** Namespace. Die drei größten W3-Pakete (`playbooks` 16, `workarea`
14, `personas` 13) laufen nie zu zweit gleichzeitig.

### Component

Web UI (apps/web)

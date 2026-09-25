# 566 — W3 System Prompts: Responsive-Audit von `features/system-prompts` (7 Dateien)

Stand: 2026-09-23 · Branch `who2be/t_6419d6e4-566-w3-system-prompts-responsive-audit-v`
Basis: `origin/main` @ `9a05a4e8` · Issue: #566 (agent-ready) · Epic: #431 (W3)

## Auftrag

Die sieben produktiven `.tsx` unter `apps/web/src/features/system-prompts/`
bei 320 / 375 / 768 / 1024 px gegen die sechspunktige Review-Checkliste aus
`docs/frontend/design-language.md` §4.4 prüfen; gefundene Defekte beheben,
nicht gefundene begründet als „kein Defekt" abhaken. Der Cap des
Platzhalter-Popovers ist **am gerenderten Popover nachzuweisen**, nicht zu
ändern (Weiche 1). Keine Änderung an geteilten Primitives
(`components/ui|layout|data|version/*`).

## Methode — gemessen, nicht geschätzt

jsdom hat kein Layout. Deshalb lief eine **Wegwerf-Messharness**
(`apps/web/probe.html` + `apps/web/src/probe.tsx`, **nicht committet**) gegen
den echten Vite-Dev-Server und wurde per Chrome DevTools Protocol vermessen:
`Emulation.setDeviceMetricsOverride` auf 320/375/768/1024 px, dann je Route
alle Elemente mit `getBoundingClientRect().right > clientWidth` eingesammelt,
dazu `document.body.scrollWidth`, Hit-Target-Höhen und `scrollWidth` je
Container. Sprache fix auf `de` — die deutschen Labels sind durchgehend länger
als die englischen und damit der harte Fall.

Fixture bewusst pessimistisch: 65-Zeichen-Name, ein trennstellenfreier
Unterstrich-Slug (`kundenonboarding_systemprompt_vertriebsteam_langbezeichner_q4_2026`,
so leitet die API ihn aus dem Namen ab), 132-Zeichen-Beschreibung, zwei
Templates, Versionsliste, alle drei Status der Aktionsleiste
(`draft`/`review`/`inactive`). Ein Schalter `?shortname=1` setzt den Namen auf
„Onboarding" zurück — nur so lassen sich die domäneneigenen Befunde von denen
der geteilten Primitives trennen (siehe §„Bewusst nicht geändert").

## Ist-Zustand nachgemessen (auf `9a05a4e8`)

```bash
find apps/web/src/features/system-prompts -name '*.tsx' \
  ! -name '*.test.tsx' ! -name '*test-utils*' ! -path '*/test/*' | wc -l   # 7
find … -exec grep -lE '\b(sm|md|lg|xl|2xl):' {} \;    # nur components/PlaceholderHelp.tsx
grep -rnE '(^|[^:a-z-])grid-cols-[2-9]' --include='*.tsx' \
  apps/web/src/features/system-prompts | grep -v '\.test\.tsx'            # (leer, exit 1)
grep -rn 'min-w-0' apps/web/src/features/system-prompts                   # (leer)
```

Bestätigt: 7 Dateien, 1 Breakpoint-Prefix, kein mehrspaltiges Grid, null
`min-w-0` — exakt die Zahlen des Issues, keine Drift.

### Gemessener Body-`scrollWidth` je Route (Langname-Fixture)

| Route | 320 | 375 | 768 | 1024 |
|---|---|---|---|---|
| `/system-prompts` | 608 | 608 | 856 | 1009 ✓ |
| `/system-prompts/sp1` | 931 | 931 | 1179 | 1179 |
| `/system-prompts/new` | 320 ✓ | 375 ✓ | 753 ✓ | 1024 ✓ |
| `/help/placeholders` | 320 ✓ | 375 ✓ | 753 ✓ | 1009 ✓ |

Mit `?shortname=1` (Name kurz, Slug weiter lang) bleibt:

| Route | 320 | Überläufer |
|---|---|---|
| `/system-prompts` | **590** | Slug-Badge, 497 px |
| `/system-prompts/sp1` | **577** | Slug-Badge, 497 px |

Damit ist der Überlauf sauber zerlegt: 497 px kommen aus der **eigenen
Domäne** (Slug-Badge), der Rest aus zwei geteilten Primitives, die diese Karte
nicht anfassen darf.

## Befund je Datei — alle sieben abgehakt

| # | Datei | §4.4-Punkt | Befund |
|---|---|---|---|
| 1 | `pages/SystemPromptsPage.tsx` | 5 | **Defekt.** Slug-Badge (`:119`, `font-mono`, kein Umbruch) misst gerendert **497 px** bei 320 px Viewport und ist der einzige domäneneigene Überläufer der Liste (`body.scrollWidth` 590). `slug` wird serverseitig aus dem Namen abgeleitet — ein einziges Wort ohne Trennstellen. |
| 2 | `pages/SystemPromptDetailPage.tsx` | 5 | **Defekt, gleiche Ursache.** Slug-Badge im `DetailHeader`-`badges`-Slot (`:55`), gemessen **497 px**, `body.scrollWidth` 577. Sonst kein Befund: kein Grid, keine feste Breite, keine `justify-between`-Zeile — bestätigt. Versionsmetadaten und Tabs bei 320 px ohne eigenen Überlauf. |
| 3 | `components/SystemPromptEditorForm.tsx` | 1 | **Defekt (latent, gemessen).** `:123` `flex items-center justify-between` ohne `flex-wrap`. Mit dem heutigen Label „Body" (32 px) passt die Zeile (238 px Container, Trigger 196 px). Bei einem längeren Label — gemessen mit „Prompt-Text des Systemprompts", 97 px — bricht die Zeile **nicht** um: der Trigger wird auf `right: 335` geschoben, `body.scrollWidth` springt von 320 auf **335**. Die Zeile hat keine Reserve; AK 3 adressiert genau das. |
| 4 | `pages/SystemPromptNewPage.tsx` | 1 | **Defekt, zweite Fundstelle derselben Zeile** (`:142`), identisch gemessen. Sonst kein Befund: `Container` + `Stack`, einspaltig, rechtsbündige Submit-Aktion, 0 Überläufer auf allen vier Viewports. |
| 5 | `components/PlaceholderHelp.tsx` | 1, 5 | **Teils erfüllt, ein Defekt.** `:87` Definitionslisten-Grid ist mobile-first gebunden (`grid-cols-1 sm:grid-cols-[10rem_1fr]`) — **kein Defekt**, gemessen: bei 320 px eine Spalte à 270 px. `:121` `w-96` am `PopoverContent` — **kein Defekt**: gerendert misst das Popover **304 px bei `left: 8` / `right: 312`**, liegt also vollständig im 320-px-Viewport; der Primitive-Cap `max-w-[calc(100vw-1rem)]` greift wie in W2 entschieden (Weiche 1: nachweisen, nicht ändern). `:89` Platzhalter-`dt` in Monospace — **Defekt**: ein trennstellenfreier Platzhaltername lässt `body.scrollWidth` auf **465** springen und drückt das Icon auf Breite **0**. |
| 6 | `components/SystemPromptStatusActionBar.tsx` | 1, 4 | **Kein Defekt**, gemessen in allen drei Status bei 320 px: `draft` (ein Button, 171 px), `review` (zwei Buttons, Leiste 229 px), `inactive` (162 px) — alle innerhalb der 288 px Containerbreite, `body.scrollWidth` 320. Hit-Targets **40 px** (`size="default"`), über dem verbindlichen Floor von ≥ 32 px (§11) und auf dem Regelfall. Kein `flex-wrap` nötig: Weiche 1 aus #431 verbietet einen Prefix ohne gemessenen Defekt. |
| 7 | `pages/HelpPlaceholdersPage.tsx` | 1–6 | **Kein Defekt.** 42 Zeilen über `Container` + `Stack`; 0 Überläufer auf allen vier Viewports. Der Zurück-Button ist `size="sm"` (36 px) — nach §11 zulässig, kein Defekt. Die Seite erbt den Fix aus #5, weil sie denselben `PlaceholderHelpContent` rendert. |

## Fix — vier Stellen, kein einziger neuer Breakpoint-Prefix

Weiche 1 aus #431 gilt: kein Prefix ohne gemessenen Defekt. Alle vier Fixes
kommen ohne aus.

1. **Slug-Badges** (`SystemPromptsPage.tsx`, `SystemPromptDetailPage.tsx`) —
   `max-w-full break-all` an der Aufrufstelle. Identisch zur bereits gemergten
   Lösung in `features/tools` (PR #595) und `features/resources` (PR #599),
   kein Pattern-Drift. `break-all`, nicht `break-words`: der Slug hat keine
   Trennstellen und muss mitten im Wort brechen dürfen.
2. **Die beiden `justify-between`-Zeilen** — `flex-wrap` plus `gap-2` an der
   Zeile. Weiche 2 des Issues, Repo-Muster `components/layout/PageHeader.tsx`
   (`flex flex-wrap items-center gap-2` im Actions-Slot). Keine zweite,
   breakpoint-abhängige Render-Variante.
3. **Platzhalter-`dt`** (`apps/web/src/features/system-prompts/components/PlaceholderHelp.tsx@ac18c4d9#PlaceholderHelpContent`) — Weiche 3: kontrolliert
   kürzen statt umbrechen. `min-w-0` am `dt` (sonst greift `truncate` im
   Flex-Kind nicht), `shrink-0` am Icon (es wurde sonst auf 0 gequetscht), und
   der Name selbst in ein `<span className="min-w-0 truncate">` mit `title` —
   der vollständige Platzhaltername bleibt so über den Tooltip erreichbar,
   wie die Weiche es verlangt. Wirkt zugleich auf `HelpPlaceholdersPage`, weil
   beide denselben `PlaceholderHelpContent` rendern.

## Bewusst nicht geändert — Primitive-Funde für den Handoff

Nach den vier Fixes bleibt bei 320 px Rest-Überlauf. Er stammt **vollständig**
aus geteilten Primitives, die diese Karte ausdrücklich nicht anfassen darf
(Kartenkommentar des PM, Out-of-Scope des Issues):

1. **`components/data/DetailHeader.tsx`** — die `<h1>` trägt keine
   Umbruch-Regel und misst mit dem 65-Zeichen-Namen **851 px**; größter
   Einzelposten des `scrollWidth` auf der Detail-Seite. Bereits als eigene
   Karte **t_126558ba** entschieden (`break-words`, kein `line-clamp`) — hier
   nur bestätigt, nicht doppelt gemeldet.
2. **`components/data/EntityCard.tsx`** — der Titel-Link der Listenkarte misst
   mit demselben Namen **515 px**. Gehört zur selben Karte t_126558ba.

Kein neuer Primitive-Fund über die bereits bekannten hinaus. Insbesondere
`components/ui/popover.tsx` blieb unberührt: sein Cap ist gemessen wirksam
(304 px bei 320 px Viewport).

## Test-first (AK 8)

Neun Fälle, alle **vor** der Änderung rot. jsdom hat kein Layout — der Vertrag
in den Tests ist ein Klassen-Vertrag; die Layout-Aussagen selbst stehen oben
mit Zahlen. Ausnahme: der Popover-Cap wird am gerenderten Popover geprüft
(AK 2 verlangt genau das) — dort assertiert der Test, dass die
Primitive-Cap-Klasse am tatsächlich gerenderten Knoten hängt und `w-96` sie
nicht auslöscht, ergänzt um die gemessene Zahl im Kommentar.

## Verifikation

```bash
cd apps/web
npm run lint
npx tsc -b
npm run test:coverage
npm run test:a11y
npm run build
npm run license:check
```

Aus dem Repo-Root:

```bash
uv run python scripts/check_code_refs.py .
uv run python scripts/changelog_fragments.py check
```

Changelog als Fragment `changelog.d/i566-system-prompts-responsive.fixed.md`
(nicht in `CHANGELOG.md` — `changelog-guard` weist das ab).

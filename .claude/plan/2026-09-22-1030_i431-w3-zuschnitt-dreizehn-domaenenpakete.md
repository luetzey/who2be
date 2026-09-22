# W3 zuschneiden: Feature-Audit je Domäne — dreizehn Pakete

Kanban-Karte `t_1354705f` · Branch `wt/i431-w3-zuschnitt` · Basis `main` @ `87de64c`
Tracking-Issue: **#431** (Welle 3) · Queue: **#442**

## Ziel (Completion Condition, messbar)

Dreizehn Issues in `luetzey/who2be` angelegt — eines je Domäne unter
`apps/web/src/features/` —, jedes mit Ziel, Ist-Zustand, Akzeptanzkriterien,
Scope, Out-of-Scope, Verifikations-Kommandos nach Repo-Norm (Vorbild: #513),
jedes per `Tracking: #431` an #431 gehängt. Die W3-Domänen-Zeile in #431
verweist auf die dreizehn Nummern. **Kein Produktionscode angefasst.**

## Was vor dem Zuschnitt gelesen und nachgemessen wurde

| Quelle | Gelesen |
|---|---|
| #431 Body, Block 2026-09-15 | Auth/Legal-Trennung → zwei Pakete, nicht „öffentliche Seiten" |
| #431 Body, Block 2026-09-14 | Billing-Fund, `__CLOUD_BUILD__`, Variante 1 (eigenes Paket) |
| #431 Body, Block 2026-09-12 | Pathspec-Falle (`**/` übergeht Wurzel), `tsc --noEmit` prüft 0 Dateien |
| #431 Kommentar 2026-09-13 | Nenner-Korrektur 216 → 213, voller Ausschluss |
| #431 Kommentar 2026-09-19 | Zeiger `index.html:7` → `:8`; Breakpoint-Kommando mit `\b` |
| #442 §Kollisionen | Pathspec-Falle, Ausschluss-Falle, Billing-Flagge, Sammelpunkte |
| CONTRIBUTING.md §DoD, CLAUDE.md §DoD Frontend | Verifikations-Kommandos |
| `docs/frontend/design-language.md` §4.4 | sechspunktige Review-Checkliste (Z. 222–233) → Basis der AKs |

### Eigene Nachmessung auf `main` @ `87de64c` (nicht übernommen)

```
find apps/web/src -name '*.tsx'                                    -> 386
find apps/web/src -name '*.tsx' ! -name '*.test.tsx'               -> 216
+ ! -name '*test-utils*' ! -path '*/test/*'                        -> 213
```

Domänenbestand (voller Ausschluss), einzeln gezählt — **deckungsgleich mit #431**:

| Domäne | n | Domäne | n | Domäne | n |
|---|---|---|---|---|---|
| playbooks | 16 | auth | 9 | resources | 6 |
| workarea | 14 | settings | 8 | feedback | 6 |
| personas | 13 | legal | 8 | dashboard | 5 |
| agents | 10 | system-prompts | 7 | tools | 4 |
| | | | | billing | 1 |

**Summe 107 bei 13 Domänen.** `ls apps/web/src/features/` liefert genau diese
dreizehn Verzeichnisse — kein vierzehntes, keines ohne Paket.

Breakpoint-Abdeckung je Domäne (`grep -lE '\b(sm|md|lg|xl|2xl):'`, voller
Ausschluss): billing 1/1 · dashboard 1/5 · feedback 3/6 · legal 3/8 ·
personas 1/13 · playbooks 3/16 · settings 3/8 · system-prompts 1/7 ·
**agents 0/10 · auth 0/9 · resources 0/6 · tools 0/4 · workarea 0/14**.
Summe 16 von 107 — fünf Domänen tragen **keinen einzigen** Breakpoint-Prefix.

Nackte Mehrspalten-Grids unter `features/`: **null** (bestätigt W2/#513).

## Abweichung vom Kartenbody — belegt

Die Karte warnt: „CLAUDE.md:152 und :234 dokumentieren noch `npx tsc --noEmit`".
**Trifft nicht mehr zu.** PR #549 ist gemergt (`2ab5246`, `e062c01`);
`CLAUDE.md:152` liest `- Typecheck: \`npx tsc -b\`` und `:234` ebenso.
Folgenlos für den Zuschnitt — die Vorgabe `tsc -b` gilt unverändert und steht
so in allen dreizehn Bodys.

## Vorentschieden (keine Owner-Frage, Zuschnitt-Zuständigkeit)

1. **Schnitt = Verzeichnis unter `features/`.** Deckungsgleich mit der Tabelle
   in #431 und mit `ls features/`. Kein Paket faltet zwei Domänen.
2. **`billing` bleibt eigenes, dreizehntes Paket** (Variante 1 aus dem
   2026-09-14-Block, dort empfohlen). Sein Verifikationsabschnitt setzt
   `VITE_WHO2BE_EDITION=cloud`; die übrigen zwölf bleiben beim Default-Build.
3. **`auth` und `legal` sind zwei Pakete** (Entscheidung 2026-09-15).
4. **AK-Gerüst = §4.4-Review-Checkliste**, nicht frei formuliert — sechs
   Punkte, je Paket auf die gemessenen Fundstellen der Domäne instanziiert.
5. **Verifikation je Paket:** `npm run lint`, **`npx tsc -b`**,
   `npm run test:coverage`, `npm run build` aus `apps/web/`. Nie `--noEmit`.
6. **W3 erbt und entscheidet nicht neu:** Schwelle `md` (W1/#500), das
   `useEffect`-freie Muster (W1), Dialog-Inset + Popover-/Dropdown-Caps
   (W2/#513). Steht in jedem der dreizehn Bodys.
7. **`StatusActionBar` als Bottom-Bar** (aus W2 verschoben) ist **kein**
   vierzehntes Paket und gehört in keines der dreizehn — die Komponente liegt
   unter `components/version/`, nicht unter `features/`, und braucht einen
   Design-Beschluss. Bleibt in #431 als offener Punkt stehen.
8. **Labels je Paket:** `web`, `agent-ready`, dazu `size/S` (≤ 8 Dateien) bzw.
   `size/M` (> 8 Dateien).

## Schritte

- [x] 1. Kontext lesen (#431 Body + 6 Kommentare, #442, CONTRIBUTING, CLAUDE.md, §4.4)
- [x] 2. Bestand auf `87de64c` selbst nachmessen (Nenner, 13 Domänen, Breakpoints, Grids)
- [x] 3. Plan ablegen (diese Datei)
- [x] 4. Body-Template festschreiben (`.claude/plan/w3/_template.md`)
- [x] 5. Dreizehn Bodys erarbeiten. **Abweichung vom Plan:** die Delegation an
      Sub-Agents war in diesem Lauf nicht verfügbar (kein Delegations-Budget);
      die Bodys sind stattdessen inline erarbeitet — **mit derselben Regel, dass
      jeder `datei:zeile`-Zeiger im Repo gemessen und nicht aus #431 übernommen
      wird**. Ausgabe je Domäne unter `.claude/plan/w3/<domaene>.md`.
      (`agents` liegt als `agents-domain.md` — der Dateiname `agents.md` ist
      als Agent-Instruction-Datei schreibgeschützt.)
- [x] 6. Review-/Konsolidierungsphase: Pflichtfelder je Body maschinell geprüft
      (13/13 vollständig), Summe der Paketgrößen **107 = 107** gegen den
      gemessenen Nenner, dreizehn Domänen = dreizehn Pakete.
- [x] 7. Dreizehn Issues angelegt: **#561–#573**, je `web` + `agent-ready` +
      `size/S|M`.
- [x] 8. #431 fortgeschrieben: W3-Zeile auf `[x]`, Tabelle #561–#573, die sechs
      Nachmess-Funde und die Zeiger-Verifikation ergänzt; `StatusActionBar`
      bleibt als offener Punkt stehen.
- [x] 9. CHANGELOG/DECISIONS: **nicht** — der Zuschnitt ändert kein Verhalten und
      keine Doku-Seite; er erzeugt Issues. Plan-Datei ist der Repo-Nachweis.
- [ ] 10. Branch pushen, PR öffnen (nur `.claude/plan/**` → Doku-Allowlist,
      schwere Jobs skippen), CI grün, Review anfordern

## Ergebnis: die dreizehn Pakete

| Issue | Domäne | n | Label |
|---|---|---|---|
| #573 | playbooks | 16 | size/M |
| #572 | workarea | 14 | size/M |
| #571 | personas | 13 | size/M |
| #570 | agents | 10 | size/M |
| #569 | auth | 9 | size/M |
| #568 | settings | 8 | size/S |
| #567 | legal | 8 | size/S |
| #566 | system-prompts | 7 | size/S |
| #565 | feedback | 6 | size/S |
| #564 | resources | 6 | size/S |
| #563 | dashboard | 5 | size/S |
| #562 | tools | 4 | size/S |
| #561 | billing | 1 | size/S |

**Summe 107** — deckungsgleich mit dem nachgemessenen Nenner.

### Funde, die beim Messen entstanden (nicht aus #431 übernommen)

1. **`playbooks` ist 2/16 breakpoint-abgedeckt, nicht 3/16.** Der Treffer in
   `PlaybookRow.tsx:71` steht in einem Kommentar (`md: 44px`), nicht in einer
   Klasse. Steht als eigener Abschnitt in #573.
2. **`auth` hat 0/9 Prefixe — und das ist korrekt.** Acht der neun Dateien
   folgen wörtlich dem §10.2-Marketing-Page-Muster, das mobile-first ohne
   Prefix konstruiert ist. In #569 als vorentschiedene Weiche festgehalten,
   damit es nicht als Defekt „repariert" wird.
3. **`workarea` ist der Grund für den dreiteiligen Ausschluss:**
   `features/workarea/test-utils.tsx` heißt nicht `*.test.tsx`; ein naiver
   Ausschluss liefert dort 15 statt 14. In #572 dokumentiert.
4. **Zwei Nicht-Befunde in `workarea`** (#572): der Tabellen-Wrapper sitzt im
   Primitive (`table.tsx:14`, `overflow-auto` — #431 suchte `overflow-x-auto`)
   und `whitespace-nowrap` in Datenzellen ist nach §4.4 bewusst richtig.
5. **`settings` hat 8 Dateien, nicht 9** — wer neun zählt, hat `billing`
   mitgezählt. In #568 explizit abgegrenzt.
6. **Die Aufrufer-`max-w-*` an `DialogContent`** (`ResourceBlockLinkPicker.tsx:180`
   `max-w-3xl`, `PlaybookComposesPicker.tsx:103` `max-w-lg`) sind **kein
   Defekt**: `w-[calc(100vw-2rem)]` aus `dialog.tsx:51` bleibt über
   `tailwind-merge` bestehen. In #573 belegt.

### Zeiger-Verifikation (Schritt 6, das Hauptrisiko des Pakets)

Alle Zeiger wurden **maschinell gegen das Repo geprüft**, nicht stichprobenhaft:

```bash
# (a) jede genannte Datei existiert, (b) Zeilenzahl im Body == Repo,
# (c) Zahl der gelisteten Dateien == behauptete Paketgroesse
bash ~/.hermes/profiles/coder/cache/scratch/w3files.sh   # -> Probleme: 0
```

**Ergebnis: 107/107 Dateien existieren, alle Zeilenzahlen exakt, alle dreizehn
Paketgrößen konsistent.** Zusätzlich wurden ~240 `datei:zeile`-Klassenzeiger
extrahiert und gegen die jeweilige Quellzeile geprüft.

**Vier echte Drift-Funde, alle korrigiert und die Issues nachgezogen:**

| Body | Zeiger | war | ist |
|---|---|---|---|
| personas.md | `PersonaSkillsTable.tsx` `w-1/3` | `:41` | **`:40`** |
| personas.md | `PersonaModesEditor.tsx` `size="sm"`-Aktionen | `ab :289` | **`:292`, `:303`** |
| settings.md | `SettingsNav.tsx` `flex-wrap` | `<nav …>` auf `:35` | **`className` auf `:35`, `<nav>` ab `:33`** |
| playbooks.md | `PlaybookRow.tsx` `PlaybookTypeIcon` | `:75` | **`:74`** |

Zusätzlich in `playbooks.md`: die Dateinamen standen verkürzt als
`components/X.tsx` — mehrdeutig, weil `apps/web/src/components/` ebenfalls
existiert. Auf `features/playbooks/…` vereinheitlicht.

**Aktualisierte Issues:** #571, #568, #573.

## Verifikation dieses Pakets

```bash
# 1. dreizehn Issues existieren und hängen an #431
gh issue list --search "W3 Feature-Audit in:title" --state open --limit 20

# 2. keine Produktivdatei angefasst
git diff --name-only origin/main...HEAD   # nur .claude/plan/**

# 3. kein Body nennt das wirkungslose Kommando
grep -rn 'tsc --noEmit' .claude/plan/w3/  # -> leer
```

## Out of scope

Implementierung der dreizehn Audits selbst · W4 (Playwright-Mobile-Profile) ·
`StatusActionBar`-Bottom-Bar · `.github/PROJECT.md`-Reparatur (#442 offene
Owner-Frage) · jede Änderung an `apps/web/**`, `apps/api/**`, `packages/**`.

## Risiken

- **Zeiger-Drift** — höchstes Risiko, hat in früheren Läufen mehrere Issues
  beschädigt. Gegenmittel: Schritt 5 misst, Schritt 6 misst gegen.
- **Ungleiche Paketgrößen** — `playbooks` 16 / `workarea` 14 / `personas` 13
  sind die drei größten; die Bodys tragen die Kollisionsnotiz „nie zwei der
  drei größten parallel, i18n je Paket auf einen Namespace".
- **Sammelpunkte** `i18n/locales/{de,en}.json`, `components/ui/*`,
  `CHANGELOG.md` — jedes Paket fasst sie zuletzt an; `billing` ist am
  i18n-Sammelpunkt nicht beteiligt (ADR-0029).

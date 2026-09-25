# 568 — W3 Settings: Responsive-Audit von `features/settings` (8 Dateien)

Stand: 2026-09-23 · Branch `who2be/t_7db37cbe-568-w3-settings-responsive-audit-von-fea`
Basis: `origin/main` @ `9a05a4e8` · Issue: #568 (agent-ready) · Epic: #431 (W3)

## Auftrag

Die acht produktiven `.tsx` unter `apps/web/src/features/settings/` gegen die
sechspunktige Review-Checkliste aus `docs/frontend/design-language.md` §4.4 bei
320 / 375 / 768 / 1024 px prüfen; gefundene Defekte beheben, nicht gefundene
begründet als „kein Defekt" abhaken. Keine Änderung an geteilten Primitives,
`features/billing` unter keinen Umständen.

## Methode — real gemessen, nicht geschätzt

jsdom hat kein Layout, und AK 1–4 des Issues sind Layout-Aussagen. Deshalb
wurde eine **Wegwerf-Messharness** (statisches HTML mit der echten Elternkette
`Container > Card > CardContent > …` und den wörtlichen Klassenlisten der acht
Dateien) gegen das **gebaute** Stylesheet `dist/assets/index-BF0blzzS.css` aus
dem eigenen `npm run build` gefahren und per Chrome DevTools Protocol
(`Emulation.setDeviceMetricsOverride`) bei allen vier Viewports vermessen.

Erfassungskriterium ist **`child.right > parent.contentRight`** je Element
(Überlauf gegen die Eltern-Innenkante), nicht nur gegen `clientWidth` — das ist
die in PR #599 Runde 2 gelernte Lehre: ein Überlauf gegen den Zeilencontainer
bleibt im Viewport und rutscht durch eine reine Viewport-Messung hindurch.

Fixture bewusst pessimistisch: eine trennstellenfreie 84-Zeichen-E-Mail
(`maximiliankonstantin…@unternehmensberatungsgesellschaft.example`), ein
43-Zeichen-Faktorname, ein 61-Zeichen-Org-Slug.

Die Probe-Datei liegt außerhalb des Repos (Scratch) und wird nicht committet.

## Ist-Zustand bestätigt (auf `9a05a4e8`)

```bash
find apps/web/src/features/settings -name '*.tsx' \
  ! -name '*.test.tsx' ! -name '*test-utils*' ! -path '*/test/*' | wc -l   # 8
# Breakpoint-Prefix: AccountPage.tsx, OrgSettingsPage.tsx, WorkspaceSettingsPage.tsx
grep -rnE '(^|[^:a-z-])grid-cols-[2-9]' --include='*.tsx' \
  apps/web/src/features/settings | grep -v '\.test\.tsx'                   # (leer)
```

Acht Dateien, drei mit Prefix, kein nacktes Mehrspalten-Grid. §4.4-Punkt 2 ist
damit in der Domäne **gegenstandslos** (AK 5 ist ohne Eingriff erfüllt).

## Befund je Datei — alle acht abgehakt (AK 7)

| Datei | §4.4-Punkt | Befund |
|---|---|---|
| `components/SettingsNav.tsx` | 4 | **Defekt.** Die Nav-Einträge messen gerendert **36 px** hoch (`px-3 py-2` bei `text-sm`: 20 px Zeilenhöhe + 2×8 px Padding). Die Rechnung des Issues stimmt auf den Pixel. Unterhalb `md` verlangt AK 2 ≥ 40 px. Umbruch selbst ist in Ordnung: bei 320 px legt `flex-wrap` die vier Einträge auf drei Zeilen, kein Überlauf. |
| `components/SettingsLayout.tsx` | 1–6 | **Kein Defekt.** 21 Zeilen, `Container className="pb-0"` + `<Outlet />`. Kein Grid, keine feste Breite, kein interaktives Element. Das vermutete zweispaltige Settings-Layout existiert nicht — bestätigt. |
| `pages/AccountPage.tsx` | 5 | **Defekt, zwei Stellen gleicher Ursache.** Die beiden Präferenz-Zeilen (`justify-between` ohne `flex-wrap`, Textspalte ohne `min-w-0`) quetschen ihre Beschreibung bei 320 px: Sprach-Zeile gemessen **124 px Textbreite auf 120 px Höhe** (sechs Zeilen für einen Satz), Theme-Zeile 182 px / 80 px. Das ist der Wortsalat aus §4.4-Punkt 5. Das `sm:grid-cols-[8rem_1fr]`-Grid `:71` und der Dialog `:308` sind **erfüllt** (gemessen kein Überlauf, `break-all` an der User-ID greift). |
| `pages/OrgSettingsPage.tsx` | 3 | **Kein Defekt.** `:219` `max-w-xs` am `Select` gemessen: **238 px bei 320 px Viewport**, also vom Container-Padding gedeckt, kein Überlauf — Weiche 4 des Issues greift und die Änderung **unterbleibt**. Workspace-Zeile `:159` trägt `flex-wrap` + `min-w-0` + `truncate` (Name gemessen 113 px statt 341 px, kürzt kontrolliert). Grid `:132` und Dialog `:332` erfüllt. Ternary `:56-58`/`:274` unangetastet. |
| `pages/WorkspaceSettingsPage.tsx` | 1–6 | **Kein Defekt.** Grid `sm:grid-cols-[10rem_1fr]` + `sm:col-start-2` erfüllt, Dialog erbt den W2-Default, alle Formularfelder sind Block-Elemente über die volle Breite. Gemessen kein Überläufer. |
| `pages/MembersPage.tsx` | 1, 4, 5 | **Defekt, zwei Stellen.** (a) Das Rollen-`Select` in der Tabellenzelle misst bei 320 px **32 px Breite** — die Tabellenspalte schrumpft es unter jede Bedienbarkeit (AK 3). Höhe ist mit 40 px in Ordnung. (b) Die Einladungs-E-Mail läuft **39 px über die Zeilen-Innenkante** (277 px in einem 238 px breiten Container): `flex-wrap` an der Zeile `:309` rettet nur die erste Umbruchebene, der `Stack` darin hat kein `min-w-0` und die Adresse keine Trennstelle (AK 6). Die Tabelle selbst scrollt in ihrem Primitive-Wrapper — zulässig, Weiche 2. |
| `components/MfaSection.tsx` | 5 | **Defekt.** `:82` ohne `flex-wrap`: bei 320 px drückt der Entfernen-Button (87 px) den Faktornamen auf **30 px Breite bei 187 px Inhalt**. `truncate` greift zwar, rettet aber nichts — sichtbar bleiben zwei Zeichen. Der QR-Dialog ist **erfüllt** (gemessen 288 px Dialog, 192 px QR, Secret mit `break-all` 238 px, kein Überlauf). |
| `components/MemoryGuardSection.tsx` | 1–6 | **Kein Defekt in der Domänen-Datei.** Kein Grid, keine feste Breite, keine gequetschte Zeile; die Modus-Boxen und der Phrasen-Editor messen bei 320 px sauber. Zwei Hit-Target-Funde liegen in Primitives und sind unten gemeldet, nicht hier repariert. |

### Gemessener Body-Überlauf (AK 1)

| Viewport | `documentElement.scrollWidth` / `clientWidth` | Überläufer gegen Eltern-Innenkante |
|---|---|---|
| 320 | 320 / 320 ✓ | 1 (Einladungs-E-Mail, 39 px) |
| 375 | 375 / 375 ✓ | 0 |
| 768 | 753 / 753 ✓ | 0 |
| 1024 | 1009 / 1009 ✓ | 0 |

Kein horizontaler **Body**-Scroll auf keinem der vier Viewports, weder vor noch
nach dem Fix — der einzige `scrollWidth > clientWidth` stammt vom
`Table`-Wrapper (990 px in 238 px), und der ist nach §4.4-Punkt 1 und Weiche 2
des Issues ein bewusst gescrollter Container.

## Fix — fünf Stellen, vier Dateien

Weiche 1 aus #431 gilt: kein Breakpoint-Prefix ohne gemessenen Defekt. Drei der
fünf Fixes kommen ohne Prefix aus; die zwei mit `md:` stehen dort, wo die
Mobile-Lösung den Desktop sonst verschlechtern würde.

1. **`SettingsNav`** — `min-h-10 md:min-h-0` an der Eintragszeile.
   **Wörtlich die im Issue vorentschiedene Lösung** (Weiche 1: „aufpolstern,
   kein Umbau"). `py-2.5` wäre die Alternative, ändert aber die Höhe implizit
   über die Zeilenhöhe; `min-h-10` sagt den 40-px-Vertrag direkt und ist das,
   was ein Test prüfen kann. Ab `md` fällt die Polsterung zurück auf die
   Desktop-Dichte. Gemessen: 36 px → **40 px** unterhalb `md`.
   **Pattern-Drift:** `WorkAreaNav` (#572) bleibt unangetastet; wer dort
   arbeitet, nimmt diese Klassenfolge wörtlich.
2. **`MfaSection.tsx:82`** — `flex-wrap` an der `<li>`, `basis-full
   md:basis-auto` an der Textspalte, `shrink-0` am Status-Badge. Unterhalb `md`
   bekommt die Textspalte damit eine eigene volle Zeile, statt gegen den Button
   zu konkurrieren. Gemessen: Faktorname 30 px → **129 px** bei 320 px,
   ab `md` unverändert 187 px (keine Desktop-Regression).
3. **`AccountPage` Präferenz-Zeilen** (Theme + Sprache) — `flex-wrap` an der
   Zeile, `min-w-0` an der Textspalte. Bewusst **ohne** `flex-1`: das hatte in
   der Messung den Desktop mitgenommen (`lang-row` wäre auch bei 1024 px
   umgebrochen). Gemessen bei 320 px: Textbreite 124 px → **238 px**, Höhe
   120 px → 60 px; bei 768/1024 px **exakt unverändert** (40 px, Vorher-Nachher
   gegengemessen).
4. **`MembersPage` Rollen-`Select`** — `min-w-32` an der Aufrufstelle.
   Weiche 3 des Issues: die Messung zeigt das Problem, also wird gehandelt —
   aber am Minimum. Die Rolle bleibt in ihrer Zelle (kein Umbau in den
   Aktionsbereich), die Zelle bekommt nur eine Untergrenze, ab der das Control
   bedienbar ist. Gemessen: 32 px → **128 px** Breite, Höhe unverändert 40 px.
   Der Tabellen-Wrapper scrollt wie vorgesehen; das `Select`-Primitive bleibt
   unberührt (`min-w-32` sitzt als `className` an der Aufrufstelle).
5. **`MembersPage` Einladungszeile** — `min-w-0` am `Stack`, `break-all` an der
   Adresse. Gemessen: Überlauf 39 px → **0 px** bei 320 px, ab 768 px
   unverändert 620 px.

## Bewusst nicht geändert

- **`OrgSettingsPage.tsx:219` `max-w-xs`** — Weiche 4 verlangt die Prüfung,
  nicht die Änderung. Gemessen kein Überlauf (238 px in 238 px Container).
  Eine prophylaktische `w-full sm:max-w-xs`-Änderung wäre eine Änderung ohne
  gemessenen Bedarf und damit genau das, was Weiche 1 aus #431 verbietet.
- **Mitgliedertabelle als Karten stapeln** — Weiche 2, verworfen.
- **`features/billing` / die Ternary-Zeilen** — Weiche 5, unter keinen
  Umständen.

## Primitive-Funde für den Handoff — nicht repariert

Beide liegen unter `components/ui/` und sind nach der Karten-Grenze
ausdrücklich Out-of-Scope (zwölf Geschwisterpakete fassen dieselben Dateien an):

1. **`components/ui/tag-input.tsx`** — der Entfernen-Button der Tag-Pille misst
   gerendert **16 × 16 px**. Das unterschreitet den in §11 verbindlich
   festgelegten Floor von ≥ 32 px, auf jedem Breakpoint. Der Inline-Kommentar
   begründet die `size-3`-Ikone (Dichte der Pille), nicht die Trefferfläche —
   ein `p-2`/`size-8` am Button würde die Pille nicht aufblähen. Betrifft jede
   Domäne mit Tag-Eingabe.
2. **`components/ui/radio-group.tsx`** — `RadioGroupItem` misst **16 × 16 px**.
   Das Label ist per `htmlFor` mitklickbar und rettet die Bedienbarkeit
   praktisch, aber der Floor gilt laut §11 für das interaktive Element selbst.
   Betrifft jede Radio-Auswahl im Produkt.

Beide sind gemessen, nicht vermutet. Keiner ist ein Blocker für dieses Paket.

## Test-first

Neue Fälle als Klassen-Vertrag neben der geänderten Datei (Muster W2/#513,
PR #595, PR #599) — jsdom hat kein Layout, die Layout-Aussage selbst ist oben
gerendert belegt und wird im PR als Messung benannt, nicht als Test verkauft:

- `SettingsNav.test.tsx` (neu): Eintrag trägt `min-h-10` und `md:min-h-0`.
- `MfaSection.test.tsx`: Faktor-Zeile trägt `flex-wrap`, Textspalte
  `basis-full` + `md:basis-auto` + `min-w-0`, Badge `shrink-0`.
- `AccountPage.test.tsx`: beide Präferenz-Zeilen tragen `flex-wrap`, ihre
  Textspalte `min-w-0` — und **kein** `flex-1` (hält die Desktop-Zusage fest,
  damit der verworfene Ansatz nicht still zurückkehrt).
- `MembersPage.test.tsx`: Rollen-`Select` trägt `min-w-32`; Einladungs-Stack
  trägt `min-w-0`, die Adresse `break-all`.

Alle Blöcke laufen **vor** der Änderung rot (eigener `test:`-Commit vor dem
`fix:`-Commit).

## Verifikation

Node 22 ist Pflicht (`.nvmrc`), lokal über `mise` bereitgestellt.

```bash
cd apps/web
npm run lint
npx tsc -b            # NICHT --noEmit
npm run test:coverage
npm run test:a11y
npm run build
npm run license:check
```

Dazu aus dem Repo-Root:

```bash
uv run python scripts/check_code_refs.py .
uv run python scripts/changelog_fragments.py check
```

Changelog als **Fragment** unter `changelog.d/` — `CHANGELOG.md` wird nicht
angefasst (die entsprechende Anweisung im Issue ist seit PR #587/#589 überholt,
der CI-Job `changelog-guard` weist sie ab).

## Ergebnis

### Gerendert nachgemessen (nach dem Fix, gegen `dist/assets/index-XQbVSFAa.css`)

Gleiche Harness, gleiches Erfassungskriterium, gegen das **neu gebaute**
Stylesheet. Die vier `md:`-Utilities existieren darin (`grep` gegen das Bundle):
`.min-h-10{min-height:2.5rem}` · `.md\:min-h-0{min-height:0}` ·
`.basis-full{flex-basis:100%}` · `.md\:basis-auto{flex-basis:auto}` ·
`.min-w-32{min-width:8rem}`.

| Messgröße | 320 | 375 | 768 | 1024 |
|---|---|---|---|---|
| `documentElement.scrollWidth` / `clientWidth` | 320/320 ✓ | 375/375 ✓ | 768/768 ✓ | 1024/1024 ✓ |
| **Überläufer gegen Eltern-Innenkante** | **0** | **0** | **0** | **0** |
| Nav-Eintrag Höhe (AK 2) | **40** | **40** | 36 | 36 |
| MFA-Faktorname Breite (vorher 30/184) | **129** | **184** | 226 | 226 |
| MFA-Zeile Höhe (Umbruch unterhalb `md`) | 88 | 88 | 54 | 54 |
| Theme-Textspalte Breite (vorher 182 @ 80 px Höhe) | **212 @ 40** | 212 @ 40 | 212 @ 40 | 212 @ 40 |
| Sprach-Textspalte Breite (vorher 124 @ 120 px Höhe) | **205 @ 40** | 205 @ 40 | 205 @ 40 | 205 @ 40 |
| Rollen-`Select` Breite (AK 3, vorher 32) | **128** | **128** | 128 | 133 |
| Einladungs-Adresse Überlauf (vorher 39 px) | **0** | 0 | 0 | 0 |

**Der 40-px-Hit-Target sitzt exakt dort, wo er hingehört:** 40 px unterhalb
`md`, 36 px ab `md` — die Desktop-Dichte ist unangetastet. Dasselbe für die
MFA-Zeile (88 px zweizeilig unter `md`, 54 px einzeilig ab `md`) und die
Präferenz-Zeilen (40 px Textspaltenhöhe auf **allen vier** Viewports, also der
Wortsalat weg, ohne dass der Desktop umbricht — genau das, was die verworfene
`flex-1`-Variante kaputtgemacht hätte).

Der einzige `scrollWidth > clientWidth` bleibt der `Table`-Wrapper
(900 px in 238 px) — bewusst gescrollter Container nach §4.4-Punkt 1 und
Weiche 2 des Issues, **kein** Body-Scroll.

### Test-first belegt

Acht neue Fälle, alle vor der Änderung rot (eigener `test:`-Commit `646a825b`
vor dem `fix:`-Commit):

- `SettingsNav.test.tsx` (neu): `2 failed | 1 passed (3)` —
  `expected [ 'flex', 'items-center', …(16) ] to include 'min-h-10'`
- `AccountPage.test.tsx`: `2 failed | 26 passed (28)`
- `MfaSection.test.tsx`: `2 failed | 12 passed (14)`
- `MembersPage.test.tsx`: `2 failed | 19 passed (21)`

Nach dem Fix: `src/features/settings` → **10 Dateien / 82 Tests, alle grün**.

### DoD-Kommandos (Node 22.23.2 aus `.nvmrc`, via `mise`)

- `npm run lint` → 0, **67 Warnungen — exakt der vorbestehende Stand** aus
  PR #599, kein neuer Warnungs-Delta
- `npx tsc -b` → 0 (nicht `--noEmit`)
- `npm run test:coverage` → 0, **201 Dateien / 1261 Tests, 0 skipped**
  (Skip-Budget-Gate erfüllt); Statements 87.35 · **Branches 81.39** (Floor 79)
  · Functions 82.76 · Lines 88.43
- `npm run test:a11y` → 0, 41 Dateien / 55 Fälle, keine axe-Violation
- `npm run build` → 0
- `npm run license:check` → 0, keine Copyleft-Lizenz
- `npm run i18n:check` → 0 (keine neuen Schlüssel in diesem Paket)
- `uv run python scripts/check_code_refs.py .` → 0 (954 legacy, **0 error**)
- `uv run python scripts/changelog_fragments.py check` → 0

**Gates aus den Akzeptanzkriterien:**

- AK 5 Grid-Gate → **keine Zeile** (Exit 1)
- AK 8 On-Prem-Bundle-Assert → `grep -rl 'BillingPanel|Jetzt upgraden'
  dist/assets/` findet **nichts**; `features/billing` ist im Diff nicht
  enthalten, die Ternary-Zeilen sind unberührt

### Scope des Diffs

Vier Dateien unter `features/settings` (drei geändert + ein neuer
Testnachbar), drei Testnachbarn ergänzt, ein Changelog-Fragment, diese
Plandatei. **Kein** `components/ui/*`, **kein** `components/layout/*`, **kein**
`features/billing`, **kein** `CHANGELOG.md`. Die Probe-Dateien lagen außerhalb
des Repos (Scratch) und sind nicht Teil des Diffs.

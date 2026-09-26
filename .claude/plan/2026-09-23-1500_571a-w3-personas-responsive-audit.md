# 571 (Hälfte A) — W3 Personas: Responsive-Audit der fünf großen Dateien

Stand: 2026-09-23 · Branch `who2be/t_0f401463-571-w3-personas-haelfte-a-responsive-aud`
Basis: `origin/main` @ `c558860d` · Issue: #571 · Epic: #431 (W3)

## Auftrag

Fünf der dreizehn produktiven `.tsx` unter `apps/web/src/features/personas/`
gegen die sechspunktige Review-Checkliste aus `docs/frontend/design-language.md`
§4.4 bei 320 / 375 / 768 / 1024 px prüfen; gefundene Defekte beheben, nicht
gefundene begründet als „kein Defekt" abhaken. Die übrigen acht Dateien der
Domäne gehören zur Schwesterkarte (Hälfte B) und werden **nicht** angefasst.

Die fünf Dateien dieses Pakets:

| Datei | Zeilen |
|---|---|
| `components/PersonaPlaybooksCard.tsx` | 391 |
| `components/PersonaModesEditor.tsx` | 378 |
| `pages/PersonaDetailPage.tsx` | 335 |
| `components/PersonaProfileFields.tsx` | 250 |
| `components/PersonaProfileEditor.tsx` | 203 |

## Hinweis zur Zahl 40 px (PM-Kommentar an der Karte, 2026-09-23)

Die 40 px in diesem Paket kommen aus **AK 3 dieses Issues**, nicht aus der Norm.
`design-language.md` §11 ist die einzige Quelle des Floors und setzt ihn auf
**≥ 32 px**; 40 px ist dort die Präferenz `size="default"`, `size="sm"` (36 px)
bleibt ausdrücklich zulässig. Die gemessenen 32–36 px der Modus-Aktionen, des
Bearbeiten-Buttons, des Info-Pills und der Sub-Playbook-Zeile sind nach der Norm
also **zulässig** — dieses Paket hebt sie unterhalb `md` an, weil **sein
Akzeptanzkriterium** es verlangt. Keine Stelle in Code, Test, Kommentar oder
Changelog-Fragment schreibt die 40 px der Norm zu.

## Methode — real gemessen, nicht geschätzt

jsdom hat kein Layout, und AK 1–5 sind Layout-Aussagen. Deshalb eine
**Wegwerf-Messharness**: statisches HTML mit den echten Elternketten
(`Container > Stack > DetailHeader | Tabs > TabsList | TabsContent > Card >
CardContent > …`) und den wörtlichen Klassenlisten der fünf Dateien, gefahren in
Chromium (Playwright 1.63) gegen das **gebaute** Stylesheet
`dist/assets/index-*.css` aus dem eigenen `npm run build`, bei allen vier
Viewports.

Fünf Szenarien, weil die Detailseite vier Tabs und die Playbooks-Karte zwei
Modi hat: `detail/edit`, `detail/modes`, `detail/modes-empty`,
`detail/playbooks`, `detail/playbooks-edit`.

Erfassungskriterien je Element:

1. **`child.right > parent.contentRight`** — Überlauf gegen die Eltern-Innenkante,
   nicht nur gegen den Viewport.
2. **`scrollWidth > clientWidth`** — abgeschnittener Text (§4.4 Punkt 5).
   Ausgenommen sind `<input>`/`<select>` (scrollen per Definition intern) und
   `truncate`-Elemente (nach AK 5 das zugelassene kontrollierte Kürzen); für die
   greift weiter Kriterium 1.
3. **Höhe interaktiver Elemente** unterhalb `md` (AK 3).

Zusätzlich `documentElement.scrollWidth` gegen `clientWidth` für AK 1
(Body-Scroll).

Die Fixture bildet zwei Eigenheiten des echten Stacks nach, weil sie das
Ergebnis verändern: das Innen-Padding der BlockNote-Insel aus `globals.css`
(`.bn-container .bn-editor`, unterhalb `md` 12 px statt 54 px) und die
`tailwind-merge`-Auflösung in `cn()` (`whitespace-normal` löscht das
`whitespace-nowrap` der Button-Basis).

Fixtures bewusst pessimistisch und domänentypisch: ein 43-Zeichen-Personaname,
ein 31-Zeichen-Modusname, ein 46-Zeichen-Playbookname, ein Legacy-System-Prompt
mit einem trennstellenfreien 61-Zeichen-Bezeichner.

Harness und Skripte liegen außerhalb des Repos (Scratch) und werden nicht
committet.

## Ist-Zustand bestätigt (auf `c558860d`)

```bash
grep -rnE '(^|[^:a-z-])grid-cols-[2-9]' --include='*.tsx' \
  apps/web/src/features/personas | grep -v '\.test\.tsx'   # (leer)
```

Das einzige Mehrspalten-Grid der Domäne (`apps/web/src/features/personas/components/PersonaModesEditor.tsx@e41bb0fd#PersonaModeCard:328`,
`grid gap-4 sm:grid-cols-2`) ist mobile-first gebunden — Vorentscheidung 4 des
Issues gilt unverändert: **nicht angefasst**. AK 6 ist ohne Eingriff erfüllt.

## Gemessener Body-Überlauf vor der Änderung (AK 1)

| Szenario | 320 px | 375 px | 768 px | 1024 px |
|---|---|---|---|---|
| `detail/edit` | 477 / 320 ✗ | 477 / 375 ✗ | ✓ | ✓ |
| `detail/modes` | 477 / 320 ✗ | 477 / 375 ✗ | ✓ | ✓ |
| `detail/modes-empty` | 477 / 320 ✗ | 477 / 375 ✗ | ✓ | ✓ |
| `detail/playbooks` | 477 / 320 ✗ | 477 / 375 ✗ | ✓ | ✓ |
| `detail/playbooks-edit` | 477 / 320 ✗ | 477 / 375 ✗ | ✓ | ✓ |

Der Body-Scroll aller fünf Szenarien hat **eine** Ursache: die Tab-Leiste der
Detailseite. Ihre vier Trigger messen zusammen 461 px; „Versionen" lief bei
320 px 173 px und bei 375 px 118 px über die Leiste hinaus.

## Befund je Datei — alle fünf abgehakt

| Datei | §4.4-Punkt | Befund |
|---|---|---|
| `pages/PersonaDetailPage.tsx` | 1, 5 | **Defekt, eine Stelle.** `:219` `TabsList` ohne `flex-wrap`: vier Trigger à 108–121 px messen zusammen 461 px in 288 px (320 px) bzw. 343 px (375 px) verfügbarer Breite. „Playbooks" lief 51 px, „Versionen" 173 px über — der einzige Erzeuger horizontalen **Body**-Scrolls in der Domäne. Sonst kein Befund: die Tag-`MetaPill`s `:126` liegen in der `flex-wrap`-Badge-Reihe des `DetailHeader` und laufen nicht über, die Kopf-Aktionen (`GiveFeedbackDialog`, Duplizieren, Export) messen 40 px und brechen im `flex-wrap`-Action-Slot um, `TabsTrigger` misst 44 px. Der Befund des Issues („kein Klassen-Befund") stimmt für die Datei; die Tab-Leiste ist ein Layout- und kein Klassen-Befund und fällt erst bei der Messung auf. |
| `components/PersonaModesEditor.tsx` | 4, 5 | **Defekt, drei Stellen.** (a) `:274` Kopfzeile + `:275` Titelgruppe ohne `flex-wrap`: bei 320 px messen Nummernchip, Modusname und Default-Badge zusammen 160 px in 39 px verfügbarer Breite — das Badge lief 121 px über, der Name war auf 42 px gestaucht. Exakt der vom Issue vermutete Fall. (b) Die beiden `size="sm"`-Aktionen `:292`/`:303` messen **36 px** — die Rechnung des Issues stimmt auf den Pixel. (c) Dieselben 36 px an den beiden „Modus hinzufügen"-Buttons `:196`/`:227`, die das Issue nicht nennt; AK 2 verlangt aber ausdrücklich, dass „Modus anlegen" auf 320 px bedienbar ist. **Erfüllt und nicht angefasst:** `:328` `sm:grid-cols-2` (Vorentscheidung 4), das Trigger-Feld und das Playbook-`Select` (beide volle Breite, 40 px), die drei BlockNote-Inseln. |
| `components/PersonaPlaybooksCard.tsx` | 4, 5 | **Defekt, drei Stellen.** (a) `:265` `CardHeader` + `:266` `CardTitle` ohne `flex-wrap`: der Kopf misst 365 px in 286 px, der Bearbeiten-Button lief 104 px über. Der vom Issue vermutete Fall, bestätigt. (b) Derselbe Button misst **36 px** hoch. (c) `:101` Sub-Playbook-Name: die Zeile misst 329 px Textbreite, dem Namen blieben bei 320 px **81 px** — `truncate` schnitt nach rund acht Zeichen ab (AK 5), und die Zeile `:96` misst 36 px, obwohl sie klickbar ist. Das Issue hält `min-w-0 flex-1 truncate` für erfüllt; das gilt für den *Überlauf*, nicht für die *Lesbarkeit*. **Erfüllt und nicht angefasst:** der Bearbeiten-Modus (Suchfeld 40 px volle Breite, Speichern-Leiste `flex justify-end gap-2` mit zwei 40-px-Buttons, die Verfügbar-Liste scrollt in ihrem eigenen `max-h-72 overflow-auto`-Wrapper — nach §4.4 Punkt 1 zulässig), die `EntityCard`-Zeilen des Anzeige-Modus. |
| `components/PersonaProfileFields.tsx` | 4, 5 | **Defekt, zwei Stellen.** (a) Der Modi-Info-Pill `:54` misst bei 320 px **355 px** in 238 px verfügbarer Breite (+118 px Überlauf) und ist durch `h-auto` nur **32 px** hoch. Ein Modusname ist frei wählbar und hat keine Längengrenze. (b) Der Legacy-System-Prompt-`<pre>` `:170` zeigt 462 px Inhalt in 212 px: `whitespace-pre-wrap` bricht nur an Leerzeichen, ein trennstellenfreier Bezeichner läuft durch. **Erfüllt und nicht angefasst:** die vier `FormSection`-Gruppen (Identität, Profil, Skills, Tags) mit je voller Feldbreite und 40 px Feldhöhe, `TagInput`, `SkillsComingSoon`. Der Befund des Issues („kein Klassen-Befund") stimmt; beide Defekte sind Laufzeit-Inhalte, keine Klassenmuster. |
| `components/PersonaProfileEditor.tsx` | 5 | **Defekt, eine Stelle.** Der `bn-container` `:130` zeigte bei 320 px 371 px Inhalt in 236 px sichtbarer Breite: ein Persona-Profil trägt fremdbestimmte Bezeichner (Playbook-/Resource-Namen, Tool-Aliasse aus den Pills) ohne Trennstelle. **Erfüllt und nicht angefasst:** das Innen-Padding der Insel ist seit W2 in `globals.css` auf 12 px unterhalb `md` gedeckelt (gemessen bestätigt), die fünf Picker liegen als Dialoge im Primitive mit W2-Inset. Der Befund des Issues („kein Klassen-Befund") stimmt; der Defekt ist reiner Laufzeit-Inhalt. |

## Fix — zehn Stellen, fünf Dateien

Weiche 1 aus #431 gilt: kein Breakpoint-Prefix ohne gemessenen Defekt. Die
`md:`-Prefixe stehen nur dort, wo die Mobile-Lösung den Desktop sonst
verschlechtern würde (Hit-Target-Anhebungen); die Umbruch- und
Umbruch-Text-Fixes kommen ohne Prefix aus.

1. **`apps/web/src/features/personas/pages/PersonaDetailPage.tsx@82f890fb#PersonaDetailPage:219`** — `flex-wrap` an der `TabsList`.
   §4.4 Checklistenpunkt 5 nennt Umbruch als Mittel der Wahl.
2. **`apps/web/src/features/personas/components/PersonaModesEditor.tsx@e41bb0fd#PersonaModeCard:274`/`:275`** — `flex-wrap` an Kopfzeile und
   Titelgruppe. **Wörtlich Vorentscheidung 1** des Issues: umbrechen, kein
   Overflow-Menü.
3. **`apps/web/src/features/personas/components/PersonaModesEditor.tsx@e41bb0fd#PersonaModeCard:292`/`:303`** — `min-h-10 md:min-h-0` an den
   beiden Modus-Aktionen (Vorentscheidung 2).
4. **`apps/web/src/features/personas/components/PersonaModesEditor.tsx@e41bb0fd#PersonaModesEditor:196`/`:227`** — dieselbe Klassenfolge an den
   beiden „Modus hinzufügen"-Buttons (aus AK 2 abgeleitet).
5. **`apps/web/src/features/personas/components/PersonaPlaybooksCard.tsx@ebc04aaf#PersonaPlaybooksCard:265`/`:266`** — `flex-wrap` am `CardHeader`,
   `min-w-0 flex-wrap` am `CardTitle`.
6. **`apps/web/src/features/personas/components/PersonaPlaybooksCard.tsx@ebc04aaf#PersonaPlaybooksCard:273`** — `min-h-10 md:min-h-0` am
   Bearbeiten-Button.
7. **`apps/web/src/features/personas/components/PersonaPlaybooksCard.tsx@ebc04aaf#SubPlaybookList:96`/`:101`** — `min-h-10 flex-wrap md:min-h-0`
   an der Sub-Playbook-Zeile, `min-w-40` statt `min-w-0` am Namen. Der
   Status-Badge bricht dadurch in die zweite Zeile, der Name behält 178 px.
   `truncate` bleibt — das kontrollierte Kürzen ist nach AK 5 zulässig, nur
   nicht bei acht sichtbaren Zeichen.
8. **`apps/web/src/features/personas/components/PersonaProfileFields.tsx@dc897c81#PersonaModesInfoPill:54`** — `min-h-10 max-w-full flex-wrap
   break-words whitespace-normal text-left md:min-h-0` am Info-Pill.
9. **`apps/web/src/features/personas/components/PersonaProfileFields.tsx@dc897c81#PersonaProfileFields:170`** — `break-words` am Legacy-`<pre>`
   (additiv zu `whitespace-pre-wrap`, Muster aus #572).
10. **`apps/web/src/features/personas/components/PersonaProfileEditor.tsx@200f5a7a#PersonaProfileEditor:130`** — `break-words` am `bn-container`.
    Die Klasse vererbt an alle Nachkommen und deckt damit auch Inhalte ab, die
    erst zur Laufzeit entstehen — dasselbe Argument, mit dem §11 `break-words`
    am `<main>` der Auth-Pages verbindlich macht.

## Bewusst nicht geändert

- **`apps/web/src/features/personas/components/PersonaModesEditor.tsx@e41bb0fd#PersonaModeCard:328` (`sm:grid-cols-2`)** — Vorentscheidung 4:
  erfüllt die §4.4-Regel bereits, ein zusätzlicher `md:`-Schritt wäre eine
  Designentscheidung ohne Defekt.
- **Der Zurück-Link im `DetailHeader`** misst 36 px (`size="sm"`). Er liegt im
  geteilten Primitive `apps/web/src/components/data/DetailHeader.tsx@3c440e80#DetailHeader:47` und wirkt auf alle
  dreizehn Domänen — **gemeldet statt repariert** (Vorgabe der Karte: keine
  Primitives unter `components/ui/` oder `components/data/` ändern). Nach der
  Norm (§11, Floor ≥ 32 px) ist er ohnehin zulässig; nur das Akzeptanzkriterium
  dieses Pakets würde ihn anheben, und das erstreckt sich nicht auf geteilte
  Primitives.
- **Der Expander-Button der `EntityCard`** („N Sub-Playbooks") misst 32 px
  (`h-auto … py-2` in `apps/web/src/components/data/EntityCard.tsx@3c440e80#EntityCard:189`). Gleicher Fall:
  geteiltes Primitive, gemeldet statt repariert, nach der Norm zulässig.
- **Die acht übrigen Dateien der Domäne** — Schwesterkarte (Hälfte B).

## Verifikation

Nachmessung mit derselben Harness gegen das neu gebaute Stylesheet:

| Szenario | 320 px | 375 px | 768 px | 1024 px |
|---|---|---|---|---|
| `detail/edit` | 320 / 320 ✓, 0 Überläufer | 375 / 375 ✓, 0 | ✓ | ✓ |
| `detail/modes` | 320 / 320 ✓, 0 | 375 / 375 ✓, 0 | ✓ | ✓ |
| `detail/modes-empty` | 320 / 320 ✓, 0 | 375 / 375 ✓, 0 | ✓ | ✓ |
| `detail/playbooks` | 320 / 320 ✓, 0 | 375 / 375 ✓, 0 | ✓ | ✓ |
| `detail/playbooks-edit` | 320 / 320 ✓, 0 | 375 / 375 ✓, 0 | ✓ | ✓ |

Die verbleibenden Hit-Targets unter 40 px bei 320 px sind ausschließlich die
zwei oben gemeldeten Primitive-Funde.

Einzelmessungen der Anhebungen (320 px, vorher → nachher):

| Element | vorher | nachher |
|---|---|---|
| Modus-Aktion „Als Default setzen" | 36 px | 40 px |
| Modus-Aktion „Entfernen" | 36 px | 40 px |
| „Modus hinzufügen" / „Ersten Modus anlegen" | 36 px | 40 px |
| Playbooks-Karte „Verknüpfungen bearbeiten" | 36 px | 40 px |
| Sub-Playbook-Zeile | 36 px | 40 px |
| Modi-Info-Pill | 32 px | 40 px |
| Sub-Playbook-Name (sichtbare Breite) | 81 px | 178 px |

Test-first (CLAUDE.md §Workflow): die neun neuen Assertions liefen gegen den
ungepatchten Stand — die Fixes waren dafür gestasht — **rot** (8 Fehlschläge
plus ein Suite-Fehler, weil `PersonaProfileEditor.test.tsx` ohne die Änderung
keinen Gegenstand hat), danach grün.

Definition of Done (`apps/web/`, Node 22):

```
npm run lint        exit 0
npx tsc -b          exit 0
npm run test:coverage  exit 0 — 206 Dateien, 1308 Tests, Branches 81.48 %
                       (Floor 79), Statements 87.3 %, Lines 88.4 %
npm run build       exit 0
```

Grid-Gate aus AK 6 gibt keine Zeile aus.

## Offene Punkte für die Schwesterkarte / das Tracking-Issue

- **Zwei Primitive-Funde** (`DetailHeader` Zurück-Link 36 px,
  `EntityCard`-Expander 32 px). Beide nach der Norm zulässig; sie treffen jedes
  W3-Paket, das die Primitives benutzt, und wären ein eigenes Paket.
- Die acht Dateien der Hälfte B sind hier **nicht** geprüft.

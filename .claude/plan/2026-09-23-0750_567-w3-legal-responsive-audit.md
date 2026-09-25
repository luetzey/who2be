# 567 — W3 Legal: Responsive-Audit von `features/legal` (8 Dateien)

Stand: 2026-09-23 · Branch `who2be/t_662775f3-567-w3-legal-responsive-audit-von-featur`
Basis: `origin/main` @ `9a05a4e8` · Issue: #567 (agent-ready) · Epic: #431 (W3)

## Auftrag

Die acht produktiven `.tsx` unter `apps/web/src/features/legal/` bei
320 / 375 / 768 / 1024 px gegen die sechspunktige Review-Checkliste aus
`docs/frontend/design-language.md#4.4` prüfen. Gefundene Defekte beheben, nicht
gefundene begründet als „kein Defekt" abhaken. Keine Änderung an geteilten
Primitives (`components/ui/*`, `components/layout/*`).

## Methode — real gemessen, nicht geschätzt

jsdom hat kein Layout. Gemessen wurde deshalb am **gerenderten Baum** gegen den
echten Vite-Dev-Server (Node 22.23.2, `.nvmrc`-Stand) per Chrome DevTools
Protocol: `Emulation.setDeviceMetricsOverride` auf 320 / 375 / 768 / 1024 px,
dann je Route

- `document.body.scrollWidth` gegen `clientWidth` (horizontaler Body-Scroll),
- jedes Element mit `getBoundingClientRect().right > clientWidth` (Überläufer),
- jedes Blatt mit `scrollWidth > clientWidth` (innerer Überlauf),
- jede Text-Node über `Range.getClientRects()` gegen die Artikel-Innenkante
  (der Fall „Wort läuft aus der Lesespalte", den Element-Rechtecke verdecken,
  weil der Block selbst 288 px breit bleibt),
- Höhe jedes `a`/`button`/`[role=button]` (Hit-Target-Floor aus
  `design-language.md#11`).

Beide Sprachen geprüft (`who2be.locale` = `de` und `en`) — die deutschen Titel
sind die längeren und der einzige Auslöser.

Die Vertragstests dazu sind **Klassen-Verträge** (jsdom), die Layout-Aussage
selbst steht hier mit Zahlen.

## Ist-Zustand nachgemessen (auf `9a05a4e8`)

```bash
find apps/web/src/features/legal -name '*.tsx' \
  ! -name '*.test.tsx' ! -name '*test-utils*' ! -path '*/test/*' | wc -l   # 8
find … -exec grep -lE '\b(sm|md|lg|xl|2xl):' {} \;
# CookieConsentBanner.tsx, LegalLayout.tsx, TermsPage.tsx
grep -rnE '(^|[^:a-z-])grid-cols-[2-9]' --include='*.tsx' \
  apps/web/src/features/legal | grep -v '\.test\.tsx'                      # (leer)
```

Bestätigt: 8 Dateien, 3 mit Prefix, kein Grid. §4.4-Punkt 2 (Grids) ist in der
Domäne gegenstandslos, Punkt 3 (feste Breiten) trägt nur `max-w-3xl`/`max-w-2xl`
— Caps nach oben, kein Mindestmaß, mobil ohne Wirkung.

### Gemessener Überlauf je Route (Body-`scrollWidth` gegen `clientWidth`)

| Route | 320 | 375 | 768 | 1024 |
|---|---|---|---|---|
| `/legal/impressum` | 320 ✓ | 375 ✓ | 753 ✓ | 1009 ✓ |
| `/legal/agb` | **353** | 375 ✓ | 753 ✓ | 1009 ✓ |
| `/legal/datenschutz` | **335** | 375 ✓ | 753 ✓ | 1009 ✓ |
| `/legal/dpa` | 320 ✓ | 375 ✓ | 753 ✓ | 1009 ✓ |

Der Body-Scroll auf zwei von vier Routen hat **eine einzige Ursache**: die `h1`
in `LegalArticle` (`text-3xl`, 30 px) rendert das längste deutsche Wort des
Titels breiter als die 288-px-Lesespalte. Text-Node-Messung bei 320 px:

| Route | Titel | Textbreite | Spalte | Überlauf |
|---|---|---|---|---|
| `/legal/agb` | „Allgemeine Geschaeftsbedingungen (AGB)" | 337 px | 288 px | **49 px** |
| `/legal/datenschutz` | „Datenschutzerklaerung" | 319 px | 288 px | **31 px** |
| `/legal/dpa` | „Vertrag zur Auftragsverarbeitung (DPA)" | 293 px | 288 px | **5 px** (innerer Überlauf, Body noch 320) |
| `/legal/impressum` | „Impressum" | 288 px | 288 px | – |

Auf `/legal/dpa` bleibt der Body bei 320, weil der Überlauf 5 px beträgt und
vom Padding geschluckt wird — derselbe Defekt, nur kleiner. Englisch löst ihn
auf keiner Route aus (längster Titel „General Terms and Conditions (GTC)",
288 px) — die deutschen Komposita sind der Fall, genau wie im Issue vermutet.

Gegenprobe am selben Element: `text-2xl` (24 px) → `scrollWidth` 288 = `clientWidth`
auf allen vier Routen. `overflow-wrap: anywhere` am `<article>` löst es
ebenfalls, auch bei `text-3xl`.

## Befund je Datei — alle 8 abgehakt (AK 7)

| Datei | §4.4-Punkt | Befund |
|---|---|---|
| `apps/web/src/features/legal/components/LegalArticle.tsx#LegalArticle` | 1, 5 | **Defekt.** Die `h1` (`text-3xl`) läuft mit dem längsten deutschen Titel 49 px aus der Lesespalte und erzeugt auf zwei von vier Routen horizontalen Body-Scroll (Zahlen oben). Einziger Überläufer der ganzen Domäne. |
| `apps/web/src/features/legal/components/CookieConsentBanner.tsx#CookieConsentBanner` | 4 | **Defekt.** Die beiden `size="sm"`-Buttons messen gerendert **36 × 124 px**. §11 ist mit 36 px eingehalten (Floor 32 px), **AK 3 dieses Issues verlangt aber ≥ 40 px unterhalb `md`** — gemessen unterschritten. Zusätzlich gemessen: die Button-Reihe misst 256 px bei 254 px Innenraum (2 px innerer Überlauf, `flex shrink-0`). |
| `apps/web/src/features/legal/components/LegalLayout.tsx#LegalLayout` | 5 | **Kein Defekt gemessen** (Kopfzeile passt auf 320 px, „Who2Be" 54 px + „RECHTLICHES" rechtsbündig). Weiche 5 des Issues ist trotzdem umzusetzen: `flex-wrap` als Vorsorge gegen längere Marken-/Labeltexte, nach dem Repo-Muster `apps/web/src/components/layout/PageHeader.tsx#PageHeader`. Kein Breakpoint-Prefix, kein Render-Zweig. |
| `apps/web/src/features/legal/pages/TermsPage.tsx#TermsPage` | 1–6 | **Kein Defekt.** Die vier Definitionspaare sind mobile-first (`flex flex-col gap-1 sm:flex-row sm:gap-2`) und stapeln gemessen auf dem Phone. Der Body-Scroll der Route stammt vollständig aus der `h1` in `LegalArticle` (Text-Node-Messung oben), nicht aus dieser Datei. |
| `apps/web/src/features/legal/pages/DpaPage.tsx#DpaPage` | 1–6 | **Kein Defekt.** Reiner Inhalt über `LegalArticle`/`LegalSection`; gemessen 0 Element-Überläufer. Der 5-px-Rest der `h1` gehört zu `LegalArticle`. |
| `apps/web/src/features/legal/pages/ImpressumPage.tsx#ImpressumPage` | 1–6 | **Kein Defekt.** Gemessen 0 Überläufer auf allen vier Viewports, Body 320/375/753/1009. Anschrift, Register- und Kontaktangaben brechen als Platzhalter-Chips im Fließtext. |
| `apps/web/src/features/legal/pages/PrivacyPage.tsx#PrivacyPage` | 1–6 | **Kein Defekt.** Gemessen 0 Element-Überläufer; der neue Captcha-Abschnitt (`privacy.sections.captcha`, seit `239198a`) rendert seinen langen Text über `Placeholder` und bricht an Wortgrenzen. Der Rest-Body-Scroll ist die `h1`. |
| `apps/web/src/features/legal/components/Placeholder.tsx#Placeholder` | 5 | **Kein Defekt gemessen** — kein Chip überläuft, weder im Banner noch im Captcha-Abschnitt (die Inhalte tragen Leerzeichen und Bindestriche). Der Chip ist ein `inline`-`<mark>`; ein trennstellenfreier Chip-Inhalt bräuchte eine Umbruchregel, die er nicht selbst trägt — sie kommt mit Weiche 2 vom gemeinsamen Träger `LegalArticle` (`break-words` vererbt auf den ganzen Prose-Teilbaum) und deckt den Chip mit ab. Datei selbst unverändert. |

Weiche 1 des Issues bestätigt sich in der Messung: den fünf prefixlosen Dateien
fehlt nichts. Von den fünf hat **keine** einen eigenen Defekt; der einzige Fund
im prefixlosen Teil sitzt im gemeinsamen Träger `LegalArticle` und wird dort
einmal behoben, nicht fünfmal nachgerüstet.

## Fix

1. **`apps/web/src/features/legal/components/LegalArticle.tsx#LegalArticle` — `h1` auf `text-2xl sm:text-3xl`**
   (Weiche 3: Abstufung *nur bei gemessenem Überlauf*; er ist gemessen, 49 px).
   Mobile-first: die präfixlose Klasse ist der Phone-Fall, `sm:` stellt den
   bisherigen Desktop-Zustand wieder her. Kein Pixel Änderung ab 640 px.
2. **`apps/web/src/features/legal/components/LegalArticle.tsx#LegalArticle` — `break-words` am `<article>`**
   (Weiche 2: am gemeinsamen Prose-Träger, nicht je Seite). Deckt lange URLs,
   E-Mail-Adressen und Registerangaben in allen vier Rechtstexten **und** die
   `Placeholder`-Chips in einem Zug ab, sobald die Platzhalter durch echten
   Text ersetzt werden. `break-all` ist laut Weiche 2 verworfen — es zerlegt
   auch normale Wörter.
   Beides zusammen, nicht eines statt des anderen: `text-2xl` ist die typo-
   grafische Antwort auf den gemessenen Titel-Fall, `break-words` die
   Schutzschicht für künftigen Fließtext, der heute noch Platzhalter ist.
3. **`apps/web/src/features/legal/components/CookieConsentBanner.tsx#CookieConsentBanner` — `h-10 md:h-9` an beiden
   Buttons** (Weiche 4). 40 px unterhalb `md`, ab `md` zurück auf die kompakte
   `size="sm"`-Höhe. `size="sm"` bleibt für Padding/Radius stehen; die Höhe
   überschreibt `tailwind-merge` konfliktfrei.
4. **`apps/web/src/features/legal/components/CookieConsentBanner.tsx#CookieConsentBanner` — Buttons `flex-1
   sm:flex-none`**, Reihe `shrink-0` → `sm:shrink-0`. Behebt den gemessenen
   2-px-Überlauf der Button-Reihe auf 320 px: unterhalb `sm` teilen sich die
   zwei Buttons die volle Kartenbreite, ab `sm` (dort steht der Banner
   ohnehin nebeneinander) gilt die bisherige kompakte Fassung.
5. **`apps/web/src/features/legal/components/LegalLayout.tsx#LegalLayout` — `flex-wrap` + `gap-x-4 gap-y-1` an der
   Kopfzeile** (Weiche 5, Muster `apps/web/src/components/layout/PageHeader.tsx#PageHeader`). Kein gemessener
   Defekt, aber vorentschieden und ohne Nebenwirkung.

Nicht angefasst: `components/ui/button.tsx`, `components/layout/Container.tsx`
und jeder andere geteilte Primitive. Der Banner-Fix sitzt am Aufrufer, nicht
an der `size`-Skala.

## Ergebnis — nach dem Fix nachgemessen

Identische Messharness, identische Viewports, beide Sprachen.

### Body-Scroll (AK 1)

| Route | 320 | 375 | 768 | 1024 |
|---|---|---|---|---|
| `/legal/impressum` | 320 ✓ | 375 ✓ | 753 ✓ | 1009 ✓ |
| `/legal/agb` | **320 ✓** (vorher 353) | 375 ✓ | 753 ✓ | 1009 ✓ |
| `/legal/datenschutz` | **320 ✓** (vorher 335) | 375 ✓ | 753 ✓ | 1009 ✓ |
| `/legal/dpa` | 320 ✓ | 375 ✓ | 753 ✓ | 1009 ✓ |

**0 Element-Überläufer und 0 Text-Überläufer** auf allen vier Routen × vier
Viewports (vorher: 5 bzw. 2 Elemente auf `/legal/agb` und `/legal/datenschutz`,
3 Text-Überläufer). Die `h1` misst auf allen vier Routen bei 320 px
`scrollWidth` 288 = `clientWidth`; ab `sm` unverändert 30 px (768/1024
gemessen, `clientWidth` 705 bzw. 720, `scrollWidth` identisch).

### Lesbarkeit langer Bezeichner (AK 2)

Härtetest mit einer 115-Zeichen-URL ohne Trennstellen, in den Fließtext der
Impressum-Seite injiziert, bei 320 px:

| | `scrollWidth` | Body |
|---|---|---|
| mit `break-words` (neuer Stand) | **288** = Spaltenbreite, 0 px Überlauf | 320 ✓ |
| Gegenprobe `overflow-wrap: normal` | 414 | **430** |

Damit ist AK 2 nicht nur für die heutigen Platzhalter belegt, sondern für den
echten Rechtstext, der sie ersetzt.

### Hit-Targets des Cookie-Banners (AK 3)

| Viewport | „Nur notwendige" | „Alle akzeptieren" |
|---|---|---|
| 320 px | **40 × 124 px** (vorher 36) | **40 × 124 px** (vorher 36) |
| 768 / 1024 px | 36 × 124 px | 36 × 124 px |

Die 36 px ab `md` sind die bewusste `size="sm"`-Dichte und liegen über dem
§11-Floor von 32 px.

### Banner im Viewport (AK 5)

320 px: Karte `left 16 → right 304` bei `clientWidth` 320 — **vollständig im
Viewport**, vorher `right 337` (17 px außerhalb) auf `/legal/agb`. 768/1024 px:
`left 41 → right 713` bzw. `left 169 → right 841`. Der Banner ist `fixed
bottom-0` und nicht-modal (`pointer-events-none` am Wrapper), überdeckt also
keinen Bedienpfad dauerhaft.

### Kopfzeile (AK 4)

`LegalLayout` passt auf 320 px vollständig (0 Überläufer, gemessen vor und
nach der Änderung); mit `flex-wrap` bricht sie um, sobald Marke plus Label
breiter werden.

### Grid-Gate (AK 6)

```bash
grep -rnE '(^|[^:a-z-])grid-cols-[2-9]' --include='*.tsx' \
  apps/web/src/features/legal | grep -v '\.test\.tsx'   # keine Zeile, exit 1
```

### Test-first (AK 8)

Vor dem Fix: `5 failed | 12 passed (17)` — die fünf Fehlschläge sind exakt die
fünf neuen Assertions (`2d4a6631`, reiner Test-Commit). Nach dem Fix:
`7 Dateien | 17 Tests | 0 skipped`, alle grün.

### DoD (`CONTRIBUTING.md`) unter Node 22.23.2

Siehe Commit-Nachtrag / Handoff.


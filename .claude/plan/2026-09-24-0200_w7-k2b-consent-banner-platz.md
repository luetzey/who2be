# W7 / K2b — Cookie-Consent-Banner blockiert auf schmalen Viewports die Formular-Aktionen

Karte: t_9825e6cb (Befund B7, Anwendungsseite) · Stapel auf K2 (`f13d41b4`).

## Ausgangslage (gelesen, nicht vermutet)

`apps/web/src/features/legal/components/CookieConsentBanner.tsx`

- Z. 25 Wrapper `pointer-events-none fixed inset-x-0 bottom-0 z-50 flex justify-center p-4`
- Z. 29 `Card` mit `pointer-events-auto` — faengt Klicks tatsaechlich ab.
- Z. 29 `flex-col … sm:flex-row` — unterhalb `sm` stapelt die Karte und wird hoch.
- Eingehaengt global in `apps/web/src/app/routes.tsx:422`.
- Kein Abstandsausgleich: nichts reserviert unten Platz.

Der zweite Teil ist der eigentliche Grund, warum „Platz reservieren" allein nicht
reicht: Playwright scrollt ein Ziel per `scrollIntoViewIfNeeded` **minimal** in
den Viewport — also an den unteren Rand, und damit direkt unter das `fixed`
Banner. Ein blosses `padding-bottom` am Inhalt verschiebt nur, wo der Inhalt
endet, nicht wohin der Browser scrollt.

## Entscheidung

Kombination aus zwei Mitteln, beide CSS, kein Eingriff in `useCookieConsent.ts`:

1. **Gemessene Bannerhoehe als CSS-Variable.** Das Banner misst sich selbst per
   `ResizeObserver` und schreibt `--cookie-banner-height` auf
   `document.documentElement`; sobald entschieden (oder unmounted) faellt der
   Wert auf `0px`. Kein Hardcoding einer Hoehe, die mit Textlaenge/Sprache/
   Schriftgroesse driftet.
2. **Zwei Verbraucher der Variablen in `globals.css`:**
   - `body { padding-bottom: var(--cookie-banner-height, 0px) }` — reserviert
     echten Platz, der Seiteninhalt endet nicht mehr unter dem Banner.
   - `html { scroll-padding-bottom: var(--cookie-banner-height, 0px) }` — sagt
     dem Scrollport, dass die unteren N Pixel **nicht** zur sichtbaren Region
     zaehlen. Genau das ist die Aufgabe von `scroll-padding`
     (CSS Scroll Snap Module Level 1, §5: definiert den „optimal viewing
     region" des Scrollports); jedes programmatische Scrollen — auch
     `scrollIntoViewIfNeeded`, das Playwright benutzt — richtet sich danach.

Mittel 1 ohne 2 loest das Klickproblem nicht (siehe oben), 2 ohne 1 haette
keine Zahl. Deshalb beides.

Bewusst **nicht** gewaehlt: das Banner unterhalb `sm` als schlanke Leiste. Das
verkleinert die Trefferflaeche des Overlays, beseitigt sie aber nicht — ein
Formularbutton kann weiterhin zufaellig darunter liegen. Es waere ausserdem eine
Design-Aenderung an einem Compliance-Artefakt (#567 hat die Buttonhoehen dort
gerade erst gegen §11 gemessen) ohne Gegenwert.

## Arbeitsschritte

1. Rot-Probe: neuer E2E-Spec `apps/web/e2e/consent-overlay.spec.ts` — **ohne**
   `decideCookieConsent`, also bei ungetroffener Entscheidung, auf `/login` den
   Submit-Button klicken. Muss vor dem Fix rot sein (Log in den Kartenkommentar).
2. Fix in `CookieConsentBanner.tsx` + `globals.css`.
3. Gruen-Messung desselben Specs auf `mobile-320`, `mobile-iphone-13`,
   `tablet-ipad-gen-7`, `chromium`.
4. `CookieConsentBanner.test.tsx` um den Vertrag der Hoehenmessung erweitern.
5. Changelog-Fragment, DoD-Kommandos, PR.

## Dateibudget

1. `apps/web/src/features/legal/components/CookieConsentBanner.tsx`
2. `apps/web/src/features/legal/components/CookieConsentBanner.test.tsx`
3. `apps/web/src/styles/globals.css`
4. `apps/web/e2e/consent-overlay.spec.ts` (neu)
5. `changelog.d/w7k2b-consent-banner-platz.fixed.md` (neu)
6. diese Plandatei

Sechs von acht — eingehalten.

## Messungen (durchgefuehrt, nicht behauptet)

Lokal gegen den Vite-Dev-Server, Node 22.23.2, Playwright-Profile aus
`playwright.config.ts`.

### Rot-Probe (vor dem Fix)

`consent-overlay.spec.ts`, alle vier Profile: **6 passed, 2 failed, 0 skipped**.
Beide Fehlschlaege auf `mobile-320`, woertlich der CI-Befund:

```
<p class="text-sm text-muted-foreground">…</p> from
<div class="pointer-events-none fixed inset-x-0 bottom-0 z-50 flex justify-center p-4">…</div>
subtree intercepts pointer events
```

und `Error: Submit-Unterkante 390px, Banner-Oberkante 322px` (Luecke -68px).

Die Routenwahl ist gemessen, nicht geraten. Bei ungetroffener Entscheidung auf
`mobile-320` (Viewport 320x568):

| Route             | scrollHeight | Klick ohne Fix |
| ----------------- | -----------: | -------------- |
| `/login`          |        662px | gelingt (Scrollweg vorhanden) |
| `/signup`         |        829px | Button ist bis Captcha `disabled` — untauglich |
| `/reset-password` |        568px | **Timeout** (kein Scrollweg) |

Deshalb `/reset-password`: dort deckt der Inhalt den Viewport genau ab, der
Button liegt fest unter dem Banner. Auf `/login` waere der Test still gruen
gewesen.

### Gruen (nach dem Fix)

`consent-overlay.spec.ts`: **8 passed, 0 failed, 0 skipped** ueber alle vier
Profile. Gemeinsam mit `scroll-guard.spec.ts` + `public.spec.ts`:
**36 passed, 0 skipped** — K2s Scroll-Guard bleibt gruen, das neue
`padding-bottom` erzeugt keinen horizontalen Ueberlauf.

Gemessene Reservierung je Profil (`--cookie-banner-height` = `body`-Padding =
`scroll-padding-bottom`), plus Luecke zwischen Submit-Unterkante und
Banner-Oberkante nach `scrollIntoViewIfNeeded`:

| Profil              | reserviert | Luecke |
| ------------------- | ---------: | -----: |
| `chromium`          |      150px |  130px |
| `mobile-iphone-13`  |      226px |   28px |
| `tablet-ipad-gen-7` |      150px |  310px |
| `mobile-320`        |      266px |  147px |

Die Spanne 150–266px belegt, warum eine feste Hoehe falsch gewesen waere.
Nach `reject` faellt die Variable in allen vier Profilen auf leer, `body`-
Padding auf `0px` — kein toter Rand nach der Entscheidung.

### Mutationsproben

Jede Mutation einzeln angebracht, gemessen, zurueckgenommen:

1. `+ 32` (Wrapper-`p-4`) aus der Rechnung entfernt → Unit-Test
   „meldet die gemessene Hoehe samt Wrapper-Abstand" rot
   (`expected '190px' to be '222px'`). E2E blieb gruen — erwartbar, 32px
   Reserve sind nicht die Grenze zwischen klickbar und nicht.
2. `html { scroll-padding-bottom }` auf `0px` genagelt → `mobile-320`
   „Das Banner ueberdeckt die primaere Aktion nicht" rot (-70px).
3. `body { padding-bottom }` auf `0px` genagelt → beide `mobile-320`-Tests rot,
   Klick wieder im Timeout.

Damit ist jeder der drei Bestandteile einzeln bewacht.

**Ein Befund aus der Probe wurde in den Code zurueckgetragen:** die erste
Fassung nahm die Reservierung an zwei Stellen zurueck (im `card === null`-Zweig
und im Cleanup). Die Mutationsprobe zeigte, dass sich beide gegenseitig
abdecken — keiner war einzeln bewacht, jeder fuer sich entfernbar, ohne dass
ein Test rot wird. Die Redundanz ist entfernt; das Cleanup ist jetzt der
einzige Ort und wird von Mutation 3 belegt gefangen.

## DoD (lokal, Node 22.23.2)

| Kommando | Ergebnis |
| --- | --- |
| `eslint .` | exit 0 — 0 errors, 73 vorbestehende Warnungen |
| `tsc -b` | exit 0 |
| `vitest run --coverage` | **1371 passed, 0 skipped**, 219 Dateien |
| Coverage | Statements 87.45%, Branches 81.70%, Functions 83.12%, Lines 88.53% |
| `assert_skips_within_budget.py junit-web.xml` | exit 0 — 0 uebersprungen |
| `npm run build` | exit 0 |
| `check-i18n.ts` | exit 0 — keine neuen Waisen |
| `npm run license:check` | exit 0 |
| `changelog_fragments.py check` | exit 0 — 28 Fragmente in Ordnung |
| `check_code_refs.py .` | **0 error** (1004 legacy vorbestehend) |

Python-Stack nicht ausgefuehrt und warum: der PR fasst ausschliesslich
`apps/web/` und `changelog.d/` an, keine Python-Datei. Im PR laeuft der
`python`-Job regulaer mit.

## Out of Scope

E2E-Helfer (K2), CI-Gate scharfstellen (K3), Consent-Fachlogik/Texte.

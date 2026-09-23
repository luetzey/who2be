# W3 Auth — Responsive-Audit von `features/auth` (Issue #569)

Karte: `t_eae7978a` · Branch: `who2be/t_eae7978a-569-w3-auth-responsive-audit-von-feature`
Basis: `origin/main` @ `b28c2ebd` · Norm: `docs/frontend/design-language.md` §4.4 / §10.2 / §11

## Ziel (Completion-Condition)

Jede Datei der Domäne ist bei 320/375/768/1024 px gegen die sechspunktige
§4.4-Checkliste **gemessen** (nicht gelesen), jeder Anmeldeweg ist auf 320 px
durchführbar, jeder Defekt behoben oder als „kein Defekt" begründet. Fertig ist
erreicht, wenn die sechs DoD-Kommandos Exit 0 liefern, die Nachmessung 0
Überläufer und 0 Body-Scroll zeigt und der PR mit grünem `all-green` offen ist.

## Messmethode (statt Klassenlesen)

Wegwerf-Probe unter `apps/web/probe/` (gitignored, wird nach der Messung
gelöscht): baut die echten Seiten mit dem **Produktions-Tailwind-Scan** und
misst im echten Chromium (Playwright-Binary, CDP-Viewport) pro Fall und
Viewport

* `documentElement.scrollWidth > clientWidth` (Body-Scroll),
* jedes Element gegen die **Innenkante** seines Elternteils (Padding/Border
  abgezogen) — nicht gegen die Randkante,
* `scrollWidth > clientWidth` je Element (fängt kürzende `readOnly`-Inputs und
  ungebrochene Tokens, die die Kantenmessung nicht sieht),
* Hit-Target-Höhen aller `button/a/input/select`.

Gemessene Fälle: `login`, `login-error`, `login-mfa`, `login-unconfirmed`,
`signup`, `reset`, `set-password`, `coming-soon`, `callback-error`,
`invitation`, `consent`, `consent-locked`, `consent-longhost`.

## Ist-Zustand — alle Dateien abgehakt

Die Domäne hat auf `b28c2ebd` **10** produktive `.tsx`, nicht 9: seit #539 ist
`components/TurnstileWidget.tsx` dazugekommen (das Issue zählte am
2026-09-22 auf `87de64c`). Die zehnte Datei wird mitgeprüft, nicht
weggelassen.

| Datei | Messbefund | Konsequenz |
|---|---|---|
| `pages/LoginPage.tsx` | §10.2-Karte 288 px @320. **Fehlerzustand: Body-Scroll 522/320** (langer GoTrue-Token im `ErrorAlert`). `justify-between` passt heute (41–279), trägt aber `flex-wrap: nowrap`. Resend-Button `size="sm"` = **36 px < 40**. MFA-Zweig: Input+Submit je 40 px, 0 Überläufer. Teiler 95 px, intakt. | Fix 1, 2, 3 |
| `pages/SignupPage.tsx` | 0 Überläufer, 0 Body-Scroll, Submit 40 px, Consent-Block bricht um. Fehlerpfad teilt den `ErrorAlert`. | Fix 1 |
| `pages/OAuthConsentPage.tsx` | 0 Body-Scroll. **Gelockter Agentenname wird im `readOnly`-Input gekürzt** (scrollWidth 366 > clientWidth 236 @320) — eine Einwilligung zeigt den Agenten damit unvollständig. Langer Redirect-Host bricht sauber um (kein Defekt). Approve/Deny je 40 px. | Fix 1, 4 |
| `pages/InvitationAcceptPage.tsx` | Beide Zustände 0 Überläufer, Button 40 px. Fehlerpfad teilt den `ErrorAlert`. | Fix 1 |
| `pages/AuthCallbackPage.tsx` | Ladezustand sauber. **Fehlerzustand: Body-Scroll 522/320** (Provider-Text). | Fix 1 |
| `pages/SetPasswordPage.tsx` | 0 Überläufer, Felder+Submit 40 px. Fehlerpfad teilt den `ErrorAlert`. | Fix 1 |
| `pages/ResetPasswordPage.tsx` | 0 Überläufer. **„Zurueck zur Anmeldung" (`ghost`/`sm`) = 36 px < 40.** | Fix 1, 2 |
| `pages/ComingSoonPage.tsx` | 0 Überläufer, CTA 40 px, kein Fehlerzustand. **Kein Defekt.** | — |
| `components/OAuthButtons.tsx` | Beide Provider-Buttons gemessen **238×40 px @320**, gestapelt, volle Breite. **Kein Defekt** (AK 4 an dieser Stelle bereits erfüllt). | — |
| `components/TurnstileWidget.tsx` | Rendert einen leeren Container plus Cloudflare-iframe fester Größe (300×65), `flex justify-center` vom Aufrufer. Passt in 288 px Karteninneres. **Kein Defekt.** | — |

Gegenprüfungen gehalten: `grid-cols-*` weiterhin 0 Treffer, Breakpoint-Prefixe
bleiben 0 in den Seitendateien (Weiche 1: das ist Norm-Konformität, kein Befund).

## Fixes

### Fix 1 — Fehlermeldungen brechen um (AK 6, Ursache des einzigen Body-Scrolls)

Der Defekt sitzt nicht in der Textlänge, sondern darin, dass ein ungebrochener
Bezeichner die **min-content-Breite** der Karte aufbläht: `w-full max-w-md`
kann dann nicht mehr schrumpfen, und die Seite scrollt horizontal.

`break-words` (`overflow-wrap: break-word`, **vererbend**) kommt an den
§10.2-`<main>` jeder Karte — ein Ort pro Datei, kein Wrapper, keine
Primitive-Änderung. Damit deckt der Fix alle Fehlerzustände ab, auch die, die
erst zur Laufzeit entstehen. Das ändert das §10.2-Muster, also wird
`docs/frontend/design-language.md` §10.2 **im selben PR** nachgezogen (AK 9,
Weiche 2: Änderung am Muster-Ort).

### Fix 2 — Hit-Targets ≥ 40 px unterhalb `md` (AK 4, Weiche 4)

`LoginPage` Resend-Button und `ResetPasswordPage` „Zurueck zur Anmeldung":
`size="sm"` liefert 36 px. Beide bekommen `h-10 md:h-9` — unterhalb `md` 40 px
(§11), ab `md` bleibt die Verdichtung. `tailwind-merge` löst `h-9` aus der
Variante zugunsten der expliziten Klasse auf (gegengeprüft an der installierten
Version).

### Fix 3 — `flex-wrap` an der Passwort-Zeile (AK 3, Weiche 3, verbindlich)

Die Zeile passt heute gemessen, die Vorentscheidung ist trotzdem umzusetzen:
sie schützt gegen längere Übersetzungen und vergrößerte Schrift, und ein
abgeschnittener Wiederherstellungs-Link verdeckt den einzigen Ausweg aus einem
vergessenen Passwort. Muster: `PageHeader`.

### Fix 4 — Gelockter Agentenname umbrechen statt kürzen (AK 5, Weiche 5)

`readOnly`-Input → umbrechendes Anzeige-Element in derselben Feld-Optik. Der
Wert ist kein Formularfeld (nicht editierbar, nicht Teil des Submits), und
Weiche 5 verlangt für den Consent ausdrücklich Umbruch statt Kürzung: ein
gekürzter Agentenname stellt die Einwilligung unvollständig dar. Testnachbar
wird mitgezogen.

## Bewusst NICHT geändert (Befunde, kein Fix in diesem Paket)

* **`components/ui/alert.tsx` / `components/data/ErrorAlert.tsx`** — der
  Umbruch-Defekt ist generisch und träfe jede Domäne. Out of scope; geht als
  Befund in den Handoff statt in diesen PR.
* **`components/ui/checkbox.tsx`** — 16×16 px Box, effektive Trefferfläche über
  das Label ca. 17 px hoch, also unter §11. Primitive, zwölf Geschwisterpakete
  hängen daran. Befund für den Handoff.
* **Inline-Textlinks** („Passwort vergessen?", „Registrieren", AGB,
  Datenschutz) mit 16 px Zeilenhöhe. §11 bemisst Buttons; Inline-Links im
  Fließtext auf 40 px Touchfläche zu heben ist eine app-weite
  Design-Entscheidung, kein Domänen-Fix. Befund für den Handoff.

## Schritte

1. Messprobe bauen, Baseline messen ✔
2. Test-first: je Fix ein Testfall, rot vor der Änderung
3. Fixes 1–4 umsetzen, Tests grün
4. `docs/frontend/design-language.md` §10.2 nachziehen
5. `changelog.d/`-Fragment (**nicht** `CHANGELOG.md` — `changelog-guard`)
6. Nachmessung mit derselben Probe, Probe löschen
7. DoD: `lint`, `tsc -b`, `test:coverage`, `test:a11y`, `build`, `i18n:check`,
   `license:check`, `check_code_refs`, `changelog_fragments check`
8. Push, PR, `all-green` am exakten Head-SHA prüfen, Handoff an Review

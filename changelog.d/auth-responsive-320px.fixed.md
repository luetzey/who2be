- Die Auth-Seiten sind bei 320px bedienbar: lange Fehlerbezeichner und
  fremdbestimmte Namen brechen um, statt die Seite horizontal scrollen zu
  lassen, und kleine Hit-Targets erreichen auf dem Telefon 40px.

  Ein ungebrochener GoTrue-Bezeichner (etwa
  `unverified_email_address_requires_confirmation`) blaehte bisher die
  min-content-Breite der Auth-Karte auf: `w-full max-w-md` konnte nicht mehr
  schrumpfen und der Login scrollte auf einem 320px-Geraet horizontal
  (gemessen 522px). `break-words` am `<main>` jeder Auth-Seite behebt das
  vererbend, also auch fuer Fehlerzustaende, die erst zur Laufzeit entstehen.

  Im OAuth-Consent zeigte der gesperrte Agentenname in einem
  `readOnly`-`<Input>` — der kuerzt auf schmalen Viewports still, womit die
  Einwilligung ihren eigenen Gegenstand unvollstaendig darstellte. Der Wert
  steht jetzt in einem umbrechenden `<output>` in derselben Feld-Optik.

  Der Resend-CTA auf der Anmeldung und der Zurueck-Link auf der
  Passwort-Zuruecksetzung standen mit `size="sm"` bei 36px — oberhalb des
  verbindlichen Floors (§11: ≥ 32px), aber unterhalb des 40px-Regelfalls an
  zwei Stellen, an denen keine Dichte gewollt ist: beide sind der einzige
  Ausweg aus einem fehlgeschlagenen Login. Unterhalb `md` sind es jetzt
  40px, ab `md` bleibt die Verdichtung.
  `docs/frontend/design-language.md` §10.2 und §11 halten beide Muster fest.

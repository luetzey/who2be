# Compliance-Nachzug Turnstile: Cloudflare in `vvt.md` §5/§6 + i18n-Abschnitt `privacy.sections.captcha`

Karte: `t_6c333cc8` · Eltern: `t_a662079e` (Review von #539 / PR #558)
Branch: `p_2d6a9710/t_6c333cc8-compliance-nachzug-turnstile-cloudflare` (auf `origin/main`, 87de64c)

## Ausgangslage (gemessen, nicht angenommen)

PR #558 ist **offen und nicht gemergt** (`gh pr view 558`: OPEN, CLEAN,
Head `wt/i539-turnstile`). Die in der Karte zitierte Checklisten-Zeile
„AV-Liste (Hetzner, Mollie, Mail, **Cloudflare** falls Turnstile aktiv) …
Quelle: `vvt.md` §5/§6" existiert deshalb **noch nicht auf `main`**, sondern
nur im PR-Branch (verifiziert via
`git diff origin/main...origin/wt/i539-turnstile -- docs/compliance/legal-texts-checklist.md`).

Folge für den Scope: diese Karte arbeitet **additiv auf `main`** und macht
genau die beiden Enden auf, auf die #558 zeigt. `legal-texts-checklist.md`
wird **nicht** angefasst — die Zeile gehört #558, ein zweites Mal geschrieben
gäbe Merge-Konflikt und doppelte Wahrheit.

Fundstellen:
- `docs/compliance/vvt.md:111-118` — §5-Tabelle, keine Cloudflare-Zeile.
- `docs/compliance/vvt.md:143-150` — §6 behauptet „kein Drittlandtransfer",
  Kern-Verarbeiter „Hetzner, Mollie, self-hosted GoTrue".
- `apps/web/src/i18n/locales/{de,en}.json:1023-1071` — `legal.privacy.sections`,
  kein `captcha`-Knoten.
- `apps/web/src/features/legal/pages/PrivacyPage.tsx:61-71` — Muster für
  `LegalSection` + `Placeholder`, zwischen `payment` (7) und `email` (8).
- Sachstand Turnstile (aus #558, `docs/signup-and-invites.md` §3 + §Datenschutz):
  Cloudflare Turnstile, Site-Key `WHO2BE_TURNSTILE_SITE_KEY`, Secret
  `GOTRUE_SECURITY_CAPTCHA_SECRET`, Schalter
  `GOTRUE_SECURITY_CAPTCHA_ENABLED`; **ab Werk aus**, ohne Site-Key wird das
  Script nicht geladen ⇒ kein Transfer.

## Schritte

1. `vvt.md` §5: bedingte Cloudflare-Zeile in die Empfänger-Tabelle
   (Rolle Bot-Abwehr, Daten IP + Browser-Signale, Standort USA/Drittland,
   AVV-Platzhalter), mit „nur wenn aktiviert"-Vorbehalt wie in der Checkliste.
2. `vvt.md` §6: Drittland-Vorbehalt ergänzen — die „kein Drittlandtransfer"-
   Aussage an den Werkszustand binden (Turnstile aus) und Cloudflare als vom
   Betreiber zu prüfende Ausnahme führen.
3. `de.json` + `en.json`: `legal.privacy.sections.captcha` (`heading` + `body`)
   zwischen `payment` und `email` einfügen; die nachfolgenden Überschriften
   umnummerieren (E-Mail 8→9, Empfänger 9→10, Speicherdauer 10→11,
   Rechte 11→12). Keine Referenz im Repo hängt an diesen Nummern (geprüft).
4. `PrivacyPage.tsx`: `LegalSection` für `captcha` analog zu `payment`.
5. Test `PrivacyPage.a11y.test.tsx` um eine Assertion auf den neuen Abschnitt
   erweitern, damit der Key nicht wieder still verschwindet.
6. `CHANGELOG.md` Unreleased-Eintrag (Doku als DoD).
7. DoD nach `CONTRIBUTING.md` §Definition of Done, Web-Stack auf **Node 22**
   (`mise exec node@22`), Python-Stack weil `docs/**` + `apps/web/**` gemischt.

## Abgrenzung

- Keine Rechtsberatung, keine Inhalte: alles Platzhalter, wie die übrigen
  Abschnitte. Der Owner füllt.
- Keine Änderung an Turnstile-Code, Env-Namen oder `legal-texts-checklist.md`.
- Der bekannte Folgebefund `t_c007ed1d` (aktives Captcha bricht
  Passwort-Login/Resend) ist **nicht** Teil dieser Karte.

## Risiko

`de.json`/`en.json` werden auch von #558 angefasst (dort `auth.signup.captcha.*`,
~Zeile 300er-Bereich; hier `legal.privacy.sections.*`, Zeile ~1055). Textuell
weit auseinander, Konflikt unwahrscheinlich — aber wer zuerst merged, zwingt den
anderen zum Rebase. Im Übergabe-Bericht vermerkt.

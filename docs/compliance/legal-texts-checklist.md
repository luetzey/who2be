# Betreiber-Checkliste: Rechtstexte (Impressum & Datenschutz)

> ⚠️ **Disclaimer:** Engineering-Checkliste, **keine Rechtsberatung.** Sie listet
> auf, **welche Inhalte** die Rechtstexte noch brauchen — sie liefert **keinen**
> verbindlichen Text. Die finale Formulierung gehoert zum Betreiber/Anwalt. Stand:
> 2026-06-05.

Die Rechtsseiten existieren als **Strukturgeruest mit Platzhaltern**
(`<PLATZHALTER: …>` ueber die `Placeholder`-Komponente). Diese Checkliste sagt,
was die Platzhalter konkret ersetzen muss. Befunde **L1** (Impressum) und **L2**
(Datenschutzerklaerung).

> ✅ **Bereits korrekt — NICHT verschlechtern:**
> - Impressum verweist auf **§ 5 DDG** (Digitale-Dienste-Gesetz, korrekt — *nicht*
>   „TMG"). Datei: `apps/web/src/features/legal/pages/ImpressumPage.tsx`,
>   i18n-Key `legal.impressum.sections.legalNotice.heading`.
> - Datenschutzerklaerung verweist auf **§ 25 TDDDG** (Telekommunikation-
>   Digitale-Dienste-Datenschutz-Gesetz, korrekt — *nicht* „TTDSG"). Datei:
>   `apps/web/src/features/legal/pages/PrivacyPage.tsx`, i18n-Key
>   `legal.privacy.sections.cookies.text1`.
> - Impressum verweist auf **§ 18 Abs. 2 MStV** (Verantwortlicher) und **§ 27a
>   UStG** (USt-IdNr). Diese Paragraphen-Verweise sind korrekt und bleiben.

---

## 1 · Impressum (§ 5 DDG) — `ImpressumPage.tsx`

| Pflichtangabe | i18n-Platzhalter-Key | Inhalt, den der Betreiber liefern muss |
|---|---|---|
| Firmenname / Rechtsform | `impressum.…legalNotice.companyName` | Vollstaendiger Name + Rechtsform (z. B. „… GmbH") |
| Anschrift (Strasse, PLZ, Ort, Land) | `…legalNotice.street/city/country` | Ladungsfaehige Anschrift (kein Postfach) |
| Vertretungsberechtigte Person(en) | `…representative.name` | Geschaeftsfuehrung/Inhaber |
| Kontakt (Telefon, E-Mail) | `…contact.phone/email` | Schnelle elektronische Kontaktaufnahme (E-Mail Pflicht, Telefon empfohlen) |
| Registereintrag (Register, Gericht, Nr.) | `…register.registry/court/number` | HRB/HRA/Vereinsregister + Registergericht + Nummer (falls eingetragen) |
| USt-IdNr (§ 27a UStG) | `…vatId.value` | USt-IdNr, **falls vorhanden** (siehe GoBD-Doku §6 offene Frage) |
| Verantwortlicher (§ 18 Abs. 2 MStV) | `…responsible.name` | Name + Anschrift (nur bei journalistisch-redaktionellen Inhalten relevant — pruefen) |
| EU-Streitschlichtung (OS-Plattform) | `…dispute.platformLink/participation` | Link zur OS-Plattform + Aussage zur (Nicht-)Teilnahme an Verbraucherschlichtung |

**Zu pruefen / entscheiden:**
- [ ] Aufsichtsbehoerde/Erlaubnis nur falls reglementiertes Gewerbe (i. d. R. n/a).
- [ ] OS-Plattform-Hinweis: seit Einstellung der EU-OS-Plattform pruefen, ob/in
      welcher Form der Hinweis noch zu fuehren ist (`<rechtliche Pruefung>`).
- [ ] Teilnahmebereitschaft an Verbraucherschlichtungsstelle (ja/nein/nicht
      verpflichtet) festlegen.

---

## 2 · Datenschutzerklaerung — `PrivacyPage.tsx`

| Abschnitt | i18n-Platzhalter-Key | Inhalt, den der Betreiber liefern muss |
|---|---|---|
| Verantwortlicher | `privacy.…controller.contactPlaceholder` | Name/Anschrift/Kontakt des Verantwortlichen (= Impressum) |
| Datenschutzbeauftragter | `…controller.dpoPlaceholder` | DSB-Kontakt oder begruendetes „nicht benannt" |
| Hosting & Infrastruktur | `…hosting.body` | Hetzner (Standort DE/FI), AVV, Rechtsgrundlage — siehe `vvt.md` §5, RUNBOOK §Standort |
| Server-Logs | `…serverLogs.body` | erhobene Logdaten, Zweck, **Speicherdauer**, Rechtsgrundlage Art. 6 I f |
| Cookies & Einwilligung | `…cookies.listPlaceholder` | konkrete Cookie-Liste, Speicherdauer, Widerrufsweg (§ 25 TDDDG bleibt!) |
| Registrierung & Konto | `…account.body` | verarbeitete Stammdaten, Zweck (Art. 6 I b), Speicherdauer (→ `data-retention-and-erasure.md`) |
| Authentifizierung (GoTrue) | `…auth.body` | GoTrue-Auth, verarbeitete Daten, OAuth-Provider (falls aktiv: Google/GitHub + Drittland) |
| Zahlungsabwicklung | `…payment.body` | Mollie als PSP, uebermittelte Daten, Mollie-Datenschutzhinweis, Rechtsgrundlage |
| E-Mail-Versand | `…email.body` | Mail-/SMTP-Provider + Standort, Anlaesse (Verify/Invite/Reset), Rechtsgrundlage |
| Empfaenger & Auftragsverarbeiter | `…processors.body` | AV-Liste (Hetzner, Mollie, Mail), Drittlandtransfer + Garantien — Quelle: `vvt.md` §5/§6 |
| Speicherdauer | `…retention.body` | Loeschkonzept + gesetzliche Aufbewahrung — Quelle: `data-retention-and-erasure.md` |
| Betroffenenrechte / Aufsichtsbehoerde | `…rights.authorityPlaceholder` | zustaendige Aufsichtsbehoerde benennen |

**Zu pruefen / entscheiden:**
- [ ] OAuth-Provider (Google/GitHub) aktiv? Falls ja: Drittland-USA + Garantien
      ergaenzen.
- [ ] Mail-/SMTP-Provider + Standort festlegen (Drittland-Pruefung).
- [ ] Konkrete Speicherfristen aus `data-retention-and-erasure.md` uebernehmen.

---

## 3 · AGB (`TermsPage.tsx`) — Status & verbleibende Inhalte

Struktur ist gesetzt (WP-I): **A. Allgemein**, **B. Verbraucher (B2C)**,
**C. Unternehmer (B2B)**, inkl. SLA-Geruest (§ 7), Widerrufsbelehrung (§ 11) und
E-Rechnungs-Empfaengerzustimmung (§ 12). Es fehlen die **Inhalte** (alle als
`<PLATZHALTER>` markiert):

- [ ] Leistungsbeschreibung + Plan-Umfang (Free/Pro) ausformulieren.
- [ ] Preise/Zahlungsbedingungen (Mollie) konkretisieren.
- [ ] **SLA-Werte** (Verfuegbarkeit, Reaktionszeiten, Wartungsfenster,
      Service-Gutschriften) festlegen — § 7.
- [ ] **Widerrufsbelehrung** + Muster-Widerrufsformular (Verbraucher) — § 11
      (anwaltlich; ggf. Hinweis auf vorzeitigen Leistungsbeginn).
- [ ] **E-Rechnung B2C:** Formulierung der Empfaengerzustimmung — § 12.
- [ ] B2B-Abweichungen (Haftung, Gerichtsstand, Widerrufsausschluss) — §§ 13–14.

---

## 4 · AVV/DPA (`DpaPage.tsx`)

Struktur (Art. 28 DSGVO) vorhanden; Inhalte offen: TOM-Anlage (→ `vvt.md` §8),
Subprozessor-Liste (→ `vvt.md` §5), Drittlandangaben, Loeschkonzept (→
`data-retention-and-erasure.md`). Anwaltliche Pruefung erforderlich.

---

## 5 · Dateibezug (fuer den Betreiber)

| Seite | Komponente | i18n-Namespace |
|---|---|---|
| Impressum | `apps/web/src/features/legal/pages/ImpressumPage.tsx` | `legal.impressum.*` |
| AGB | `apps/web/src/features/legal/pages/TermsPage.tsx` | `legal.terms.*` |
| Datenschutz | `apps/web/src/features/legal/pages/PrivacyPage.tsx` | `legal.privacy.*` |
| AVV/DPA | `apps/web/src/features/legal/pages/DpaPage.tsx` | `legal.dpa.*` |

i18n-Quellen: `apps/web/src/i18n/locales/de.json` + `en.json`. Platzhalter sind
ueber die `Placeholder`-Komponente (`<PLATZHALTER: …>`) im UI rot/gestrichelt
markiert, damit kein Platzhalter versehentlich live geht.

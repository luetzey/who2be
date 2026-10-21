# ADR-0061 — Rechnungsstellung über Mollie Invoicing (Sales Invoices API)

- Status: **Accepted** (Owner, 2026-10-20). Die Richtung steht im Wortlaut in
  Abschnitt 2. Drei Weichen (W61-1 bis W61-3, Abschnitt 11) liegen beim
  Owner; jede trägt eine Empfehlung, die bis zur Entscheidung als Annahme
  gilt und mit der Entscheidung nachgetragen wird.
- Datum: 2026-10-21
- Gemessen gegen: `origin/main` @ `e09c9c4b`. Code-Aussagen tragen einen
  Symbolanker (Konvention `docs/code-references.md`).
- Grundlage: zwei Berichte außerhalb des Repos, beide vom 2026-10-20:
  „Zahlung und Rechnung für den Who2Be-Cloud-Release“ (Karte t_568abafb,
  im Folgenden „Bericht §n“) und „Mollie Invoicing – Go/No-go-Test im
  Testmodus“ (Karte t_f6e65a16, im Folgenden „Test Pn“). Diese ADR entsteht
  auf Kanban-Karte t_d9701423 (Paket R0).
- Bezug: ADR-0029 (Billing build-zeit-isoliert, nur Cloud), ADR-0031
  (Compliance-Journale, Aufbewahrung vor Löschung), ADR-0048 (BlobStore),
  ADR-0057 (Worker für Hintergrund-Routinen),
  `docs/compliance/gobd-verfahrensdokumentation.md`, `docs/compliance/vvt.md`.
- Umfang: **nur Dokumentation.** Diese ADR ändert keinen Code, kein Schema
  und kein Compose. Umsetzung in den Paketen R1 und R2 (Abschnitt 10).

> **Keine Steuer- oder Rechtsberatung.** Alle steuerlichen Aussagen sind
> Arbeitsannahmen aus dem Bericht und **mit dem Steuerberater zu bestätigen**.
> Genau deshalb sind Steuermodus und Preisbasis Schalter (Abschnitt 5) und
> keine fest verdrahtete Logik.

## Inhalt

1. Kontext und Befund
2. Entscheidung (Owner-Wortlaut)
3. Ablauf: bezahlte Zahlung wird bezahlte Rechnung
4. Idempotenz: genau eine Rechnung je Zahlung
5. Schalter: Steuermodus und Preisbasis
6. Steuerlogik als Tabelle
7. PDF-Archiv
8. Storno und Erstattung
9. Datenschutz
10. Umsetzung in Paketen
11. Weichen (offen, mit Empfehlung)
12. Verworfene Optionen
13. Konsequenzen

## 1. Kontext und Befund

Who2Be rechnet die Cloud-Edition heute über Mollie ab: Checkout legt einen
Customer und eine Erstzahlung an, der Webhook holt die Zahlung nach
(Pull-after-Ping) und leitet daraus das Entitlement ab
(`packages/billing/src/who2be_billing/mollie.py#MollieBillingService.handle_webhook`).
Eine Rechnung im Sinne von §14 UStG entsteht dabei nicht. Die
Verfahrensdokumentation sagt das ausdrücklich: „Who2Be stellt keine eigenen
Rechnungen aus“ (`docs/compliance/gobd-verfahrensdokumentation.md` §5).

Gebraucht wird zum Cloud-Release eine Rechnung mit fortlaufender Nummer,
Kundenadresse, gegebenenfalls beiden USt-IdNr. und Reverse-Charge-Vermerk, mit
der richtigen Steuer je Kunde und einer Aufbewahrung von 8 bis 10 Jahren
(Bericht §1, §2).

Der Go/No-go-Test im Mollie-Testmodus hat die Sales Invoices API geprüft und
mit „GO mit Auflagen“ abgeschlossen. Belegt sind [B = Beleg im Testbericht]:

- Eine Rechnung mit `status=paid` und `paymentDetails.source=payment` plus
  `sourceReference=<payment_id>` bezieht sich auf eine schon bezahlte Zahlung,
  ohne sie ein zweites Mal einzuziehen (Test P3a).
- Eine erfundene `sourceReference` lehnt Mollie mit HTTP 422 ab (Test P3a).
- **Mollie sperrt keine Duplikate:** dieselbe Zahlung ein zweites Mal
  referenziert ergibt eine zweite Rechnung mit neuer Nummer (Test P3b).
- Den Reverse-Charge-Vermerk druckt Mollie nicht von selbst; er kommt nur über
  das Freitextfeld `memo` aufs PDF (Test P1).
- Mollie prüft die USt-IdNr. des Empfängers nicht (im Testmodus belegt, Test P1).
- Eine Gutschrift oder Stornorechnung gibt es in der API nicht. Der Status
  heißt `payment-reversed` mit Bindestrich, nicht wie in der Referenz mit
  Unterstrich (Test P3c).
- Das PDF liegt hinter `_links.pdfLink`, einem API-Endpunkt mit
  Authentifizierung, keine öffentliche URL (Test P3d).
- OSS (`vatScheme=one-stop-shop`) lehnt Mollie ab, solange das Konto nicht für
  OSS registriert ist (Test P2b).
- Nummernkreis, Präfix und Absenderangaben stammen aus dem Mollie-Profil
  (Test P4). Die Sprache folgt `recipient.locale` (Test P4).
- Invoicing kostet nichts zusätzlich (Test P5, offizielle Preisseite).
- Mollie bewahrt Rechnungen nur 5 Jahre auf (Bericht §3.2).

## 2. Entscheidung (Owner-Wortlaut)

Owner, 2026-10-20 (Telegram), zuerst zum Auftrag der Recherche:

> „2. Recherchieren und beste Technolgie auswählen (gerne deutsche Anbieter
> oder EU, buget freundlich beim start, gute Softwareeinbindung)“

und nach dem Testbericht:

> „mollie ok“

Bedeutung (Option A1 im Bericht):

- Mollie bleibt Zahlungsanbieter.
- Rechnungen stellt Who2Be über **Mollie Invoicing** (Sales Invoices API) aus.
- Steuerfragen (Kleinunternehmer ja/nein, netto oder brutto, Text des
  Reverse-Charge-Vermerks, Storno) klärt der Owner mit dem Steuerberater. Der
  Code baut sie deshalb **umschaltbar**, nicht fest verdrahtet.

## 3. Ablauf: bezahlte Zahlung wird bezahlte Rechnung

Die Rechnung entsteht im bestehenden Mollie-Webhook-Pfad, nicht in einem
eigenen Sales-Invoice-Webhook. Mollie bietet Webhooks für Sales Invoices an
(Test P5), sie sind für diesen Ablauf aber nicht nötig.

1. **Auslöser.** `handle_webhook` stellt fest, dass eine Zahlung bezahlt ist:
   die Erstzahlung (`sequenceType=first`) oder eine Folgezahlung des Abos.
   Nicht bezahlte Zahlungen (fehlgeschlagen, offen) lösen keine Rechnung aus.
2. **Vormerken.** Im selben Transaktionspfad wie das Entitlement legt der
   Webhook eine Zeile „Rechnung zu Zahlung `<payment_id>`“ mit Status
   `pending` an (Abschnitt 4). Ab hier ist die Rechnung geschuldet, auch wenn
   der Mollie-Aufruf danach scheitert.
3. **Steuerfall bestimmen.** Eine reine Funktion bildet Rechnungsdaten der
   Organisation (aus R1) und die beiden Schalter (Abschnitt 5) auf einen
   Steuerfall ab: Satz, `vatMode`, `memo`, Empfängertyp (Abschnitt 6).
4. **Ausstellen.** `POST /v2/sales-invoices` mit:
   - `status=paid`, `paymentDetails={source: "payment", sourceReference: <payment_id>}`
   - `vatScheme=standard` (OSS erst, wenn das Konto registriert ist)
   - `vatMode` nach Schalter Preisbasis (`exclusive` oder `inclusive`)
   - `recipient`: `type` `consumer` oder `business`, Name bzw.
     `organizationName`, Adresse, bei `business` die `vatNumber`, `locale`
   - eine Zeile: Plan-Name und Leistungszeitraum in der Beschreibung
     (höchstens 100 Zeichen, Test P4), Betrag, `vatRate`
   - `memo` je Steuerfall (Abschnitt 6), sonst leer
5. **Archivieren.** Who2Be holt das PDF serverseitig über `_links.pdfLink` mit
   dem API-Key und legt es im eigenen Archiv ab (Abschnitt 7). Danach ist die
   Zeile `archived`.
6. **Fehler.** Scheitert Schritt 4 oder 5, bleibt die Zeile `pending` bzw.
   `issued`. Der Webhook quittiert Mollie trotzdem mit 200, denn das
   Entitlement ist geschrieben und ein Mollie-Retry würde wegen des
   Dedupe-Ledgers ohnehin nichts mehr auslösen. Eine Worker-Routine (ADR-0057)
   nimmt offene Zeilen wieder auf (Abschnitt 4).

Festlegungen aus dem Test, die der Code einhält:

- **Sprache:** `de_DE` für Empfänger in DE, AT, CH und LI, sonst `en_GB`.
  Mollie lässt weitere Locales zu (Test P4); zwei Sprachen reichen zum Start.
- **Absender, Nummernkreis, Präfix:** nur im Mollie-Profil, nie im Code. Das
  Jahr gehört ins Präfix, weil der Zähler zum 1. Januar zurückgesetzt wird
  (Test P4). Das richtet der Betreiber in Mollie ein.
- **Testmodus:** Tests sprechen nie mit Mollie (gemockte API). Ein manueller
  Probelauf im Testmodus schickt die Rechnung nur an verifizierte Adressen der
  eigenen Organisation, sonst HTTP 422 (Test, Abschnitt „Auswirkung auf das
  Coder-Paket“).
- **Ohne Steuermodus keine Rechnung:** Fehlt der Schalter aus Abschnitt 5,
  entsteht keine Rechnung, die Zeilen bleiben `pending`. Fail closed statt
  einer Rechnung mit geratener Steuer. Nachholen geht: Mollie stellt eine
  bezahlte Rechnung auch nachträglich zu einer längst bezahlten Zahlung aus
  (Test P3b, zweite Rechnung zur selben Zahlung).

## 4. Idempotenz: genau eine Rechnung je Zahlung

Mollie verhindert keine doppelte Rechnung (Test P3b). Who2Be sichert deshalb
selbst ab, und zwar an zwei Stellen.

**Eine Zeile je Zahlung.** Eine eigene Tabelle (Arbeitsname
`billing_invoice`, Migration in R2, Nummer nach Reservierung 0109 und vor dem
Anlegen gegen `origin/main` geprüft) mit `UNIQUE (payment_id)`. Felder:
`org_id`, `payment_id`, `status` (`pending`, `issued`, `archived`,
`failed`), Mollie-Rechnungs-ID, Rechnungsnummer, SHA-256 und Ablageort des
PDF, Zeitpunkte, letzter Fehler. Die Zeile entsteht mit
`INSERT … ON CONFLICT (payment_id) DO NOTHING`. Ein zweiter Webhook oder ein
paralleler Worker-Lauf findet die Zeile und legt keine zweite Rechnung an.

Der vorhandene Dedupe-Ledger `processed_webhook_event`
(`packages/billing/src/who2be_billing/processed_event_repository.py#PgProcessedEventRepository.claim`)
bleibt, wie er ist. Er schützt den ganzen Webhook vor Replays, gibt seinen
Claim aber bei einem Fehler wieder frei
(`packages/billing/src/who2be_billing/mollie.py#MollieBillingService._released_on_error`).
Die Rechnung braucht einen Zustand, der den Fehler überlebt; deshalb die
eigene Zeile statt nur des Ledgers.

**Unsichere Antwort.** Der gefährliche Fall ist ein Timeout nach dem POST:
Mollie hat die Rechnung vielleicht angelegt, Who2Be weiß es nicht. Bevor der
Worker für eine Zeile in diesem Zustand erneut POSTet, sucht er die
Rechnung bei Mollie über die List-API: die neuesten Rechnungen, verglichen auf
`paymentDetails[].sourceReference == payment_id`. Findet er sie, übernimmt er
ID und Nummer und POSTet nicht. Ob die List-API dafür einen Filter hat oder
seitenweise gelesen werden muss, belegt R2 gegen die Referenz.

**Retry.** Eine Worker-Routine `invoice-retry` (Registry nach ADR-0057) nimmt
Zeilen in `pending` oder `issued` auf, die älter als einige Minuten sind, mit
begrenzter Wiederholung und Backoff. Nach dem letzten Versuch steht die Zeile
auf `failed` und ist in der Betreiber-Sicht sichtbar. Keine Rechnung geht
still verloren.

## 5. Schalter: Steuermodus und Preisbasis

Zwei Umgebungsvariablen, wie alle Betriebseinstellungen des Repos
(`apps/api/src/who2be_api/core/config.py#Settings`). Keine UI, keine DB-Zeile:
die Werte ändern sich höchstens nach einer Entscheidung mit dem
Steuerberater, und ein Wechsel gehört in den Deploy, nicht in einen Klick.

| Variable | Werte | Ohne Wert |
| --- | --- | --- |
| `WHO2BE_INVOICE_TAX_MODE` | `regular` (Regelbesteuerung) · `small_business` (Kleinunternehmer §19 UStG) | **keine Rechnung**, Zeilen bleiben `pending`, Warnung im Log und in der Betreiber-Sicht |
| `WHO2BE_INVOICE_PRICE_BASIS` | `net` (Plan-Preis ist netto, `vatMode=exclusive`) · `gross` (Plan-Preis ist brutto, `vatMode=inclusive`) | `net` |

Bewusst so:

- **Kein Default für den Steuermodus.** Ein falscher Steuermodus erzeugt
  Rechnungen mit falscher Steuer und vergebener Nummer, die sich über die API
  nicht stornieren lassen (Abschnitt 8). Ohne Wert lieber keine Rechnung.
- **Default `net` für die Preisbasis.** Der Bericht rechnet mit Nettopreisen
  (Bericht §3, Rechenbasis); ohne Steuermodus entsteht ohnehin keine Rechnung.
- **Ein Wechsel wirkt nur nach vorn.** Ausgestellte Rechnungen bleiben, wie sie
  sind. Die Zeile hält fest, mit welchen Schalterwerten sie entstanden ist.

**Wirkung auf den Zahlbetrag.** Bei `net` hängt der Zahlbetrag vom Steuerfall
ab (netto × (1 + Satz)). Die Steuerfunktion aus Abschnitt 6 bestimmt ihn
deshalb schon beim Checkout, und die Mollie-Subscription wird mit diesem
Betrag angelegt. Ändert eine Organisation später Land, Kundentyp oder
USt-IdNr., muss der Abo-Betrag mitziehen (R1/R2). Bei `gross` siehe Weiche
W61-2.

Der Plan-Preis selbst kommt weiter aus
`packages/billing/src/who2be_billing/plans.py#PRO_PLAN` und ist nicht Teil
dieser ADR.

## 6. Steuerlogik als Tabelle

Eine reine Funktion ohne I/O, mit Tests für jede Zeile (R1). Eingaben:
Steuermodus, Preisbasis, Land der Rechnungsadresse, Kundentyp (B2B/B2C),
USt-IdNr. mit Prüfstand (geprüft gültig, ungültig, ungeprüft). Ausgabe:
Satz, `vatMode`, Empfängertyp, `memo`-Schlüssel.

**Steuermodus `regular`** (Arbeitsannahme, mit Steuerberater zu bestätigen):

| Fall | Satz | Empfänger | `memo` |
| --- | --- | --- | --- |
| DE, B2B oder B2C | 19 % | `business` bzw. `consumer` | keines |
| EU (ohne DE), B2B, USt-IdNr. per VIES gültig | 0 % | `business` mit `vatNumber` | Reverse Charge |
| EU (ohne DE), B2B, USt-IdNr. ungeprüft | siehe Weiche W61-3 | | |
| EU (ohne DE), B2B, USt-IdNr. ungültig oder fehlt | 19 % (wie B2C) | `business` ohne `vatNumber` | keines |
| EU (ohne DE), B2C, unter der EU-Schwelle | 19 % DE | `consumer` | keines |
| Drittland, B2B | 0 % | `business` | nicht im Inland steuerbar |
| Drittland, B2C | 0 % | `consumer` | nicht im Inland steuerbar |

Hintergrund der Zeilen (Bericht §2, alles mit Steuerberater zu bestätigen):

- EU-B2B: Leistungsort beim Empfänger (§3a Abs. 2 UStG), der Empfänger
  schuldet die Steuer. Die Rechnung braucht beide USt-IdNr. und den Vermerk
  „Steuerschuldnerschaft des Leistungsempfängers“ (§14a Abs. 5 UStG). Die
  eigene USt-IdNr. druckt Mollie aus dem Profil.
- EU-B2C: Bis 10.000 € EU-weit (Vorjahr und laufendes Jahr) bleibt der
  Leistungsort in DE (§3a Abs. 5 UStG). Who2Be überwacht diese Schwelle nicht;
  das tut der Betreiber mit seiner Buchhaltung. Über der Schwelle braucht es
  OSS: Konto bei Mollie registrieren, dann `vatScheme=one-stop-shop` und eine
  neue Zeile in dieser Tabelle (Ausbaupfad, Abschnitt 13). Ob Mollie den Satz
  des Ziellands dann selbst wählt, ist nicht getestet (Test P2b).
- Drittland: in DE nicht steuerbar. Ob in einzelnen Ländern eine eigene
  Registrierungspflicht entsteht (etwa CH, UK, NO für B2C-Digitalleistungen),
  klärt der Betreiber mit dem Steuerberater, bevor Drittland-Kunden zahlen.

**Steuermodus `small_business`:** jede Rechnung mit 0 %, Empfänger nach
Kundentyp, `vatNumber` wie angegeben, `memo` Kleinunternehmer. Kein
Reverse-Charge-Vermerk, kein OSS (Test, Frage 2 an den Steuerberater).

**`memo`-Texte.** Die Texte stehen als Konstanten im Code, je Sprache, mit
einem Kommentar „mit Steuerberater zu bestätigen“. So gehen sie durch ein
Review, statt in einer Umgebungsvariable zu verschwinden. Arbeitsfassungen:

| Schlüssel | de_DE | en_GB |
| --- | --- | --- |
| Reverse Charge | Steuerschuldnerschaft des Leistungsempfängers. | Reverse charge: VAT to be accounted for by the recipient. |
| nicht im Inland steuerbar | Nicht im Inland steuerbare Leistung. | Service not subject to German VAT. |
| Kleinunternehmer | Gemäß § 19 UStG wird keine Umsatzsteuer berechnet. | No VAT is charged under section 19 of the German VAT Act (small business). |

Die Prüfung der USt-IdNr. per VIES baut R1 (Ausfall oder Timeout: speichern
und als „ungeprüft“ markieren, kein Blocker im Checkout).

## 7. PDF-Archiv

**Pflicht.** Rechnungen sind 8 Jahre aufzubewahren (§14b UStG), Buchungsbelege
je nach Art bis zu 10 Jahre (§147 AO). Who2Be hält jedes Rechnungs-PDF
**mindestens 10 Jahre ab Ende des Ausstellungsjahres** vor, damit die längere
Frist sicher erfüllt ist (die genaue Frist legt der Steuerberater fest). Mollie
selbst hält nur 5 Jahre (Bericht §3.2), das eigene Archiv ist also die
maßgebliche Kopie.

**Unveränderbarkeit.** Das PDF wird unverändert abgelegt, so wie Mollie es
liefert. Die Archivzeile trägt den SHA-256 des PDF; die Laufzeitrolle darf
Archivzeilen nur anlegen und den Status nach vorn setzen, nie das PDF oder den
Hash ändern (Grant-Schnitt wie bei `entitlement_history`, ADR-0031). Löschen
darf nur die Owner-Rolle, und zwar erst nach Ablauf der Frist.

**Ablageort:** offene Weiche **W61-1** (Abschnitt 11). Empfehlung: eigener
Präfix `invoices/<org_id>/<jahr>/<rechnungsnummer>.pdf` im vorhandenen
BlobStore (ADR-0048), Katalog in Postgres. Der Präfix liegt bewusst außerhalb
von `blobs/<workspace_id>/`, den der Workspace-Purge räumt
(`apps/api/src/who2be_api/blobstore/port.py#workspace_prefix`).

**Auslaufen.** Nach Ablauf der Frist löscht eine Worker-Routine PDF und Zeile.
Die Routine kommt erst, wenn die erste Rechnung fällig wird, frühestens 2037;
bis dahin genügt der Eintrag in der Fristentabelle des Löschkonzepts.

## 8. Storno und Erstattung

Die Sales Invoices API kennt keine Gutschrift und keine Stornorechnung. Eine
Rechnung lässt sich nur auf `payment-reversed` setzen; sie behält dabei ihre
Nummer (Test P3c).

Festlegung für den Start:

- **Who2Be ändert ausgestellte Rechnungen nicht automatisch.** Kein PATCH auf
  `payment-reversed`, kein Löschen.
- **Erstattung und Rückbuchung macht der Betreiber von Hand** und erstellt
  den Korrekturbeleg selbst (Stornorechnung mit Bezug auf die Originalnummer,
  im Mollie-Dashboard oder in der Buchhaltung). Den Beleg legt er im selben
  Archiv ab. Welcher Beleg genau nötig ist, klärt er mit dem Steuerberater
  (Test, Frage 5).
- **Hinweis im Betreiber-Ablauf:** Der Ablauf für Erstattungen kommt mit R2 in
  `docs/cloud-erstinbetriebnahme.md` und in die Verfahrensdokumentation.

Grenze heute, ehrlich benannt: Der Dedupe-Ledger beansprucht je Zahlung genau
einen Ping
(`packages/billing/src/who2be_billing/mollie.py#MollieBillingService.handle_webhook`).
Ein späterer
Ping zur selben Zahlung, etwa nach einer Rückbuchung, ist deshalb ein No-Op.
Who2Be erkennt Erstattungen also heute nicht von selbst. Eine automatische
Erkennung mit Hinweis an den Betreiber ist Ausbaupfad (Abschnitt 13); bis
dahin sieht der Betreiber Erstattungen im Mollie-Dashboard.

## 9. Datenschutz

**Neue Daten.** Für die Rechnung erfasst R1 je Organisation: Kundentyp,
Firmenname oder Name, Rechnungsadresse, Land, optional USt-IdNr. mit
Prüfstand und Prüfzeitpunkt. Dazu kommt die Rechnungszeile aus Abschnitt 4
und das PDF, das Name und Adresse enthält.

**Rechtsgrundlage.** Vertrag (Art. 6 Abs. 1 lit. b DSGVO) für die Erfassung,
gesetzliche Pflicht (lit. c, §14 und §14b UStG, §147 AO) für Rechnung und
Aufbewahrung.

**Empfänger.** Mollie B.V. (NL) bekommt die Rechnungsdaten mit jeder
Rechnung; VIES (EU-Kommission) bekommt die USt-IdNr. zur Prüfung. Mollie ist
im VVT schon als Empfänger geführt. Ob für Invoicing eine eigene Vereinbarung
nötig ist, prüft der Betreiber anhand der Mollie-Invoicing-Bedingungen.

**Löschung.** Zwei Klassen, wie bei `entitlement_history` (ADR-0031):

- **Rechnungsdaten der Organisation** (die erfassten Stammdaten aus R1)
  fallen mit dem Konto- bzw. Org-Purge weg. Der Purge-Test ist Teil von R1.
- **Ausgestellte Rechnungen** (Archivzeile und PDF) bleiben trotz
  Löschwunsch bis zum Ende der Frist aus Abschnitt 7 (Art. 17 Abs. 3 lit. b
  DSGVO). Die Archivzeile hat deshalb keinen `ON DELETE CASCADE` auf die
  Organisation.

**VVT und Löschkonzept** werden mit den Paketen nachgezogen, die die Daten
einführen: die Stammdaten mit R1, Rechnung und Archiv mit R2
(`docs/compliance/vvt.md` §3 und §7,
`docs/compliance/data-retention-and-erasure.md` §3).

**Öffentliches Repo.** Beispiele, Tests und Doku verwenden nur Platzhalter
(Adresse, Name, USt-IdNr. als `<USt-IdNr.>`). Keine Daten des Betreibers,
keine Mollie-IDs aus dem Testbericht, keine Keys.

## 10. Umsetzung in Paketen

| Paket | Inhalt | Voraussetzung |
| --- | --- | --- |
| **R0** | diese ADR, Hinweis in der Verfahrensdokumentation | — |
| **R1** | Rechnungsdaten im Checkout bzw. BillingPanel (Kundentyp, Name/Firma, Adresse, USt-IdNr.), Validierung in Client und Server, VIES-Prüfung (gemockt in Tests), Steuerfunktion aus Abschnitt 6 mit Tests, Purge-Test, VVT-Nachtrag | R0 gemergt, Weiche W61-3 |
| **R2** | Rechnung im Webhook-Pfad (Abschnitt 3), Tabelle mit `UNIQUE (payment_id)` (Abschnitt 4), PDF-Archiv (Abschnitt 7), Worker-Routine `invoice-retry`, Schalter (Abschnitt 5), Tests mit gemockter Mollie-API (Erfolg, 422, Timeout, Doppel-Webhook), `e2e-billing-cloud` erweitert, Betreiber-Ablauf Storno, Verfahrensdokumentation §4/§5 | R1 gemergt, Weichen W61-1 und W61-2 |

Migrationsnummern: reserviert ist 0109 (PM), geprüft wird beim Anlegen gegen
`origin/main`; ist die Nummer belegt, nimmt das Paket die nächste freie und
nennt sie im PR.

## 11. Weichen (offen, mit Empfehlung)

### W61-1 Wo liegt das PDF-Archiv?

| Option | Vorteil | Nachteil |
| --- | --- | --- |
| **A** eigener Präfix `invoices/…` im vorhandenen BlobStore (SeaweedFS/S3), Katalog und Hash in Postgres | keine neue Infrastruktur; der BlobStore ist schon im nächtlichen Backup (`s3 sync` plus restic, `deploy/hetzner/scripts/backup.sh`); Datenbank-Dumps bleiben klein | das Backup hält nur 6 Monate Historie (`keep-monthly 6`); das Archiv selbst ist der Bucket, ein versehentliches Löschen dort wäre nach 6 Monaten endgültig |
| **B** PDF als `bytea` in Postgres | transaktional mit der Rechnungszeile, keine zweite Quelle, im verschlüsselten Dump enthalten | etwa 170 KB je PDF (Test P3d): bei 100 Kunden rund 200 MB im Jahr, 2 GB in 10 Jahren in jedem Dump |
| **C** zusätzlich zu A eine Ablage außerhalb von Who2Be (Export in die Buchhaltung oder ein Speicher mit Schreibschutz) | unabhängig vom App-Stack; Schreibschutz deckt die GoBD-Forderung am besten ab | eigener Betreiber-Ablauf; ohne Buchhaltungssoftware zum Start ein Handgriff im Monat |

**Empfehlung: A**, und C als Betreiber-Ablauf, sobald eine Buchhaltung
angebunden ist. A nutzt, was schon läuft und gesichert wird, und der Hash in
der Archivzeile belegt die Unverändertheit. Die Lücke in der Backup-Historie
ist bei A und B gleich und spricht eher für C als gegen A.

### W61-2 Preisbasis brutto: was zahlt ein Kunde ohne deutsche USt?

Gilt nur bei `WHO2BE_INVOICE_PRICE_BASIS=gross`. Betroffen sind EU-B2B mit
Reverse Charge und Drittland.

| Option | Vorteil | Nachteil |
| --- | --- | --- |
| **A** denselben Plan-Preis, als Nettobetrag mit 0 % | ein Betrag für alle, das Abo ändert sich nie mit dem Steuerfall | Geschäftskunden aus der EU zahlen netto so viel wie deutsche Kunden brutto, also mehr |
| **B** den Nettoanteil (Plan-Preis / 1,19) | gleicher Nettoerlös je Kunde, fair für Geschäftskunden | krumme Beträge, der Abo-Betrag hängt wieder vom Steuerfall ab |

**Empfehlung: A**, weil die Preisbasis brutto gerade wegen des einen festen
Betrags gewählt würde. Preisfrage, mit dem Steuerberater abzustimmen.

### W61-3 EU-B2B mit ungeprüfter USt-IdNr.

VIES fällt öfter aus; R1 speichert die Nummer dann als „ungeprüft“ und lässt
den Checkout weiterlaufen. Welche Rechnung entsteht für so eine Zahlung?

| Option | Vorteil | Nachteil |
| --- | --- | --- |
| **A** Rechnung zurückhalten, bis eine Nachprüfung (Worker) gelingt, dann nach Ergebnis ausstellen | jede Rechnung beruht auf einem geprüften Stand | die Rechnung kommt Stunden bis Tage nach der Zahlung |
| **B** sofort mit 19 % ausstellen wie B2C | Rechnung sofort, keine Steuer zu wenig | falsch, wenn die Nummer gültig ist; über die API nicht korrigierbar (Abschnitt 8) |
| **C** sofort mit Reverse Charge ausstellen | Rechnung sofort | falsch, wenn die Nummer ungültig ist; dann fehlt die Steuer |

**Empfehlung: A** mit einer Obergrenze (etwa 72 Stunden), danach B und ein
Hinweis an den Betreiber. A passt zum fail-closed-Ablauf aus Abschnitt 3 und
vermeidet Rechnungen, die sich nicht stornieren lassen.

## 12. Verworfene Optionen

Aus dem Bericht §3 bis §5:

- **A2 Mollie + Lexware Office XL:** deutscher Anbieter mit fertigen
  Steuerarten für Reverse Charge und §13b, ZUGFeRD/XRechnung und GoBD-Archiv.
  Kostet aber 32,90 € im Monat netto, die API gibt es erst ab XL, der Umbau ist
  größer (Kontaktabgleich, OAuth, Rate-Limit 2/s, eigener Retry-Pfad, Umbau M
  statt S–M). Bleibt der fertige Plan B ohne Änderung an der Zahlungsseite,
  falls Mollie Invoicing später nicht trägt.
- **Merchant of Record (Paddle, Creem, Stripe Managed Payments, Polar u. a.):**
  nimmt Who2Be die Steuer ab, kostet aber etwa das 2- bis 6-Fache der
  Mollie-Gebühren (bei 100 Kunden rund 200 bis 220 € statt 35 bis 125 € im
  Monat), verlangt einen Neubau von Checkout, Abo-Lebenszyklus und allen
  Billing-Tests (Umbau L) und sitzt meist außerhalb der EU (Paddle UK, Stripe
  MP über Link LLC USA). Creem als einziger EU-MoR hat keine USt-IdNr.-Eingabe
  für B2B. Wieder prüfen, sobald nennenswert Kunden außerhalb der EU kaufen.
- **Stripe Billing + Tax:** kompletter Wechsel des Zahlungsanbieters (Umbau L),
  ohne Vorteil bei der E-Rechnung, die dort nur über Apps von Drittanbietern
  geht.
- **Eigene Rechnungserzeugung in Who2Be (PDF selbst rendern):** Nummernkreis,
  Pflichtangaben und Layout wären eigene Pflege und eigene Haftung, ohne
  Vorteil gegenüber der kostenlosen Mollie-Funktion.

## 13. Konsequenzen

**Positiv.**

- Rechnungen nach §14 UStG ohne neuen Anbieter und ohne Fixkosten, auf der
  Mollie-API, die Who2Be schon nutzt.
- Steuermodus und Preisbasis sind Schalter: die Antwort des Steuerberaters
  wird ein Deploy, kein Umbau.
- Eine Rechnung je Zahlung ist durch die Datenbank gesichert, nicht durch
  Hoffnung auf Mollie.
- Ohne Steuermodus entsteht keine Rechnung mit geratener Steuer.

**Negativ / Aufwand.**

- Storno und Erstattung bleiben Handarbeit des Betreibers, bis Mollie
  Gutschriften per API anbietet.
- Who2Be überwacht die OSS-Schwelle nicht.
- Bei Preisbasis netto hängt der Abo-Betrag am Steuerfall; ändern sich die
  Rechnungsdaten, muss das Abo nachziehen.
- Die Verfahrensdokumentation (§5 „Who2Be stellt keine eigenen Rechnungen
  aus“) wird mit R2 falsch und muss dort ersetzt werden.
- E-Rechnung bleibt außen vor. Eine Monatsrechnung liegt beim heutigen
  Preis weit unter der Kleinbetragsgrenze von 250 € brutto (§33 UStDV), eine
  Pflicht entsteht deshalb auch ab 2027/2028 nicht (Bericht, Kurzfassung;
  mit Steuerberater zu bestätigen). Mollie bietet Peppol ohne Aufpreis an,
  falls größere Geschäftskunden danach fragen.

**Offen beim Betreiber** (nicht durch Code entscheidbar):

- Steuermodus und Preisbasis mit dem Steuerberater festlegen.
- Texte der `memo`-Vermerke bestätigen lassen (Abschnitt 6).
- Im Mollie-Profil: Absenderangaben und eigene USt-IdNr. prüfen, Jahr ins
  Präfix des Nummernkreises.
- Bei Mollie schriftlich fragen: getrennte Nummernkreise für Test und Live?
  Gutschriften per API geplant? Prüft Mollie die USt-IdNr. im Live-Modus?

**Ausbaupfad.**

- OSS, sobald das Konto registriert ist: `vatScheme=one-stop-shop`, Satz des
  Ziellands, neue Zeile in der Tabelle aus Abschnitt 6.
- Erstattungen erkennen: Ping zu einer schon beanspruchten Zahlung mit
  `amountRefunded > 0` oder Rückbuchung als Hinweis an den Betreiber, statt
  ihn zu verwerfen.
- Sales-Invoice-Webhooks von Mollie (`sales-invoice.paid` u. a.) als
  Gegenprobe, falls der synchrone Pfad nicht reicht.

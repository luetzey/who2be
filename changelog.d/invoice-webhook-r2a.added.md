- Rechnung je bezahlter Zahlung (Cloud, ADR-0061 Paket R2a). Zu jeder
  bezahlten Erst- und Folgezahlung stellt der Mollie-Webhook über Mollie
  Invoicing eine Rechnung aus: Empfänger aus den Rechnungsdaten der
  Organisation, Steuer aus der Steuerfunktion aus R1, Leistungszeitraum in der
  Positionszeile. Das PDF wird unverändert mit SHA-256-Prüfsumme im BlobStore
  unter `invoices/<org>/<jahr>/<nummer>.pdf` archiviert.

  Neue Tabelle `billing_invoice` (Migration `billing_0111`) mit genau einer
  Zeile je Zahlung (`UNIQUE (payment_id)`), die vor dem Aufruf bei Mollie
  angelegt wird. Ein doppelter Webhook ergibt so keine zweite Rechnung.
  Mollie-ID, Nummer, Ablageort und Prüfsumme sind nach dem ersten Setzen per
  Trigger unveränderlich; Steuerangaben (Schalterwerte, Satz, Memo), Betrag,
  Leistungszeitraum, Plan, Kunde und Ausstellungszeit ab Status `issued`. Die
  Zeile überlebt den Org-Purge (Aufbewahrung). Neue Einstellungen
  `WHO2BE_INVOICE_TAX_MODE` (`regular` oder `small_business`, bewusst ohne
  Default: leer heißt, es wird keine Rechnung ausgestellt) und
  `WHO2BE_INVOICE_PRICE_BASIS` (`net`, Default, oder `gross`). Fehlen Daten
  (Rechnungsdaten, E-Mail, ungeprüfte USt-IdNr., abweichender Betrag), bleibt
  die Rechnung vorgemerkt, statt mit geratenen Angaben ausgestellt zu werden.
  Das Entitlement hängt nie an der Rechnung. Die Durchreichung der Schalter in
  den Compose-Stacks und `.env.example` folgt mit Paket R2d, der Worker-Retry
  mit R2b.

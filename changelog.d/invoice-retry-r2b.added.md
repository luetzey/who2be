- Worker-Routine `invoice-retry` (Cloud, ADR-0061 Paket R2b). Der
  Mollie-Webhook merkt eine Rechnung jetzt nur noch vor; ausgestellt und
  archiviert wird ausschließlich im Worker, alle 5 Minuten, höchstens 25
  Rechnungen je Lauf. Technische Fehler werden mit Backoff wiederholt (5 min,
  verdoppelt, höchstens 6 h). Nach 8 Fehlversuchen steht die Rechnung auf
  `failed` und der Worker schreibt eine ERROR-Zeile für den Betreiber. Eine
  ausgestellte Rechnung, deren PDF-Archiv fehlt, wird nie `failed`.
  Zurückgehaltene Rechnungen zählen keinen Versuch und werden stündlich neu
  geprüft.

  Endete ein POST ohne klare Antwort, sucht der nächste Lauf die Rechnung zuerst
  über die Mollie List-API (`paymentDetails.sourceReference`). Wird sie gefunden,
  übernimmt der Worker Nummer und Steuerangaben ohne neuen POST. Bleibt die Suche
  unklar, wird nichts gePOSTet. Eine ungeprüfte USt-IdNr. prüft der Worker bei
  VIES nach und schreibt das Ergebnis in die Rechnungsdaten zurück. Antwortet
  VIES 72 Stunden nach dem Vormerken weiterhin nicht, wird die Rechnung mit 19 %
  ausgestellt (W61-3, Option B), zusammen mit einer WARN-Zeile für den Betreiber.
  On-Prem und ohne installiertes Billing-Paket ist die Routine ein No-Op. Die
  Durchreichung der Mollie- und Rechnungs-Variablen an den `worker`-Dienst folgt
  mit Paket R2d; bis dahin bleiben vorgemerkte Rechnungen offen.

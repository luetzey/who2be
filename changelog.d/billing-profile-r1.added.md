- Rechnungsdaten je Organisation (Cloud, ADR-0061 Paket R1). Admins erfassen
  in den Org-Einstellungen Kundentyp (Firma oder Privat), Name bzw. Firmenname,
  Rechnungsadresse, Land und für Firmen in der EU optional die USt-IdNr.

  Die USt-IdNr. prüft der Server bei VIES. Antwortet VIES nicht oder nicht
  rechtzeitig, wird sie als „ungeprüft“ gespeichert, das Speichern scheitert
  daran nicht. Neue Endpunkte `GET`/`PUT /v1/workspaces/{ws}/billing/profile`
  (admin, nur Cloud), neue Tabelle `billing_profile` (Migration
  `billing_0109`), die mit der Organisation gelöscht wird. Der Upgrade-Knopf
  bleibt gesperrt, bis Rechnungsdaten gespeichert sind. Die Steuerfunktion für
  die Rechnungsstellung liegt als reine Funktion bereit; verdrahtet wird sie
  mit R2.

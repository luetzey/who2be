- Cloud: Im Billing-Bereich der Organisations-Einstellungen sehen Admins jetzt
  ihre Rechnungen mit Nummer, Datum, Betrag und Status und laden das PDF aus
  dem eigenen Archiv herunter (ADR-0061, Paket R3).

  Neu sind `GET /v1/workspaces/{ws}/billing/invoices` und
  `GET /v1/workspaces/{ws}/billing/invoices/{invoice_id}/pdf`, beide nur für
  Admins und nur in der Cloud-Edition. Gelistet werden nur ausgestellte
  Rechnungen der eigenen Organisation. Eine fremde, unbekannte oder noch nicht
  archivierte Rechnung ergibt 404. Das PDF wird nur ausgeliefert, wenn sein
  SHA-256 noch zur Archivzeile passt.

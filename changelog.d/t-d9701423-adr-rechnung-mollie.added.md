- ADR-0061 (Accepted) legt fest, wie Who2Be in der Cloud-Edition Rechnungen
  ausstellt: über Mollie Invoicing (Sales Invoices API), eine bezahlte Rechnung
  je bezahlter Mollie-Zahlung, abgesichert durch eine eigene Zeile je
  `payment_id`, weil Mollie Duplikate nicht verhindert.

  Steuermodus (Regelbesteuerung oder Kleinunternehmer) und Preisbasis (netto
  oder brutto) werden Schalter, die Steuerlogik eine Tabelle; ohne gesetzten
  Steuermodus entsteht keine Rechnung. Die PDFs archiviert Who2Be selbst für
  mindestens 10 Jahre. Storno und Erstattung bleiben vorerst ein manueller
  Beleg des Betreibers. Es ändert sich noch kein Verhalten.

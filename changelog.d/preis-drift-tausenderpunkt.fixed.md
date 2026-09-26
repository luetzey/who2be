- Der Preis-Drift-Wächter liest deutsche Tausenderpunkte nicht mehr als
  Dezimalpunkt.

  `_eur()` in `packages/billing/tests/test_doc_price_drift.py` behandelte einen
  Punkt ohne Komma als Dezimaltrenner. Damit kollabierten genau die
  Tausenderbeträge, deren Punktform auf einen erlaubten Preis fällt: „9.990 €"
  wurde zum Pro-Preis 9,99 €, „99.000 €" zum Team-Vorschlag 99 € — beide liefen
  still grün durch, obwohl ein vierstelliger Jahresbetrag in der Tarif-Doku
  auffallen müsste. Vorbestehend, nicht durch die Prosaform-Erweiterung
  eingeführt; die hat den Defekt nur sichtbar gemacht, weil der Scan seither
  *jeden* Euro-Betrag in den preistragenden Dateien beansprucht und
  Tausenderbeträge in Prosa (Jahreslizenzen, Pauschalen) dort plausibel sind.

  Entschieden wird jetzt an der Stelligkeit: genau drei Ziffern hinter jedem
  Punkt und höchstens drei davor ist Tausendertrennung („9.990" → 9990), alles
  andere ein Dezimalpunkt („9.99" → 9,99, die Mollie-Notation aus `plans.py` und
  die JS-Zahl in `BillingPanel.tsx`). Ein Komma bleibt eindeutig der
  Dezimaltrenner. Die verbleibende Zweideutigkeit — „1.234" ohne Komma wird als
  Tausender gelesen, nicht als Betrag mit drei Nachkommastellen — ist im Code
  benannt und fällt auf die sichere Seite: die größere Zahl fällt eher aus der
  Liste der erlaubten Preise und macht den Wächter rot statt stumm.

  Dazu ein Tabellentest direkt auf `_eur()`: die Funktion trug die gesamte
  Betragslogik des Wächters, wurde aber nur indirekt über die Doku-Dateien
  geprüft — eine Fehl-Lesart blieb still, solange keine Doku-Zeile sie auslöste.

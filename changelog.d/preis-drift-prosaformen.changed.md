- Der Preis-Drift-Wächter erfasst auch die Prosaformen des Preises.

  Das Scan-Muster in `packages/billing/tests/test_doc_price_drift.py` traf
  zuvor nur die Kurzform „9,99 €/Monat" und ließ jede ausgeschriebene Variante
  durch — „49 € im Monat", „49 EUR pro Monat", „49 € monatlich" und die reine
  Prosa „zahlt heute 49 €". Zwei solcher Sätze stehen real im Analysepapier
  `docs/cloud-hosting-owner-guide.md` und hingen bis jetzt an keiner Prüfung;
  dass sie heute stimmen, war Handarbeit — genau die, die der Wächter ersetzen
  soll.

  Der Scan prüft deshalb nicht mehr die Formulierung, sondern den Betrag:
  *jeder* Euro-Betrag in den preistragenden Dateien muss ein bekannter Betrag
  sein. Eine Liste erlaubter Formulierungen wäre immer unvollständig geblieben,
  die Menge der erlaubten Beträge dagegen ist endlich und hängt an `plans.py`.
  Die bestehenden Prosa-Sätze sind damit erfasst statt freigestellt — Drift
  genau dort ist ab jetzt rot.

- Der Pro-Tarif kostet 9,99 € pro Monat (Owner-Entscheidung); zuvor stand an
  mehreren Stellen 29 €.

  Führende Quelle ist `PRO_PLAN.price_eur` in
  `packages/billing/src/who2be_billing/plans.py` — Mollie-Syntax und Intervall
  (`1 month`) bleiben unverändert. Nachgezogen sind die Tarif-Tabelle in
  `docs/licensing/plans.md`, das Analysepapier
  `docs/cloud-hosting-owner-guide.md` und die `TIERS`-Stammdaten des
  Billing-Panels, das den Preis dupliziert, weil das Backend ihn nicht
  mitliefert. Die Preisanzeige formatiert den Betrag jetzt über den
  i18next-`number`-Formatter, sonst stünde im deutschen Locale ein
  Dezimalpunkt.

- Ein Drift-Wächter hält die Preisangaben in Doku und Frontend an `plans.py`.

  `packages/billing/tests/test_doc_price_drift.py` prüft zweierlei: bekannte
  Stellen nennen exakt `PRO_PLAN.price_eur` (und melden, wenn ihr Muster nicht
  mehr trifft, statt still durchzulaufen), und *jeder* Euro-Betrag in den
  preistragenden Dateien muss ein bekannter Betrag sein — eine neue Fundstelle
  mit fremder Zahl ist damit ein roter Test, kein stiller Fund.

- Die Pro-Tarifzeile nennt nur noch `core` als Feature.

  `composite_playbooks`, `agents` und `audit_export` werden nirgends im Repo
  per `has_feature()` geprüft; die eigene Dokumentation nennt sie deshalb „kein
  Leistungsversprechen". Sie bleiben Teil des Datenmodells und der
  Mollie-Metadata, gehören aber nicht in eine Tarifdarstellung — auch das
  sichert der Wächter ab.

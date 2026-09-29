- Prüffälle und Prüfläufe sind jetzt in Auskunft und Löschung eingebunden
  (ADR-0053, Paket B1c): Der DSGVO-Export enthält je Workspace die Blöcke
  `test_cases` und `test_runs`. Beim Löschen eines Kontos setzt der Purge
  `test_case.created_by` (nur bei von Menschen angelegten Prüffällen) und
  `test_run.reported_by_user_id` auf die anonyme Kennung; beim Löschen einer
  Organisation fallen beide Tabellen per Kaskade mit. VVT (V21) und
  Löschkonzept (§4b) beschreiben die neue Verarbeitung.

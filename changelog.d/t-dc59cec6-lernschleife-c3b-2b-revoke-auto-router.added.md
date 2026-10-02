- Gedaechtnis: REST-Endpunkt `POST /memories/revoke-auto` fuer den Not-Aus
  automatisch aktivierter Eintraege (ADR-0053 6.4.1, Paket C3b-2b). Mit
  `dry_run=true` antwortet er mit der Vorschau `{count, sample, hidden_count}`
  und aendert nichts. Ohne `dry_run` ist `expected_count` Pflicht. Die Antwort
  `{count, hidden_count, results}` enthaelt ein Ergebnis je Eintrag; weicht die
  Zahl ab, kommt 409 `memory_batch_count_mismatch` (`params={count}`).

  Der Aufruf verlangt die Rolle `editor`, `viewer` bekommt 403.
  `include_other_users` steht nur `admin` offen. Fremdes Nutzergedaechtnis
  erscheint dabei nur als Zahl (`hidden_count`), nie mit Inhalt oder ID.

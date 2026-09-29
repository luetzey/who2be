- Die semantische Suche erkennt eine fehlende Vektor-Spalte jetzt zuverlaessig,
  auch wenn in derselben Datenbank ein weiteres Schema mit gleichnamiger
  Tabelle liegt.

  Die Probe `vector_supported` in `content_chunk_repository` und
  `memory_repository` las `information_schema.columns`. Dieser Katalog ignoriert
  den `search_path` und findet jede gleichnamige Tabelle in jedem Schema. Lag
  irgendwo eine zweite `content_chunk`- oder `agent_memory`-Tabelle mit
  `content_vector`, meldete die Probe die Spalte als vorhanden, obwohl die
  tatsaechlich genutzte Tabelle sie nicht hatte. Jeder Vektor-Zugriff scheiterte
  dann mit `UndefinedColumnError`, statt in den Volltext-Modus zu fallen. Die
  Probe liest jetzt `pg_attribute` ueber `to_regclass`, nach dem Muster von
  Migration 0021.

  Die Tests `test_works_without_the_vector_column` (Memory und Content-Suche)
  entfernen die Spalte nicht mehr im geteilten `public`-Schema, sondern in einem
  eigenen, frisch migrierten Wegwerf-Schema. Dafuer gibt es den neuen Helper
  `who2be_api.testing.isolated_schema`. Ein abgebrochener Lauf hinterlaesst
  keine Dev-DB ohne `content_vector` mehr. `CONTRIBUTING.md` beschreibt, wie man
  eine bereits betroffene lokale DB repariert.

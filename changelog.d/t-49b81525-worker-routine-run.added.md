- Worker: Laufprotokoll der Hintergrund-Routinen (ADR-0057, Paket P1a).
  Migration 0102 legt `routine_run` (eine Zeile je Lauf, genau ein Lauf je
  Routine und Slot über `UNIQUE (routine, slot)`) und `worker_heartbeat` an.
  Beide Tabellen tragen keine Mandantendaten; die Laufzeitrolle `who2be_app`
  darf sie nur lesen. Das Ergebnis eines Laufs enthält nur Zähler, ein Fehler
  nur den Namen der Exception-Klasse.

  Neu ist das Modul `who2be_api.worker.store` mit Slot-Claim, Lauf-Abschluss,
  Lauf- und Worker-Heartbeat, dem Markieren abgebrochener Läufe
  (`Abandoned` nach 5 min ohne Heartbeat) und dem Advisory-Lock je Routine auf
  einer eigenen Verbindung. Der Org-Export führt beide Tabellen als
  instanzweit und nimmt sie nicht ins Archiv. Runner, Zeitpläne und der Dienst
  `worker` folgen in den nächsten Paketen; an laufenden Installationen ändert
  sich bis dahin nichts.

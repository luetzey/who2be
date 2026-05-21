# ADR-0004 — Versionierung ueber separate History-Tabellen

- Status: Akzeptiert
- Datum: 2026-05-21
- Kontext: Who2Be MVP (PROJ-19)

## Kontext

Persona und Playbook werden bei jedem Update versioniert; alte Staende muessen
abrufbar bleiben. Zu entscheiden ist das Speicher-Modell.

## Optionen

- **A — Separate History-Tabelle:** Aktueller Stand in `persona`/`playbook`;
  jeder Update schreibt einen unveraenderlichen Snapshot in
  `persona_version`/`playbook_version`. CRUD bleibt einfach, Historie klar.
- **B — Append-only mit Versions-Spalte:** Jede Version eine Zeile in einer
  Tabelle, "aktuell" ueber `is_current`-Flag/hoechste Versionsnummer. Eine
  Tabelle, aber jede CRUD-Query muss filtern.
- **C — Audit-/Event-Log:** Generische Aenderungs-Log-Tabelle mit JSONB-Diffs.
  Sehr flexibel, aber Rekonstruktion einer konkreten Version teuer und komplex.

## Entscheidung

Option A (Anwender-Entscheidung). `persona`/`playbook` tragen Identitaet,
`current_version` und denormalisierte filterbare Felder; `persona_version`/
`playbook_version` halten je Update einen unveraenderlichen `jsonb`-Snapshot.
Der Update ist transaktional: Version inkrementieren, Snapshot einfuegen,
denormalisierte Felder aktualisieren.

## Konsequenzen

- Lesen des aktuellen Stands und Listen-Filter sind einfache Queries ohne Join.
- Versionshistorie ist unveraenderlich und direkt abfragbar.
- Inhalt wird je Version vollstaendig dupliziert (kein Diff) — fuer die
  erwartete MVP-Datenmenge unkritisch.
- Die `persona_playbook`-Verknuepfung wird im MVP **nicht** unabhaengig
  versioniert (KISS); falls noetig, kann die Playbook-Liste spaeter Teil des
  Persona-Snapshots werden.

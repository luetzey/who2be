- Gedächtnis: Secret-Scan, Ratenbegrenzung und Verfall (ADR-0053, Paket C2b).
  `save_memory` weist Inhalte, die nach Zugangsdaten oder Geheimnissen
  aussehen, mit `memory_guard_rejected` ab — zusätzlich zum Injection-Wächter
  und unabhängig von dessen Einstellung (auch bei `off`). Der Scan ist ein
  Vorfilter für Versehen, keine Garantie. `save_memory` zählt wie bisher gegen
  das Schreib-Ratenlimit des Agenten (`write_rate_limit`, `write_rate_limited`)
  und gegen das globale Schreiblimit; ein Test hält beides jetzt fest.

  **Verhaltensänderung:** Unbestätigte Einträge verfallen nach 30 Tagen
  (gesetzte Annahme). Das gilt jetzt auch für Vorschläge (`pending`), nicht
  nur für automatisch aktivierte Einträge; neue Vorschläge tragen deshalb ein
  `expires_at`. Lernvorschläge (`kind=lesson`) verfallen nie. Abrufe
  verlängern nichts. Eine Freigabe in der Triage gilt als menschliche
  Bestätigung: sie setzt `confirmed_at`/`confirmed_by` und hebt den Verfall
  auf (`expires_at = null`).

  Neuer Befehl `who2be-memory-expire` (Owner-Verbindung, wie
  `who2be-purge`): setzt fällige unbestätigte Einträge auf `expired` und
  schreibt je Eintrag das Ereignis `expired`. Gelöscht wird nichts —
  abgelaufene Einträge zählen weiter für die Dublettenprüfung. Betrieb: einmal
  täglich per Host-Cron gegen den Produktions-Stack; Cron-Zeile je Edition,
  Einrichtung und Verifikation stehen im Hetzner-Runbook
  (`deploy/hetzner/RUNBOOK.md`, Abschnitt „Verfall unbestaetigten
  Gedaechtnisses“).

- Statusfolgen der Lernschleife (ADR-0053, Paket E3): Wird eine mit einer
  Maßnahme verknüpfte Version durch einen Menschen aktiv, erhält die Maßnahme
  in derselben Transaktion das Ereignis `activated`, und ihre Fälle gehen auf
  `addressed` (Akteur System, mit Version und Maßnahme). Fälle in
  `addressed`, `verified` oder `dismissed` bleiben unverändert. Die Einstufung
  der Nachschau setzt die Fälle bei `effective` von `addressed` auf
  `verified` und bei `ineffective` auf `reopened`, mit der Begründung der
  Einstufung; `not_measurable` ändert keinen Fallstatus.
- Fallstatus `in_progress` lässt sich jetzt von Hand setzen, aber nur mit der
  `measure_id` einer Maßnahme, die den Fall enthält. `verified` von Hand
  bleibt gesperrt (409, `params.requires = "review"`) — es folgt nur aus der
  Einstufung. Die bisherige Sperre `params.requires = "phase_e"` entfällt.

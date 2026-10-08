- Service-Schicht für zwei Wege zum Fall (ADR-0053, Paket D2c-1): ein offener
  Lernvorschlag (`lesson`, `pending`) wird in einen Fall umgewandelt
  (`convert`), ein offenes Alt-Feedback wird in einen Fall übernommen
  (`promote`). Beides läuft in einer Transaktion. Bei `convert` wird der
  Eintrag `converted` mit Verweis auf den Fall und bekommt das Ereignis
  `converted` in seiner Historie. Bei `promote` bekommt das Alt-Feedback
  `addressed` mit dem Verweis `case:<id>`. Beides dürfen nur Menschen ab der
  Rolle `editor`, Agent-Tokens nie. Neue Fehlergründe
  `memory_not_convertible` und `feedback_not_promotable` (409). Die
  HTTP-Routen folgen mit D2c-2.

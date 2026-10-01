- ADR-0055 (Accepted) dokumentiert das Trennungskonzept für die
  Mandantentrennung. Nach der Owner-Entscheidung vom 2026-09-30 bekommt nicht
  jede Organisation eine eigene Datenbank. Die gemeinsame Datenbank mit Row
  Level Security (ADR-0019) bleibt und wird gehärtet.

  Die ADR beschreibt das Trennmodell (Mandantenschlüssel, Mandanten-GUCs,
  Rollen, Blob- und SQLite-Speicher je Workspace), weist die Restrisiken
  gesondert aus und nennt die Tests, die die Trennung belegen. Die verworfene
  Option ist mit Normzitaten begründet (DSGVO, OH Mandantenfähigkeit, SDM,
  BSI C5 OPS-24). Wie die Policies der Auflösungspfade strikt werden, bleibt als
  offene Weiche mit drei Optionen stehen. Es ändert sich noch kein Verhalten.

- Worker: Die Daten-Schicht für die Betreiber-Sicht auf die Hintergrund-Routinen
  steht (ADR-0057, Paket P4b). Je Routine liefert sie den wirksamen Zeitplan,
  an/aus, ob ein `WHO2BE_ROUTINE_*`-Override greift, den letzten Lauf (Status,
  Auslöser, Dauer, Zähler, Fehlerklasse), den nächsten Termin, den letzten
  Erfolg und den Hinweis auf einen noch laufenden externen Zeitplan, dazu
  „Worker zuletzt gesehen“. Gelesen wird über die App-Rolle mit reinem
  Leserecht. Eine Route gibt es noch nicht (Paket P4c).

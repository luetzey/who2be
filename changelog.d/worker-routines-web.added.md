- Web: In den Konto-Einstellungen gibt es den nur lesenden Abschnitt
  „Hintergrund-Routinen“ (ADR-0057 §7, Paket P5). Er zeigt je Routine Zeitplan,
  an/aus, Quelle, letzten Lauf (Status, Dauer, Zähler, Fehlerklasse), nächsten
  Termin und letzten Erfolg, dazu „Worker zuletzt gesehen“ und den Hinweis auf
  einen noch laufenden externen Zeitplan. Zeiten stehen in Ortszeit mit UTC.
  Sichtbar ist er nur für Betreiber (`WHO2BE_OPERATORS`); alle anderen bekommen
  von `GET /v1/system/routines` eine 403 und sehen weder Abschnitt noch
  Navigationseintrag noch Fehlermeldung.

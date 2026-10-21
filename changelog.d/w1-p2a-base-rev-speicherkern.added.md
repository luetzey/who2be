- Grundlage für Teiländerungen nach ADR-0058 §6.2/§6.3 (W1-P2a), noch ohne
  neue Route und ohne sichtbares Verhalten. Der Speicherkern kennt jetzt den
  Konflikt-Token `base_rev`: die ersten 16 Hex-Zeichen eines SHA-256 über die
  kanonische JSON-Form von Inhalt, Name und Sprache der Version, auf die
  geschrieben würde. Ist ein erwarteter Wert gesetzt, prüfen die Schreibpfade
  ihn in derselben Transaktion unter der Zeilensperre und lehnen einen
  veralteten Stand ab, bevor sie schreiben. Ohne gesetzten Wert bleibt jeder
  Schreibpfad unverändert. Der erwartete Wert wird nur über einen
  Kontextmanager gesetzt, der ihn auch nach einem Fehler zurücksetzt.

  Der System-Prompt hat dazu einen Draft-Pfad wie die übrigen Elementarten:
  ein offener Draft wird in place aktualisiert, sonst entsteht ein neuer
  Draft. Steht die aktuelle Version in Review, antwortet der Pfad mit 409
  `review_conflict`.

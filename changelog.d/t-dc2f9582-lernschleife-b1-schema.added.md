- Das Datenmodell für Prüffälle und Prüfläufe steht (ADR-0053, Paket B1):
  Migration 0089 legt `test_case` und `test_run` an, dazu die Modelle in
  `who2be_models.test_case` und ein Repository. Ein Prüffall hängt immer an
  einem Agenten und optional an einem Element; sein Inhalt ist
  unveränderlich, nur der Status lässt sich ändern. Prüfläufe sind
  append-only.

  Die Datenbank sichert die Regeln selbst ab: `verdict='pass'` nur bei
  `runs_passed = runs_total`, mindestens ein Lauf, `human_rating` nur mit
  meldendem Menschen, alle Verweise im selben Workspace, strikte
  Workspace-Trennung per RLS. Es gibt noch keinen Endpunkt und kein
  MCP-Werkzeug; beides folgt in B2 und B3.

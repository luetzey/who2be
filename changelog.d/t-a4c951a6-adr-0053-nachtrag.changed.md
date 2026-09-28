- ADR-0053 ist jetzt vollständig Accepted: Die letzte offene Weiche P4 ist
  entschieden (Option (a)). Für eine Elementversion gelten die direkt
  gebundenen Prüffälle plus alle aktiven Prüffälle jedes Agenten, der das
  Element heute erreicht.

  Dazu drei Präzisierungen der Phase-B-Verträge: `verdict='pass'` nur bei
  `runs_passed = runs_total`, sonst 422 `test_run_verdict_inconsistent`;
  `test_run.attestation` kennt `client_self_report` und `human_rating`
  (Bewertung von `human_rule`-Prüffällen durch einen Menschen in der
  Web-Oberfläche); `override_reason` bleibt 1–1 000 Zeichen ohne
  10-Zeichen-Mindestlänge. Es ändert sich noch kein Verhalten.

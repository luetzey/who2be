- ADR-0054 (Accepted) hält die Owner-Entscheidung zum Orchestrator-Agenten
  fest: ein Delegationsobjekt als A2A-Task-Vorlage (Ziel, Format, Grenzen,
  Abnahme), ein deklaratives Feld `run_limits` am Agenten, ein Export als
  A2A-Agent-Card und als AGENTS.md sowie eine neue Prüffall-Art `tool_trace`.
  Der Einzelagent mit Playbooks bleibt der Standard, der Orchestrator wird nur
  als Vorlage angeboten.

  Who2Be deklariert Delegation und Grenzen und prüft sie nach, setzt sie aber
  nicht durch. Der Abgleich von A2A-`skills` mit Playbooks ist noch offen. Die
  Umsetzung beginnt erst nach dem Cloud-Test. Es ändert sich noch kein
  Verhalten.

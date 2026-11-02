- Builder lädt Playbooks sparsamer (Builder schlank B6, `BUILDER_CONTENT_VERSION`
  22 → 23, DE und EN). Das Builder-Profil sagt jetzt: Playbooks über der
  Warnschwelle erst mit `format="outline"` holen, dann nur die nötigen Abschnitte;
  schon geladene Konventions-Abschnitte nicht erneut holen. Die Fall-Triage hat
  einen Wegweiser, der nur den gegangenen Weg (A, B oder C) laden lässt. Das
  Agent-Playbook erklärt bei der `tool_policy` nur noch die Felder; Muster,
  Empfehlung und Eskalationsgrenzen stehen allein in den Konventionen. Das
  Persona-Playbook lädt den Sprach-Abschnitt der Konventionen mit. Bestehende
  Workspaces erhalten den Stand beim nächsten Start automatisch.

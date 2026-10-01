- Freigabematrix für das Gedächtnis (ADR-0053, Paket C2a). Was ein Agent
  über `save_memory` ohne menschliche Freigabe aktiv setzen darf, entscheidet
  jetzt eine Workspace-Einstellung „Art x Herkunft“
  (`GET/PUT /v1/workspaces/{id}/memory-auto-policy`, nur `admin` und nur im
  eingeloggten Web-Login, nicht per API-Token). Schaltbar ist genau eine Zelle:
  Nutzerfakt ohne Verhaltenswirkung, den der Nutzer selbst gesagt hat
  (`user_fact` x `user_stated`). Alle anderen Zellen bleiben immer in der
  Freigabe; eine entsprechende Einstellung ignoriert der Server. Jedes Ein- und
  Ausschalten steht im Audit-Log (`memory.auto_policy.enabled`/`.disabled`).
  Automatisch aktivierte Einträge sind unbestätigt und verfallen nach 30 Tagen
  (`expires_at`); die Antwort trägt `auto_activated`.

  **Verhaltensänderung:** Die Matrix ist zunächst ganz ausgeschaltet. Agenten
  mit `memory_mode=auto` speichern deshalb ab sofort wie `suggest` als
  Vorschlag (`pending`), bis ein Admin die Zelle einschaltet.

  `save_memory` verlangt jetzt die Herkunft `origin` (`user_stated`,
  `inferred`, `external_content`; sonst `memory_origin_required`) und kennt Art
  (`kind`) und Geltungsbereich (`scope`); eine unpassende Kombination ergibt
  `memory_kind_scope_invalid`. Den Kanal setzt der Server. Wiederholt ein Agent
  einen Lernvorschlag, entsteht kein neuer Eintrag: die Antwort ist 200 mit
  `merged_into`, der Treffer zählt hoch und behält seinen Status. Neue
  Obergrenzen: höchstens 200 Arbeitsnotizen je Agent
  (`memory_note_cap_reached`, zählen nicht gegen die 500 der Agentengrenze)
  und höchstens 500 Einträge im Nutzergedächtnis je Workspace und Nutzer
  (`memory_cap_reached` mit `scope: "user"`). Migration 0095 legt die Spalte
  `workspace.memory_auto_policy` an.

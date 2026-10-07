- Das Datenmodell für Fälle steht (ADR-0053, Paket D1a). Migration 0100 legt
  `agent_case` an, dazu den Verlauf `agent_case_event`, die Zuordnung zu
  Bausteinen `agent_case_element` und die Schilderung des betroffenen Agenten
  `agent_case_statement`. Neu sind außerdem die Modelle in
  `who2be_models.case` und ein Repository. Ein Fall hängt immer an genau
  einem Agenten. Sein Inhalt ist nach dem Melden unveränderlich. Der Status
  ist keine Spalte, sondern ergibt sich aus dem jüngsten Ereignis im Verlauf.

  Die Datenbank sichert die Regeln selbst ab:
  - Längengrenzen und geschlossene Wertemengen für Schwere, Melder und Ziel.
  - Bei Werkzeugrechten und Modellgrenze bleibt die Element-ID leer, bei
    allen anderen Zielen ist sie Pflicht.
  - `addressed` braucht eine Version.
  - Kein Agent setzt `addressed`, `verified` oder `dismissed`.
  - Schildern kann nur der betroffene Agent.
  - Verlauf und Schilderungen sind append-only.
  - Die Workspaces sind per RLS strikt getrennt.

  Ein Fall lässt sich samt Verlauf löschen; zurück bleibt eine Audit-Zeile
  ohne Inhalt. `agent_memory.converted_case_id` hat jetzt einen
  Fremdschlüssel auf einen Fall desselben Agenten und ist nur bei
  Lernvorschlägen erlaubt. Endpunkte, MCP-Werkzeuge und die Einbindung in
  Export und Löschkonzept folgen in eigenen Paketen.

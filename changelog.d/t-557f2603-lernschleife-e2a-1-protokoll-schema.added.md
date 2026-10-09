- Das Datenmodell für Gesprächsprotokolle und Maßnahmen steht (ADR-0053,
  Lernschleife Phase E, Paket E2a-1). Migration 0103 legt das Protokoll
  `feedback_session` an, dazu die besprochenen Fälle `feedback_session_case`,
  die Maßnahme `measure`, deren Fälle `measure_case` und den Verlauf
  `measure_event`. Neu sind außerdem die Modelle in `who2be_models.session` und
  ein Repository. Ein Protokoll bespricht genau einen Agenten. Seine Fälle,
  seine Maßnahmen, deren Prüffall und eine Korrektur (`supersedes_id`) gehören
  per Fremdschlüssel zu genau diesem Agenten. Der Zustand einer Maßnahme ist
  keine Spalte, sondern ergibt sich aus dem jüngsten Ereignis im Verlauf.

  Die Datenbank sichert die Regeln selbst ab:
  - Längengrenzen: Zusammenfassung 4 000 Zeichen, Änderung 2 000,
    Erfolgskriterium und Gegenposition je 1 000.
  - Das Nachschau-Datum am Protokoll und der Prüffall an der Maßnahme sind
    Pflicht.
  - Eine Maßnahme an den Werkzeugrechten hat keine Element-ID, an allen
    anderen Zielen ist sie Pflicht. Modellgrenzen sind kein Ziel.
  - Jedes Ereignis hat seine Form: Version bei `draft_linked` und `activated`,
    Kennzahlen bei `follow_up_prepared`, Einstufung bei `reviewed`, Begründung
    bei `withdrawn` und bei „unwirksam“.
  - Nur ein Mensch stuft ein oder zieht zurück, nur das System aktiviert.
  - Protokolle, Maßnahmen und Verlauf sind unveränderlich, die App-Rolle darf
    nur lesen und anlegen.
  - Die Workspaces sind per RLS strikt getrennt.

  Wird ein Fall gelöscht, verschwinden nur seine Verknüpfungen. Protokoll und
  Maßnahme bleiben. Der Purge eines Agenten oder Workspace entfernt alles.
  Service, Endpunkte, MCP-Werkzeuge und die Einbindung in Export und
  Löschkonzept folgen in eigenen Paketen.

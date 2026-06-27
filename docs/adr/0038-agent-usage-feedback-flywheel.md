# ADR-0038 — Agent-Usage- & Feedback-Flywheel

- Status: Proposed
- Datum: 2026-06-27
- Kontext: AI-native-Optimierung; eine AgentDB wird erst dann selbst-verbessernd,
  wenn die konsumierenden Agenten zuruckmelden, *was* sie genutzt haben und *wie
  gut* es war.
- Bezug: ADR-0030 (MCP-Write-Tools), ADR-0012 (Prompt-Injection-Risiko),
  ADR-0031 (Compliance-Audit-Journals), ADR-0023 (RBAC / Per-Agent-Policy)

## Kontext

Der Schreibpfad heute ist reiner **Content-Write** (create/update/transition).
Es gibt keinen Rueckkanal: ein Agent konsumiert ein Playbook, aber das System
erfaehrt nie, ob das Playbook genutzt, uebersprungen oder als veraltet erkannt
wurde. `PlaybookUsage`/`ResourceUsage` sind nur strukturelle Backlinks (FK „wer
referenziert mich"), kein Laufzeit-Signal. Ohne diesen Loop kann der menschliche
Kurator nicht datengestuetzt entscheiden, was gepflegt, gemerged oder retired
gehoert — das ist die zentrale Luecke zur AI-native-Reife.

## Entscheidung

Wir fuehren einen **append-only Telemetrie-/Feedback-Kanal** als eigene
Schreibflaeche ein, strikt getrennt vom Content-Write.

- **`record_usage(entity_type, entity_id, version?, outcome?)`** — append-only
  Ereignis: *dieser Agent hat dieses Element (in dieser Version) genutzt*.
  `outcome ∈ {applied, skipped, error}`. Quantitatives Signal.
- **`submit_feedback(entity_type, entity_id, signal, note?)`** — qualitativ:
  `signal ∈ {helpful, outdated, incorrect, unclear}` + Freitext. Vorschlag, kein
  Auto-Edit.
- **`get_feedback(entity_type, entity_id)`** — Read fuer Kuratoren/Agenten
  (`editor`+), aggregiert Signale + letzte Notizen.

Persistenz: neue, **immutable** Tabellen `usage_event` und `agent_feedback`
(polymorph ueber `entity_type`+`entity_id`+optional `version`), je mit
`agent_id`/`actor`, `workspace_id`, `created_at`. Kein Update/Delete; passt unter
die Audit-Journal-Linie (ADR-0031).

## Warum das KEIN neuer Prompt-Injection-Vektor ist (Abgrenzung zu ADR-0012/0030)

Der Einwand aus ADR-0012 galt dem Content-Write: veraenderte Persona/Playbook
wird spaeter wieder *in einen Prompt gerendert*. **Telemetrie und Feedback
fliessen NIE in einen gerenderten System-Prompt.** Sie sind ausschliesslich
Eingang fuer das Kurator-Dashboard und Aggregate. Damit ist diese Schreibflaeche
risikoarm und braucht **keinen** Draft→active-Approval-Workflow — Events landen
sofort. Free-Text-`note` wird im UI escaped angezeigt (kein HTML-Render).

## Rechte

- Neue Capability **`feedback_write`** in `AgentToolPolicy`. **Default: True** —
  abweichend vom „secure by default"-Writes-Prinzip, weil Telemetrie der
  eigentliche Zweck des Flywheels und risikoarm ist; der Owner kann sie pro Agent
  abschalten (`feedback_write=False`).
- `record_usage` ist auf das **zugewiesene/sichtbare** Set begrenzt (Read-Scope):
  ein Agent meldet nur Nutzung von Elementen, die er auch sehen darf.
- `get_feedback` ist `editor`-gated (Kurations-Sicht).

## Konsequenzen

- Migration: `usage_event`, `agent_feedback` (append-only, indiziert auf
  `(workspace_id, entity_type, entity_id)`).
- Dashboard-Aggregate (Phase 2.1b-Dashboard erweitern): „meistgenutzt",
  „als veraltet markiert", „fehlerhaft gemeldet" → Kurations-Backlog.
- MCP: drei Tools; `tools-overview` listet sie gemaess Policy.
- Bewusst **kein** MCP-Delete/Edit auf Events (Audit-Integritaet, ADR-0031).

## Agenten-Verankerung (Folge, 2026-06-27)

Die Tools *verfuegbar* zu haben heisst nicht, dass das LLM sie *nutzt* — ein
Tool-Docstring wird erst beim Aufruf gelesen, nicht im Planungs-Prompt. Damit
Agenten das Flywheel auch bedienen, ist die Nutzung dreifach im Prompt verankert
(rein instruktiv, kein Zwang — passt zu „Vorschlag, kein Auto-Edit"):

1. **`tools-overview`-Resolver (global, hoechster Hebel):** Ist `feedback_write`
   aktiv, haengt der Resolver ein **Rueckmelde-Protokoll mit konkretem Beispiel**
   an die Tool-Liste (`record_usage` nach jedem Einsatz, `submit_feedback` bei
   veralteten/falschen Inhalten). Policy-gated — Agenten ohne die Capability
   sehen weder Tool noch Protokoll. Erreicht jeden Agenten mit dem
   `{{tools-overview}}`-Placeholder ohne Template-Pflege.
2. **Default-System-Prompt-Templates:** je ein Methodik-Bullet in der
   Hinweise-Sektion (im prozeduralen Fluss, nicht nur im Tool-Anhang).
3. **Builder-Persona:** Rueckmelde-Disziplin in der „Erlaubt"-Sektion (beim
   Konsistenz-Check Veraltetes melden statt uebergehen).

## Web-Surfacing (Folge, 2026-06-27)

Das Kurations-Aggregat ist jetzt in der Web-UI sichtbar — bewusst rein lesend,
kein neuer Schreibpfad, keine Migration (beide Read-Endpunkte aggregieren zur
Laufzeit ueber die append-only Tabellen):

- **Zwei additive editor-gated Read-Endpunkte** neben `GET …/feedback/{type}/{id}`:
  `GET …/feedback/{type}/{id}/events` (Drill-down auf die juengsten Einzel-
  Ereignisse, je Liste serverseitig auf 50 gekappt) und `GET …/feedback-overview`
  (workspace-weite Aggregation pro Element via FULL-OUTER-JOIN der beiden
  Tabellen; geloeschte Elemente fallen ueber den Namens-JOIN raus).
- **`FeedbackPanel`** auf den Detailseiten (Persona/Playbook/Resource, editor+):
  Nutzungszahl + Ergebnis-/Signal-Verteilung (Token-Balken, kein Chart-Dep),
  letzte Notizen (escaped), Lazy-Drill-down und — bei negativen Signalen — eine
  „Ueberarbeiten"-Aktion (scrollt zum Editor; der Auto-Save legt beim Bearbeiten
  einen Draft an).
- **`FeedbackTiles`** auf dem Dashboard (meistgenutzt / am haeufigsten bemaengelt)
  + eigene **Feedback-Uebersichtsseite** (`/w/{ws}/feedback`, Nav-Eintrag).

Der `note`-Freitext wird ueber React-Textnodes escaped; kein HTML-Render.
Triage (erledigt/ignoriert) bleibt bewusst offen — append-only erlaubt nur ein
*zusaetzliches* Resolution-Event, kein Mutieren der Feedback-Zeile.

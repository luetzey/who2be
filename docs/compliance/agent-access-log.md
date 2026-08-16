# Agent-Zugriffslog (`agent_access_log`)

**Zweck (Spec F, ADR-0047):** Rückwirkend beantworten können, *welche Elemente
je an einen externen Modell-Anbieter gegangen sind* — ohne auf die Disziplin
der Agenten-Runtimes angewiesen zu sein. Der Server protokolliert jeden
erfolgreichen Zugriff eines agent-gebundenen Tokens auf WorkArea-/KB-Objekte
automatisch; das verwendete Modell steht als betreiber-gepflegte Konfiguration
am Agenten (`agent.model_provider` / `agent.model_name`).

## Mechanik

- **Tabelle:** `agent_access_log` (Migration 0079) — append-only: die
  App-Rolle `who2be_app` hat nur `SELECT, INSERT` (DB-erzwungen, Muster
  ADR-0031). Dedupliziert pro `(agent_id, ref_kind, ref_id, operation,
  access_date)` via `ON CONFLICT DO NOTHING` — pro Element, Operation und Tag
  entsteht höchstens eine Zeile; das Volumen bleibt gebunden.
- **Schreibpunkte:** Einzel-Reads und Writes auf Artifacts (`wa_artifacts`,
  Ingest), KB-Nodes (inkl. Kanten — eine Kante verändert die Aussagekraft
  beider Node-Seiten) und Tabellen (`query`/`describe` = read, `rows` =
  write). Suchen loggen nicht (Snippets; der Inhalt fließt beim Einzel-Read,
  und der loggt). Menschen-Tokens (JWT) loggen nie.
- **`sensitivity_at_access`** ist der Server-Stand des Objekts zum
  Zugriffszeitpunkt — Agenten können ihn nicht deklarieren oder fälschen.
- **`model_provider_at_access` / `model_name_at_access`** (Migration 0080)
  sind der Server-Snapshot der Agent-Modell-Config **zum Zugriffszeitpunkt**.
  Der Insert zieht sie per Skalar-Subquery aus `agent` — kein Client-Input,
  kein zweiter Roundtrip. Vorher beantwortete nur ein JOIN auf die *aktuelle*
  Config die Anbieter-Frage; damit löschte ein Umstellen auf `local` die
  Vergangenheit rückwirkend.
- **Modell-Config:** `model_provider`/`model_name` pflegt **ausschließlich ein
  Mensch** — ein agent-gebundener Token bekommt beim Setzen 403
  (`missing_capability`), sonst könnte ein Agent seine eigene Attribution
  fälschen. Jede Änderung landet als `agent.model_config_changed` (alter +
  neuer Wert + `agent_id` des Aufrufers) im `audit_log`.
- **Nur agent-gebundene Tokens** erreichen die WorkArea-/KB-/Tabellen-Routen
  (403 sonst). Ein `w2b_`-Token ohne `agent_id` hätte sonst unbeschränkt
  gelesen, ohne je im Log zu erscheinen.
- **Lückenanzeige:** Das Logging ist best-effort (es bricht den Hauptpfad
  nie), zählt aber jeden verschluckten Schreibfehler in
  `services/access_log.failed_log_writes()`. Jeder Wert > 0 bedeutet: es hat
  Zugriffe gegeben, die nicht protokolliert sind.

## Betreiber-Query

„Welche sensiblen Elemente sind je an einen externen Anbieter gegangen?"

Maßgeblich sind die **gesnapshotteten** Spalten — sie beschreiben den Zustand
zum Zugriffszeitpunkt und ändern sich nie nachträglich:

```sql
SELECT l.access_date,
       a.name                     AS agent,
       l.model_provider_at_access AS model_provider,
       l.model_name_at_access     AS model_name,
       l.ref_kind,
       l.ref_id,
       l.operation
FROM agent_access_log l
JOIN agent a ON a.id = l.agent_id
WHERE l.sensitivity_at_access = 'sensitive'
  AND coalesce(l.model_provider_at_access, '') NOT IN ('', 'local')
ORDER BY l.access_date DESC, agent;
```

Der Join auf `agent` liefert nur noch den **Namen** — und ergänzend, wenn man
Snapshot und heutigen Stand vergleichen will, `a.model_provider` /
`a.model_name`. Weichen sie ab, ist der Agent seither umkonfiguriert worden;
die Historie dieser Änderungen steht als `action =
'agent.model_config_changed'` im `audit_log` (inkl. `agent_id` des Aufrufers,
falls die Änderung über einen Token lief).

Zeilen aus der Zeit vor Migration 0080 tragen `NULL` in den
Snapshot-Spalten — für sie bleibt der Join auf die aktuelle Config die
einzige (unscharfe) Auskunft.

## Grenze (bewusst, ADR-0047-Nachtrag)

Who2Be ist **kein Agent-Runtime-Host**: Das Modell eines Zugriffs ist die
*Agent-Konfiguration zum Zugriffszeitpunkt*, nicht eine pro Aufruf gemessene
Größe. Wechselt eine Runtime ihr Modell, ohne dass der Betreiber die
Agent-Config nachführt, weicht die Zuordnung ab — deshalb ist die Pflege der
Modell-Felder Betreiberpflicht (Menschen-Vorbehalt + auditiert). Ein
pro-Aufruf-Protokoll wäre nur per Selbstauskunft der Runtime möglich und
damit unvollständig genau dann, wenn es zählt (bewusst verworfene
Alternative, ADR-0047).

Seit Migration 0080 ist die Zuordnung immerhin **nicht mehr rückwirkend
verfälschbar**: der Snapshot friert sie ein, und der Menschen-Vorbehalt auf
`model_provider`/`model_name` verhindert, dass ein Agent sie selbst setzt.
Was bleibt, ist die Lücke zwischen Config und tatsächlicher Runtime — eine
Frage der Betreiberdisziplin, nicht der Manipulierbarkeit.

## Aufbewahrung

Append-only wie die übrigen Audit-Journale (ADR-0031): keine Updates/Deletes
durch die App; Löschung nur im Rahmen von GDPR-Erasure (Workspace-/
Org-Purge, `docs/compliance/data-retention-and-erasure.md`).

Seit Migration 0080 gilt das auch gegen **FK-Cascade**: `agent_access_log.
agent_id` referenziert `agent` mit `ON DELETE NO ACTION`. Vorher hätte ein
gewöhnlicher Agent-Delete über die API die Protokollzeilen desselben Agenten
mit abgeräumt — der Cascade läuft mit Owner-Rechten und ignoriert den
Grant-Entzug. Konsequenzen im Betrieb:

- Ein Agent mit protokollierten Zugriffen lässt sich **nicht löschen** (409,
  „nur über den Retention-/Purge-Pfad"). Wer ihn stilllegen will, setzt ihn
  auf `disabled`.
- Der Purge-Job (`core/purge.py`, Owner-Connection) löscht die Log-Zeilen der
  betroffenen Workspaces **explizit**, bevor die Organization-CASCADE greift
  — der eine legitime Löschpfad.

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
- **Modell-Config:** `model_provider`/`model_name` pflegt der Betreiber über
  den Agent-Update-Pfad; jede Änderung landet als
  `agent.model_config_changed` (alter + neuer Wert) im `audit_log`.

## Betreiber-Query

„Welche sensiblen Elemente sind je an einen externen Anbieter gegangen?"

```sql
SELECT l.access_date,
       a.name            AS agent,
       a.model_provider,
       a.model_name,
       l.ref_kind,
       l.ref_id,
       l.operation
FROM agent_access_log l
JOIN agent a ON a.id = l.agent_id
WHERE l.sensitivity_at_access = 'sensitive'
  AND coalesce(a.model_provider, '') NOT IN ('', 'local')
ORDER BY l.access_date DESC, agent;
```

Für die vollständige Historie der Modell-Zuordnung (Agent lief früher auf
einem anderen Modell) die `audit_log`-Einträge
`action = 'agent.model_config_changed'` desselben Agenten hinzuziehen.

## Grenze (bewusst, ADR-0047-Nachtrag)

Who2Be ist **kein Agent-Runtime-Host**: Das Modell eines Zugriffs ist die
*Agent-Konfiguration zum Zugriffszeitpunkt*, nicht eine pro Aufruf gemessene
Größe. Wechselt eine Runtime ihr Modell, ohne dass der Betreiber die
Agent-Config nachführt, weicht die Zuordnung ab — deshalb ist die Pflege der
Modell-Felder Betreiberpflicht (auditiert). Ein pro-Aufruf-Protokoll wäre nur
per Selbstauskunft der Runtime möglich und damit unvollständig genau dann,
wenn es zählt (bewusst verworfene Alternative, ADR-0047).

## Aufbewahrung

Append-only wie die übrigen Audit-Journale (ADR-0031): keine Updates/Deletes
durch die App; Löschung nur im Rahmen von GDPR-Erasure (Workspace-/
Org-Purge, `docs/compliance/data-retention-and-erasure.md`).

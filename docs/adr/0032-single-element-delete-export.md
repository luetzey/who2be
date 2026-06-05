# ADR-0032 — Einzel-Element Hard-Delete + Einzel-Export (Persona/Playbook/Resource)

- Status: Accepted
- Datum: 2026-06-05
- Kontext: Bis dato kein echter Loesch-Pfad fuer die Kernelemente Persona/
  Playbook/Resource (nur der Status-Workflow `draft → review → active →
  inactive`); Export existierte nur als DSGVO-Gesamtexport (`GET /v1/gdpr/export`).
- Bezug: ADR-0004 (Versionierung/History-Tabellen), ADR-0019 (Tenant/Org/
  Workspace), ADR-0020 (Status pro Version), ADR-0023 (Multi-User-RBAC),
  ADR-0024 (Composite-Playbooks), ADR-0030 (MCP-Write-Tools — kein delete/export
  ueber MCP)

## Kontext

Hart loeschbar war bislang nur der **Agent** (`DELETE …/agents/{id}`). Fuer
Persona/Playbook/Resource gab es ausschliesslich den Status-Workflow ("Retire" =
`inactive`), aber keinen Weg, eine Zeile inkl. Versionshistorie endgueltig zu
entfernen. Ebenso fehlte ein **Einzel**-Export eines Elements (nur der
Gesamtexport ueber `GdprExportService` existierte).

Zwei verschraenkte Fragen mussten beantwortet werden:

1. **Loesch-Semantik bei Referenzen.** Personas referenzieren Playbooks
   (`persona_playbook`), Playbooks referenzieren Resource-Bloecke
   (`playbook_resource_link`) und koennen Composite-Kinder haben
   (`playbook_composition`); Resources koennen Sub-Resources haben
   (`resource_composition`); Agents pinnen eine Persona (`agent.persona_id`,
   ON DELETE RESTRICT). Was passiert, wenn ein referenziertes Element geloescht
   wird?
2. **Export-Format.** JSON (vollstaendig, maschinenlesbar) und/oder ein
   menschenlesbares Markdown.

## Entscheidung

### 1. Hard-Delete sofort, kein Soft-Delete

`DELETE /v1/workspaces/{ws}/{personas|playbooks|resources}/{id}` loescht die
Identitaets-Zeile sofort und unwiderruflich (analog Agent-Delete), Status `204`.
Gate: `require_role(ctx, editor)` (konsistent mit `agent_service.delete`).

**FK-Kaskaden innerhalb des Aggregats** raeumen den Rest: alle Migrations-FKs auf
`{entity}_version` sowie die *ausgehenden* Link-/Composition-Zeilen stehen bereits
auf `ON DELETE CASCADE` (Migrationen 0002/0003/0004/0014/0015/0016/0028/0032).
Es war **keine neue Migration** noetig — ein einfacher
`DELETE FROM {entity} WHERE id = $1 AND workspace_id = $2` genuegt; Tests
verifizieren, dass keine Waisen-Versionen/-Links zurueckbleiben.

### 2. Eingehende Referenzen blockieren mit 409 (kein Cascade auf fremde Aggregate)

Loeschen wird **abgelehnt** (HTTP `409`), solange ein *anderes* Aggregat auf das
Element zeigt. Es gibt **kein** Cascade und **kein** Null-Setzen ueber
Aggregat-Grenzen — der Nutzer muss die Verknuepfung zuerst loesen.

| Element  | Blockiert durch (Quelle)                                                |
|----------|-------------------------------------------------------------------------|
| Persona  | `agent.persona_id` (Agenten)                                            |
| Playbook | `persona_playbook` (Personas) **+** `playbook_composition` (Eltern-Composites) |
| Resource | `playbook_resource_link` (Playbooks) **+** `resource_composition` (Eltern-Composites) |

> *Ausgehende* Links des zu loeschenden Elements blockieren nicht — sie
> verschwinden per Aggregat-internem FK-Cascade. Blockierend sind nur
> **eingehende** Referenzen anderer Aggregate.

Der 409-Body ist ein strukturiertes `DeleteBlocked`-Schema (`message: str`,
`blocked_by: dict[str, list[...]]`), sodass das Frontend die Verwender auflisten
kann (Quelle-Schluessel `agents`/`personas`/`playbooks`/`composites`).

Fuer Persona greift zusaetzlich der DB-seitige `ON DELETE RESTRICT` auf
`agent.persona_id` als zweite Verteidigungslinie; der 409-Pfad faengt den Fall
serverseitig vor dem DELETE ab und liefert die Klartext-Begruendung.

### 3. Einzel-Export als JSON und Markdown

`GET /v1/workspaces/{ws}/{entity}/{id}/export?format=json|markdown` (Default
`json`). **Lesen ist fuer Viewer offen** (kein `require_role`); Workspace-
Mitgliedschaft via `get_current_workspace` genuegt. Rate-Limit `write_limit`
(durchlaeuft alle Versionen, analog GDPR-Export).

- `json`: Identitaets-Zeile + **alle** Versionen, interne Mandanten-Spalten
  (`workspace_id`) entfernt (`_clean`-Muster aus `GdprExportService`).
- `markdown`: gerenderter Body der **aktiven** Version (sonst der neuesten) mit
  YAML-Frontmatter (`name`/`status`/`tags`, bei Playbook zusaetzlich `type`).
  Die Placeholder-Expansion laeuft ueber den **vorhandenen**
  `render_template_body`-Kern (denselben, den `PersonaService.render` und
  `PlaybookService.render` nutzen) — keine Render-Logik dupliziert.

Beide Formate setzen `Content-Disposition: attachment;
filename="who2be-{entity}-{id}.{json|md}"`.

### 4. Bewusst kein MCP-Delete/-Export

ADR-0030 haelt fest: **kein delete ueber MCP**. Diese ADR fuegt **kein** neues
MCP-Tool hinzu — weder Delete noch Export. Destruktive Operationen und der
Datenexport bleiben dem authentifizierten Web-/REST-Pfad mit RBAC-Gate
vorbehalten; der Agent-Pfad (MCP) bleibt read- und draft-fokussiert.

## Konsequenzen

- Sechs neue Endpunkte (3× `DELETE`, 3× `GET …/export`), je ein neues
  Repo-`delete(...)`, Usage-Reverse-Lookups (`list_persona_usages`,
  Composite-Parents fuer Playbook/Resource), ein gemeinsamer
  `EntityExportService`.
- Neues Pydantic-Model `PersonaUsage` (analog `PlaybookUsage`/`ResourceUsage`)
  und `DeleteBlocked` (strukturierter 409-Body).
- Keine Schema-Migration noetig (bestehende Cascades reichen).
- MCP unveraendert; ADR-0030-Grenze bleibt gewahrt.

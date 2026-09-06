# ADR-0051 — API-Fehler tragen einen stabilen `reason` neben `detail`

- Status: Akzeptiert
- Datum: 2026-09-06
- Kontext: Issue #402 (Tracking) mit #436 als Welle 0. Server-Fehler erreichen
  die UI heute als deutscher Prosa-String, unabhaengig von der UI-Sprache;
  MCP-Clients bekommen an denselben Stellen nichts Auswertbares.
- Bezug: WP-2 / #254 (`ApiProblem`, RFC 7807 an den Gates), ADR-0002
  (Exception-Hierarchie, offen), ADR-0023 (Tenancy/RBAC),
  `docs/frontend/i18n.md`, CLAUDE.md §Code-Style (Interims-Leitplanke: kein
  HTTP in Services).

## Kontext

Eine Fehlerantwort der API sah bis hierher auf zwei Arten aus.

**An den zentralen Gates** (Autorisierung, Status-Uebergaenge, WorkArea/KB)
liefert `ApiGateError` seit WP-2 einen RFC-7807-Body als
`application/problem+json`: `type`, `title`, `status`, `detail` plus die
Who2Be-Felder `reason`, `actionable_by`, `request_id`. Das sind **52**
Call-Sites, und ihr `reason` kommt aus `ProblemReason`
(`packages/models/src/who2be_models/errors.py`).

**Ueberall sonst** — rund **79** Stellen — steht eine nackte `HTTPException`
mit `detail="…"` auf Deutsch. Der Web-Client las genau dieses eine Feld
(`apps/web/src/api/client.ts`), ein MCP-Client bekommt Prosa, auf die er nicht
verzweigen kann.

Zwei Dinge waren dabei zu klaeren, und die zweite Frage haben wir zuerst
falsch beantwortet:

1. Ob `detail` bleibt. → Ja, additiv (siehe Entscheidung).
2. Ob das neue Fehlervokabular ein **zweiter** Enum neben `ProblemReason`
   wird. Die urspruengliche Empfehlung sagte ja — auf der Annahme,
   `ProblemReason` sei ein enges Gate-Vokabular mit fuenf Werten. **Diese
   Annahme war falsch.** `ProblemReason` traegt 24 Werte, darunter
   `ingest_too_large`, `blobstore_unconfigured`, `url_forbidden`,
   `tablestore_unavailable` — WorkArea, Knowledge Base, Ingest, Blob-Storage.
   Es ist laengst kein Gate-Vokabular mehr, sondern das Fehler-Vokabular der
   API. Ein zweiter Enum daneben waere eine Dublette gewesen, und zwei Listen
   mit derselben Aufgabe laufen auseinander.

## Entscheidung

**Ein Vokabular, zwei Serialisierungen.**

### 1. `ProblemReason` ist das Fehler-Vokabular der ganzen API

Jeder maschinenlesbare Fehlergrund — Gate oder nicht — kommt aus
`who2be_models.errors.ProblemReason`. Neue Gruende werden dort ergaenzt, Welle
fuer Welle. Es gibt keinen zweiten Enum.

Der Preis: die Liste waechst (heute 27 Werte). Das ist der richtige Preis —
ein Agent, der auf `reason` verzweigt, hat genau eine Liste zu kennen, und
`_PROBLEM_TITLES` in `main.py` bleibt die eine Titel-Tabelle dazu (ein Test
haelt sie vollstaendig).

### 2. `detail` bleibt Wort fuer Wort, `reason` kommt additiv dazu

Kein Feld wird entfernt oder umformuliert. `client.ts` und die MCP-Clients
lesen `detail` heute; eine migrierte Stelle unterscheidet sich fuer sie nur um
ein zusaetzliches Feld, das sie ignorieren duerfen. Optional kommt `params`
dazu: die Werte, die der Client in den uebersetzten Text interpoliert.

### 3. Zwei Serialisierungen bleiben — und das ist Absicht

| | `ApiProblem` | `ApiErrorBody` |
|---|---|---|
| Wo | die 52 Gate-Stellen | alles uebrige |
| Content-Type | `application/problem+json` | `application/json` |
| Felder | `type`, `title`, `status`, `detail`, `reason`, `actionable_by`, `request_id` | `detail`, `reason`, optional `params` |
| Exception | `ApiGateError` | `ApiError` (Unterklasse von `HTTPException`) |

**Warum nicht vereinheitlichen** — die Frage, die sonst bei jedem Router neu
gestellt wird:

- Die Gate-Antworten sind ein **bestehender, ausgelieferter Vertrag** mit
  eigenem Content-Type. Die 79 Stellen auf `problem+json` zu heben hiesse, den
  Content-Type jeder Fehlerantwort der API zu aendern und ueberall
  `actionable_by`/`type`/`title` zu erfinden — ein Breaking Change am gesamten
  Fehler-Contract, plus 79 Entscheidungen, wer den Fehler beheben kann.
  Umgekehrt (Gates auf den schlanken Body) verloere man `actionable_by` und
  `request_id`, die dort Zweck haben.
- Der Nutzen waere gering, weil der **Client die Huelle nicht sieht**: er liest
  `reason` und uebersetzt. Unterschiedlich ist die Serialisierung, nicht das
  Vokabular — es gibt genau einen Uebersetzungspfad.
- Eine Vereinheitlichung ist damit ein eigenes Vorhaben mit eigener
  Migrations-Frist (#402, „Weg C"), kein Nebenprodukt dieser Welle.

### 4. Der Grund entsteht in der Domaene, nie im Router

`ApiError` wird an der Service-/Domain-Stelle geworfen, die den Fehler kennt.
Der zentrale Handler `_on_api_error` (`apps/api/src/who2be_api/main.py`)
serialisiert; er leitet keinen Grund her. Router bleiben unangetastet — das
haelt die Interims-Leitplanke aus CLAUDE.md ein und verhindert, dass derselbe
Fall an zwei Stellen verschiedene Gruende bekommt.

`ApiError` erbt bewusst von `HTTPException`: `except HTTPException`,
`exc.status_code`, `exc.detail` und die Header gelten unveraendert weiter.
Starlette waehlt den Handler entlang der MRO, `ApiError` steht darin vor
`HTTPException` — **nicht migrierte Stellen laufen weiterhin in den
FastAPI-Default und sind byte-identisch zu vorher.** Das ist die eigentliche
Risiko-Zusage der Welle, und ein Test haelt sie fest
(`test_unmigrated_error_body_is_unchanged`).

### 5. Client: `reason` gewinnt, `detail` faengt auf

```ts
i18n.t(`common:errors.${reason}`, { ...params, defaultValue: detail })
```

Der Locale-Key ist der `reason` **wortgleich** (`common:errors.agent_not_found`)
— kein Mapping, das driften koennte. `defaultValue: detail` ist der Grund,
warum die Migration ueberhaupt in Wellen laufen kann: ein Grund ohne
Locale-Key zeigt den deutschen Servertext, nie einen rohen Key. Der Pfad gilt
fuer **beide** Serialisierungen, weil beide `reason` tragen.

### 6. OpenAPI

`ApiErrorBody` ist an den Pilot-Routen als `responses`-Eintrag deklariert,
damit das Schema im Contract-Artefakt steht (`docs/reference/openapi.json`).
`openapi_surface.json` friert nur Methode/Pfad/`operationId` ein und aendert
sich dadurch nicht.

`db_unavailable` bleibt undeklariert: er entsteht in einer Dependency, die
fast jede Route traegt — ihn pro Route zu deklarieren waere Rauschen ohne
Erkenntnis.

## Konsequenzen

**Gut:**

- Ein Agent kann auf `reason` deterministisch verzweigen, ohne Freitext zu
  parsen — an Gate- wie an Nicht-Gate-Stellen.
- Die UI zeigt Server-Fehler in der UI-Sprache, ohne dass der Server die
  Sprache des Aufrufers kennen muss.
- Die Wellen W1–Wn (#402) sind unabhaengig mergebar: jede migriert Stellen,
  ergaenzt Gruende und Locale-Keys, und bricht nichts, was noch nicht dran war.

**Kosten / Risiken:**

- Zwei Fehler-Serialisierungen bleiben nebeneinander bestehen. Wer die API
  neu liest, wird das als Inkonsistenz sehen — deshalb steht die Begruendung
  hier und nicht nur im Commit.
- `ProblemReason` waechst zu einer langen Liste. Akzeptiert; die Alternative
  (zwei Listen) ist schlechter.
- Bis alle Wellen durch sind, tragen manche Fehlerantworten `reason` und
  andere nicht. Der `defaultValue`-Fallback macht das fuer den Nutzer
  unsichtbar.
- Die Locale-Keys sind `snake_case` inmitten `camelCase`-Nachbarn. Bewusst:
  der Key IST der Wire-Wert.

## Umfang von Welle 0 (#436)

Drei Pilot-Gruende, an ihren Domain-Stellen:

| `reason` | Status | Wo |
|---|---|---|
| `agent_not_found` | 404 | `services/agent_service.py`, `services/memory_service.py`, `services/agent_render_service.py`, `services/agent_fetch_rendered_service.py`, `core/agent_scope.py`, `core/workarea_scope.py` |
| `db_unavailable` | 503 | `core/security.py` (beide Pool-Zugriffe) |
| `last_workspace_undeletable` | 409 | `services/workspace_service.py` |

**Nicht in W0:** die uebrigen ~76 `detail`-Stellen, die MCP-Client-Seite, die
zwei Inline-`HTTPException`-Raises in `routers/agents.py` (Confinement-Guards
— sie gehoeren in eine Welle, die sie zugleich in die Domaene zieht), und die
Vereinheitlichung der Content-Types.

## Verworfene Alternativen

**A — zweiter Enum `ErrorCode` neben `ProblemReason`.** Verworfen: die
Annahme, `ProblemReason` sei ein enges Gate-Vokabular, war falsch (24 Werte,
davon die Haelfte ausserhalb der Gates). Zwei Listen mit derselben Aufgabe
laufen auseinander, und der Client haette zwei Uebersetzungspfade gebraucht.

**C — alle Fehlerantworten auf `application/problem+json`.** Verworfen fuer
diese Welle: Breaking Change am gesamten Fehler-Contract, plus 79 Mal die
Frage nach `actionable_by`. Bleibt als eigenes Vorhaben moeglich; diese ADR
macht es nicht schwerer, weil das Vokabular schon geteilt ist.

**D — `detail` durch den Code ersetzen.** Verworfen: `client.ts` und die
MCP-Clients lesen `detail` heute. Ein Ersetzen waere ein Breaking Change ohne
Migrationsweg, und Logs/Support verlieren den Klartext.

**E — Uebersetzung serverseitig ueber den `Accept-Language`-Header.**
Verworfen: die UI-Sprache ist eine Client-Eigenschaft (Umschalter ohne
Reload), der Server muesste jede Sprache kennen, und MCP-Clients wollen gar
keinen Text, sondern den Code.

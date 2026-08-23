# Persona-Lookup per Name: serverseitiger Filter statt Client-Scan

_Angelegt: 2026-08-23 13:35 UTC — Coder / Code-Task-Flow_

## Anlass

`get_persona("Builder")` (Aufloesung per NAME) brach im YouTube-Workspace mit
einem nichtssagenden `Error occurred during tool execution` ab, waehrend
`get_persona("<uuid>")` unmittelbar danach durchlief. Der Agent hat sich ueber
`whoami` → `get_agent` → `get_persona(<persona_id>)` selbst geholfen.

## Ursache (belegt)

Die beiden Aufloesungs-Pfade sind strukturell verschieden:

- **Per UUID** (`apps/mcp/src/who2be_mcp/client.py:288-293`): ein gezieltes
  `GET .../personas/{id}`.
- **Per Name** (`client.py:295-302`): `GET .../personas` — die **ganze Liste**
  — und anschliessend ein linearer Namensvergleich im Client.

`PersonaRead` traegt `content` (`packages/models/src/who2be_models/persona.py:251`),
also den vollstaendigen BlockNote-Body. Der Name-Pfad zieht damit den
ausgeschriebenen Text JEDER Persona des Workspace ueber die Leitung, nur um
einen String zu vergleichen. Groessenordnung: eine einzelne Persona des
Who2Be-Workspace rendert 119.255 Zeichen. Bei `_TIMEOUT = 10.0`
(`client.py:76`) und einer frisch aufgebauten Verbindung pro Request
(`client.py:198`, kein Pooling) ist das die plausibelste Ursache des Abbruchs.

**Grenze der Diagnose:** aus dem Transkript nicht beweisbar — die Meldung
traegt kein Detail. Belegbar ist nur, dass es KEIN sauberer Fehlerpfad war:
ein `ToolError` haette seinen Text gezeigt (hier: „Keine Persona mit Name
'Builder'."), so wie die Workspace-Meldung aus #413. Es war also eine
unbehandelte Ausnahme oder ein Transport-Abbruch. Endgueltig klaeren wuerde es
das Server-Log zu `request_id: req_011CeKm1LsS3nTPoKa4JjZvj`.

## Zweiter, latenter Fehler (gleicher Code-Pfad)

`_resolve_persona_by_name` sendet **kein `limit`** und folgt **nie dem
`X-Next-Cursor`**, obwohl der List-Endpoint paginiert ist
(`apps/api/src/who2be_api/routers/personas.py:75-90`, `DEFAULT_LIMIT = 100` in
`packages/models/src/who2be_models/pagination.py:24`). Ab 101 Personas meldet
die Namenssuche „Keine Persona mit Name X" fuer eine existierende Persona —
eine still falsche Antwort statt eines Fehlers.

Der serverseitige Filter behebt das mit: die gefilterte Ergebnismenge liegt bei
1-2 Zeilen und damit weit unter dem Seiten-Limit. Cursor-Verfolgung im Client
wird dadurch entbehrlich statt nachgeruestet.

## Arbeitspakete

### AP1 — API: `?name=`-Filter auf `GET /v1/workspaces/{ws}/personas`

- `repositories/persona_repository.py`: `list_by_workspace(..., name=None)`,
  Praedikat `AND ($n::text IS NULL OR e.name = $n)` — dieselbe Mechanik wie die
  bestehenden `locale`- und `restrict_ids`-Filter. Beide Query-Zweige (mit und
  ohne Cursor) und das Protocol mitziehen.
- `services/persona_service.py`: `list_all(..., name=None)` durchreichen.
- `routers/personas.py`: `?name=` als `Query(max_length=200)` (Laenge wie
  `PersonaCreate.name`).

**Exakter Match, kein `ILIKE`.** Der Client vergleicht heute mit `==`; ein
case-insensitiver oder unscharfer Filter waere eine stille Verhaltensaenderung
an einem Aufloesungs-Pfad. Sortierung bleibt `created_at DESC, id DESC`, damit
bei mehreren gleichnamigen Personae (Name ist NICHT unique — dieselbe Persona
kann in `de` und `en` existieren, ADR-0045) derselbe Treffer gewinnt wie bisher.

### AP2 — MCP: den Filter nutzen, Client-Check als Sicherheitsnetz behalten

`_resolve_persona_by_name` sendet `?name=` mit. Der bestehende
`persona.name == name`-Vergleich bleibt **bewusst stehen**: eine aeltere API
ignoriert den unbekannten Query-Parameter und liefert die volle Liste — der
Client faellt dann auf das heutige Verhalten zurueck, statt die erstbeste
Persona als Treffer auszugeben. Ohne diesen Rest waere ein Versions-Versatz
zwischen MCP und API ein stiller Falschtreffer.

### AP3 — Doku

- `CHANGELOG.md` (Unreleased): Fixed/Changed.
- `docs/reference/openapi.json` regenerieren (`scripts/export_openapi.py`).

## Out of Scope

- `_resolve_external_tool_by_alias` (`client.py:542`) hat dasselbe
  Scan-Muster. External-Tool-Bindungen tragen aber keine grossen Bodies, der
  Leidensdruck ist ein anderer — eigener Befund, eigenes Ticket.
- Das strukturelle Thema „nachschlagen statt gezielt fragen" insgesamt: ADR-0050.

## Acceptance Criteria

1. `GET .../personas?name=Builder` liefert nur die Personae mit exakt diesem
   Namen; ohne `?name=` ist die Antwort unveraendert.
2. `?name=` kombiniert sich mit `?locale=` und `?agent=`.
3. Der MCP-Namens-Pfad laedt nicht mehr die ganze Library.
4. Aeltere API ohne `?name=` (Parameter wird ignoriert) → Aufloesung bleibt
   korrekt, kein Falschtreffer.
5. `ruff` / `ruff format` / `mypy` / `pytest --cov --cov-fail-under=85` gruen.

## Verifikation

`uv run ruff check . && uv run ruff format --check . && uv run mypy . &&
uv run pytest --cov --cov-fail-under=85`

Kein `apps/web`-Diff — der Web-Stack ist nicht betroffen.

## Uebergabe-Bericht

### (a) Betroffene Software-Elemente (per ripgrep rueckwaerts gesucht)

**DIREKT**

- `PgPersonaRepository.list_by_workspace` + das `PersonaRepository`-Protocol —
  1 Aufrufer: `services/persona_service.py:218`. Neuer Parameter mit Default
  `None`, beide Query-Zweige (mit und ohne Cursor) gezogen.
- `PersonaService.list_all` — 1 Aufrufer: `routers/personas.py:90`.
- `list_personas` (Router) — neuer optionaler Query-Parameter; ohne `?name=`
  ist die Antwort byte-gleich zu vorher.
- `ApiClient._resolve_persona_by_name` — 1 Aufrufer: `client.get_persona`
  (`client.py:291`).

**TRANSITIV**

- MCP-Tool `get_persona` (`server.py:418`) und damit jeder Agenten-Boot, der
  seine Persona per Namen laedt — genau der Pfad, der gebrochen war.
- `apps/web/src/api/client.ts:622` ruft `GET .../personas` mit optionalem
  Query-String. Additiver Parameter, Default `None` → kein Web-Verhalten
  aendert sich; kein `apps/web`-Diff in diesem PR.

**VERMUTET (unsicher)**

- Fremde Clients, die `GET .../personas` direkt sprechen: sie erhalten
  unveraendert die volle Liste, solange sie `?name=` nicht setzen. Nicht
  ausgefuehrt verifiziert, da ausserhalb des Repos.

### (b) Rest-Test-Liste

**Diff-Coverage: in dieser Umgebung nicht messbar** — kein Docker-Daemon, kein
erreichbares Postgres, 448 DB-Integrationstests werden zentral uebersprungen
(`conftest.py`). Unit-seitig gruen: 1305 passed, 448 skipped (vorher 1300).
Das 85-%-Gate muss die CI bestaetigen.

Neu abgedeckt:

- `PersonaService.list_all(name=…)` — Treffer, Exaktheit (kein Substring, kein
  Case-Fold) und Unveraendertheit ohne Filter.
- `_resolve_persona_by_name` — dass `?name=` tatsaechlich mitgeht (echter
  Regressionstest: vorher wurde der Parameter nie gesendet) und dass der
  Client-Vergleich bei einer aelteren, den Parameter ignorierenden API den
  richtigen statt des erstbesten Treffers liefert.

Ungedeckt und manuell zu pruefen:

- `list_personas` (Router) mit `?name=` in Kombination mit `?locale=` und
  `?agent=` — die Kombination haengt an DB-gestuetzten Integrationstests
  (hier uebersprungen). Der Service-Test deckt den Filter selbst ab, nicht das
  Zusammenspiel der drei Query-Parameter im Router.
- Der Abnahme-Fall selbst: `get_persona("Builder")` gegen einen Workspace mit
  mehreren ausgebauten Personas muss durchlaufen, statt in den Timeout zu
  rennen. Nur gegen einen laufenden Stack pruefbar.

### Offen (nicht Teil dieses PR)

Die urspruengliche Fehlermeldung trug kein Detail. Ob wirklich der Timeout
zugeschlagen hat, klaert nur das Server-Log zu
`request_id: req_011CeKm1LsS3nTPoKa4JjZvj`. Die Aenderung entfernt die Ursache
unabhaengig davon — aber falls das Log einen 5xx zeigt, steckt dahinter noch
etwas anderes.

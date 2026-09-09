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

## Ausnahme (2026-09-08, W7b von #491/#502): drei Objekt-`detail`-Stellen bleiben aussen vor

Drei Stellen wandern bewusst **nicht** in dieses Schema, obwohl sie
`HTTPException` mit dynamischem Inhalt werfen:

- `services/persona_service.py:107` (`_delete_blocked`)
- `services/playbook_service.py:105` (`_delete_blocked`)
- `services/resource_service.py:97` (`_delete_blocked`)

Alle drei liefern `detail=<Model>.model_dump(mode="json")` — ein **Objekt**
(`{"detail": "...", "blocked_by": {...}}`), keinen String. `ApiErrorBody.detail`
ist als `str` deklariert (siehe oben, Abschnitt 3): die Struktur ist an diesen
drei Stellen die **Nutzlast** selbst (der Client braucht `blocked_by`, um die
blockierenden IDs anzuzeigen), nicht eine Fehlermeldung mit Beiwerk. Sie in
`ApiError`/`ApiErrorBody` zu pressen hiesse entweder, `blocked_by` zu verlieren,
oder `ApiErrorBody.detail` auf `str | dict` zu erweitern — beides eine
Vertragsaenderung am bestehenden Fehler-Contract, keine additive Migration.
Eine Erweiterung des Vertrags ist als eigenes Vorhaben denkbar (#504), aber
nicht Teil dieser Welle.

Das ist eine **Owner-Entscheidung vom 2026-09-08** (Option C zu #491:
dokumentieren statt erzwingen), kein Uebersehen — der Fall war beim Zuschnitt
von #491 bekannt und ist bereits einmal aufgetaucht:
`.claude/context/DECISIONS.md:1432-1440` (Eintrag „Der Bestandszaehler von
#402 zaehlt Wuerfe, nicht Schreibweisen", 2026-09-07) haelt exakt dieselben
drei Stellen als „mit dem heutigen Vertrag gar nicht migrierbar" fest.

## Ausnahme (2026-09-09, W7c von #491/#506): sechs WorkArea-Gruende bleiben ohne Locale-Key

Sechs Gruende tragen bewusst **keinen** Eintrag unter `common.errors`, obwohl
sie nach Abschnitt 5 einen bekommen koennten:

- `promote_unsupported` (`routers/wa_artifacts.py`)
- `table_rows_invalid`, `query_invalid`, `query_timeout` (`routers/wa_tables.py`)
- `timeline_request_invalid`, `query_timeout` (`routers/wa_timeline.py`)
- `memory_guard_rejected` (`services/memory_service.py`)

**Ein Locale-Key uebersetzt fuer einen menschlichen Leser. Diese sechs haben
keinen.** Ihre Endpunkte sind ausschliesslich ueber MCP erreichbar; die
Web-Anwendung ruft keinen von ihnen auf (`apps/web/src/api/client.ts`,
gegengezaehlt am 2026-09-09: null Aufrufe fuer `insert_rows`, `query_table`,
`timeline`, `promote_artifact`; bei `save_memory` nutzt das Web nur
list/triage/update/delete). Das ist keine Luecke, sondern eine
Architekturentscheidung — `apps/web/src/features/workarea/pages/TableDetailPage.tsx:46-48`
haelt sie fest: die Tabellen-Ansicht ist „bewusst read-only … geschrieben wird
ueber MCP (`create_table`/`insert_rows`); die Web-Ansicht ist der Nachvollzug
fuer den Menschen, nicht ein zweiter Schreibpfad" (ADR-0049).

Der Konsument dieser Fehler ist also ein Agent — und der liest den `reason`,
nicht den Text. Abschnitt 5 beschreibt bereits, was ohne Key passiert
(`defaultValue: detail` zeigt den deutschen Servertext, nie einen rohen Key).
Fuer diese sechs ist das der **Endzustand**, nicht ein Zwischenstand einer
noch laufenden Welle.

**Der Ausloeser, der diese Ausnahme umdreht:** wird einer der fuenf Endpunkte
schreibend an die Web-UI angebunden — also ADR-0049 an dieser Stelle revidiert
—, ist der Locale-Key fuer die betroffenen Gruende faellig. Dann aber **mit
`params`**: das `detail` ist an allen sechs Stellen zur Laufzeit
uneindeutig (fuenf Wurfstellen bei `TableRowsInvalid` mit Zeile, Spalte und
Limit; fuenf Call-Sites bei der Timeline-Validierung; der `sqlite3`-Fehlertext
bei `query_invalid`; zwei Router-Suffixe bei `query_timeout`). Ein statischer
Key wuerde den spezifischen Text nicht ergaenzen, sondern **ersetzen** — aus
„Zeile 3: unbekannte Spalten foo, bar — das Schema kennt nur: id, name."
wuerde „Zeilen-Import passt nicht zum Tabellen-Schema." Das Muster fuer den
richtigen Weg steht in W7b (`316e1e9`): `ApiError(reason=…, params={…})`,
Platzhalter im Locale-Key.

Nicht Teil dieser Entscheidung ist, ob `table_rows_invalid` und
`timeline_request_invalid` in feinere Gruende zerfallen sollten — beide decken
je fuenf Fehlerarten ab. Heute verzweigt kein Client darauf; eine feinere
Taxonomie braucht einen eigenen Nutzen-Nachweis.

Das ist eine **Owner-Entscheidung vom 2026-09-09** (Option A von drei zu
#510), kein Uebersehen: der Fall war beim Zuschnitt bekannt und wurde
gemessen, bevor er entschieden wurde. Dieselbe Argumentationslinie liegt
offen fuer die 52 Gate-Stellen, deren 23 Gruende ebenfalls keinen Locale-Key
tragen (#504).

## Ausnahme (2026-09-09, #504): die RFC-7807-Huelle bekommt kein `params`

`ApiErrorBody` traegt ein optionales `params`, `ApiProblem` nicht. Die Frage,
ob die RFC-Huelle es ebenfalls bekommen soll, ist mit **nein** entschieden —
vorerst.

Gemessen am 2026-09-09 (`.claude/plan/scripts/measure_gate_reasons.py`):

- **52** Gate-Stellen (`ApiGateError(...)`), darunter **23** distinkte Gruende
- davon **23 von 23 ohne Locale-Key** unter `common.errors`
- ohne `params` waeren nur **7** Gruende (10 der 52 Stellen) allein durch
  Locale-Keys uebersetzbar; die uebrigen 16 Gruende / 42 Stellen brauchen
  entweder `params` oder je Fall einen eigenen Key

**Die Zahl, die den Ausschlag gibt, ist nicht 52, sondern 23 von 23.** Dass
kein einziger Gate-Grund je einen Locale-Key bekommen hat, belegt nicht nur
die Luecke, sondern auch, dass sie in der gesamten Geschichte des Projekts
niemanden gestoert hat. Ueber `defaultValue: detail` (Abschnitt 5) erscheint
an jeder der 52 Stellen ein spezifischer, korrekter Satz — er ist nur deutsch.

Dazu kommt eine Eigenschaft, die beim Zuschnitt leicht uebersehen wird:
**`params` allein aendert nichts, was ein Nutzer sieht.** Das Feld uebersetzt
keine Meldung; es ermoeglicht eine Folgewelle, die fuer 23 Gruende Locale-Keys
in DE und EN anlegt und an 42 Stellen die interpolierten Werte herauszieht.
Der Preis von „ja" ist also nicht eine Vertragsaenderung, sondern **eine
Vertragsaenderung plus eine Welle ueber 52 Stellen** — und die Aenderung
traefe eine Huelle mit `model_config = ConfigDict(extra="forbid")`, die jeder
streng validierende Client kennen muesste.

**Der Ausloeser, der diese Entscheidung umdreht**, ist einer von zweien:

1. der erste externe Konsument, fuer den eine deutsche Fehlermeldung ein
   Mangel ist (ein Kunde, ein Cloud-Nutzer, ein MCP-Client mit englischer
   Oberflaeche), oder
2. der erste Fall, in dem ein Client auf einem Gate-Wert **verzweigen** soll
   statt ihn nur anzuzeigen — dann ist `params` kein i18n-Thema mehr, sondern
   Vertrag.

Tritt einer davon ein, ist die Erweiterung faellig, und dann als ein
Zuschnitt: Feld **plus** Welle, nicht das Feld allein. **`nein` ist jederzeit
nach `ja` revidierbar; `ja` nach `nein` nur mit einem zweiten Vertragsbruch** —
das ist der eigentliche Grund fuer die Reihenfolge.

Das ist eine **Owner-Entscheidung vom 2026-09-09** (Option A von drei zu
#504), getroffen nach fuenf unabhaengigen Messungen derselben Flaeche. Sie
folgt derselben Linie wie die Ausnahme zu W7c oben: **bevor eine Flaeche
uebersetzbar gemacht wird, wird gezaehlt, wer sie liest.**

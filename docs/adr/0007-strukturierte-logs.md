# ADR-0007 — Strukturierte JSON-Logs (structlog)

- Status: Akzeptiert
- Datum: 2026-05-25
- Kontext: Who2Be MVP (PROJ-19), MS-3 H2

## Kontext

API und MCP-Server loggen heute fragmentarisch ueber stdlib `logging` ohne
Format-Konvention und ohne Request-Korrelation. Mit dem bevorstehenden
Hetzner-Deploy (MS-2) wird Log-Aggregation noetig — der Aggregator (Loki /
CloudWatch / etc.) muss strukturierte Felder parsen koennen, und eine
`request_id` muss Eintraege ueber Schichten hinweg zusammenfuehren.

Anforderung aus der Roadmap (MS-3 H2): pro Request bzw. Tool-Aufruf eine
JSON-Zeile mit `request_id`, `owner_id` (API), `path`, `status`,
`duration_ms`.

## Optionen

- **A — `structlog` mit `ProcessorFormatter` ueber stdlib.** Native
  Context-Binding ueber `contextvars`, composable Processor-Pipeline, ein
  Renderer-Schalter `json`↔`console`. Bestehende `logging.getLogger(__name__)`-
  Aufrufe (`core/db.py`, `core/security.py`, `client.py`) bleiben funktional
  und werden mit-formatiert.
- **B — `python-json-logger` + `logging.config.dictConfig`.** Bleibt im stdlib-
  Universum, minimal-invasiv, aber Context-Binding (`request_id`,
  `owner_id`) muss ueber einen Custom-`Formatter` manuell aus `contextvars`
  geholt werden — mehr Boilerplate, kein offizielles async-Pattern.
- **C — Eigener `logging.Formatter` mit `json.dumps`.** Geringste Abhaengigkeit,
  aber jedes Feature (Timestamp, Level-Name, Exception-Info, Context-Merge)
  selbst zu implementieren und zu warten.

## Entscheidung

**A — `structlog`** in API und MCP. Hauptgruende:

- **Context-Binding via `structlog.contextvars`** ist async-safe und
  passt direkt zum bestehenden Pattern (`get_current_user`-Dependency
  bindet `owner_id`; ASGI-Middleware bindet `request_id`).
- **`ProcessorFormatter`** macht die bestehenden `logging.getLogger`-Calls
  ohne Refactor JSON-fit.
- **`JSONRenderer` ↔ `ConsoleRenderer`-Schalter** ueber `LOG_FORMAT`-Env
  haelt die lokale DX (lesbarer Tail) gleichwertig.
- **mypy-strict-kompatibel** dank vollstaendiger Typ-Stubs in structlog 24+.

## Konsequenzen

- Eine zusaetzliche Dependency in `apps/api/pyproject.toml` und
  `apps/mcp/pyproject.toml` (`structlog>=24.1`).
- `X-Request-ID`-Header wird Eingangs- (uebernommen, falls vorhanden) und
  Ausgangs-Vertrag der API — fuer kuenftiges Distributed Tracing relevant.
- Log-Aggregatoren bekommen ab MS-2 strukturierte Zeilen; Loki-/CloudWatch-
  Queries koennen direkt nach `request_id`, `owner_id`, `status` filtern.
- Kein automatisches Forwarden der `request_id` an Cross-Service-Aufrufe
  (z. B. MCP → API) — bewusste Folge-Task, nicht Teil von H2.
- Sensible-Daten-Redaction bleibt out of scope: wir loggen nur Metadaten,
  keine Request-Bodies.

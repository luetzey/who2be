# ADR-0010 — Observability: Prometheus-Metriken ueber internal-Pfad

- Status: Akzeptiert
- Datum: 2026-05-26
- Kontext: Who2Be MVP (PROJ-19), MS-3 H7 / Plan-Review 2026-05-26
- Bezug: ADR-0007 (strukturierte Logs)

## Kontext

ADR-0007 deckt strukturierte Logs ab, aber Logs allein erlauben keine
Trend-Sicht und keine SLO-Messung. Im Hetzner-Deploy (self-hosted)
sollen RED-Metriken (Rate, Errors, Duration) ohne Log-Forensik
sichtbar sein.

## Optionen

- **A — Logs-only (Status quo).** Null neue Abhaengigkeit, aber Trends
  und Histogramme nur per `grep | awk`.
- **B — Prometheus + Grafana, RED-Metriken.** Standard-Stack,
  `prometheus-fastapi-instrumentator` liefert Latency-Histogramme und
  Counter pro Pfad/Status frei Haus. Aufwand: 1 Instrumentator-Hook
  + 2 Compose-Services + 1 Dashboard-JSON.
- **C — Logs + Metrics + Distributed Tracing (OTel + Tempo/Jaeger).**
  Vollstaendige Request-Trace, aber +300 MB RAM und Setup-Aufwand 1d+;
  fuer ein 1-Owner-MVP uebersteuert.

## Entscheidung

**B — Prometheus + Grafana.**

- API-Modul `apps/api/src/who2be_api/core/metrics.py` mountet
  `prometheus-fastapi-instrumentator` mit
  `should_group_status_codes=True`, `excluded_handlers=["/v1/internal/.*"]`.
- Metriken werden auf `GET /v1/internal/metrics` exponiert.
- Caddy (siehe MS-3 H5) blockt `/v1/internal/*` von extern (403).
  Prometheus scraped innerhalb des Compose-Netzes ueber den
  internen Service-Namen — kein externer Port.
- Grafana laeuft im selben Compose-Netz, wird ueber Caddy unter
  `app.<domain>/grafana/` mit Basic-Auth + `Cache-Control: no-store`
  exponiert.
- Vorpaketiertes Dashboard `deploy/hetzner/grafana/dashboards/who2be-red.json`:
  Requests/s pro Pfad, P50/P95/P99-Latenz, Error-Rate pro Status-Class,
  `who2be_auth_token_attempts_total` (Trigger fuer ADR-0008).

## Konsequenzen

- Neue Dependencies: `prometheus-fastapi-instrumentator>=7` in
  `apps/api/pyproject.toml`. Keine Python-Aenderung im MCP (MCP ist
  Adapter, Metriken kommen aus API-Sicht).
- Compose-Netz wird um zwei Container reicher (Prometheus, Grafana);
  beide mit `restart: unless-stopped`, persistente Volumes
  (`prometheus-data`, `grafana-data`).
- Security-Posture: Metrics-Endpoint ist intern, Grafana per
  Basic-Auth + HTTPS. Keine Anonymous-Read-Pfade.
- Custom-Counter `who2be_auth_token_attempts_total{result="hit|miss"}`
  liefert das Mess-Signal fuer den F-04-Re-Eval-Trigger aus ADR-0008.
- Alerting bleibt out-of-scope MVP — der RED-Dashboard reicht fuer
  Human-Review; Prometheus-Alertmanager kann post-MVP nachgeschoben
  werden, ohne dass diese ADR sich aendert.
- Test-Vertrag: ein Integrationstest belegt
  `GET /v1/internal/metrics` → 200 mit `text/plain; version=0.0.4`-
  Content-Type; ein Caddy-Smoke (`tests/test_headers.sh`) belegt 403
  von extern.
</content>
</invoke>
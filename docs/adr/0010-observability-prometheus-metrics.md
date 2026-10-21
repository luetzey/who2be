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

## Nachtrag 2026-10-21 — Bisher nicht umgesetzt; Folge-ADR-0062

**Stand der Umsetzung.** Diese ADR war bis 2026-10-21 nur in einem Punkt
umgesetzt: der 403-Sperre für `/v1/internal/*` im Hetzner-Caddyfile. Es gab
kein `core/metrics.py`, keine `prometheus-fastapi-instrumentator`-Abhängigkeit,
keinen Prometheus- oder Grafana-Dienst und kein Dashboard. Die Beschreibung in
`docs/architecture.md` stellte den Stack trotzdem als laufend dar; sie ist mit
diesem Nachtrag korrigiert.

**Revision durch ADR-0062** (Owner, 2026-10-20, „wie empfohlen, Sicherheitskarte
ok“). Der Kern bleibt: RED-Metriken der API über den Instrumentator auf
`GET /v1/internal/metrics`, nie öffentlich, dazu
`who2be_auth_token_attempts_total`. Revidiert sind vier Punkte, Details in
[ADR-0062](0062-stabilitaet-fehler-tracking-waechter-alarme.md) Abschnitt 4:

1. **MCP einbezogen.** „Keine Python-Aenderung im MCP“ gilt nicht mehr; der
   MCP-Server bekommt RED-Metriken je Werkzeug.
2. **Push statt Prometheus/Grafana im Prod-Compose.** Auf Prod läuft nur ein
   Metrik-Agent, der per `remote_write` an VictoriaMetrics + Grafana auf einem
   zweiten Server (Wächter) schickt. Grafana unter `app.<DOMAIN>/grafana/`
   entfällt.
3. **Dokploy/Traefik.** Die `/v1/internal`-Sperre auf dem Stack ohne Caddy
   regelt eine eigene Sicherheitskarte; ein Metrik-Endpunkt kommt erst, wenn
   die Sperre auf jedem ausgelieferten Stack belegt ist.
4. **Alarmierung im Umfang.** „Alerting bleibt out-of-scope MVP“ gilt nicht
   mehr; Alarmwege Telegram + Mail.

Zusätzlich führt ADR-0062 Fehler-Tracking (GlitchTip, Sentry-SDK,
DSN-gesteuert), vorläufige SLOs und den Belastungstest ein. Die Umsetzung
dieser ADR folgt als Paket B2 (API) und B3 (MCP) nach dem Cloud-Release.
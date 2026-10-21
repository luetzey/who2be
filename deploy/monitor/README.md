# Waechter-Stack (Monitoring)

Compose-Stack fuer den **zweiten, kleinen Server**, der Who2Be-Prod von aussen
ueberwacht und Fehler-Events annimmt. Entscheidung und Begruendung:
[ADR-0062](../../docs/adr/0062-stabilitaet-fehler-tracking-waechter-alarme.md).
Einrichtung Schritt fuer Schritt, Alarmwege und Abnahme:
[RUNBOOK §Waechter-Server](../hetzner/RUNBOOK.md#waechter-server-monitoring-adr-0062).

Der Stack laeuft **nie** auf dem Prod-Host: faellt Prod aus, muss der Waechter
den Alarm noch senden koennen.

## Inhalt

```
deploy/monitor/
  compose.yml      # caddy, glitchtip, glitchtip-db, uptime-kuma, beszel
  Caddyfile        # errors./status./hosts.<MONITOR_DOMAIN>, Auto-HTTPS
  .env.example     # Vorlage fuer deploy/monitor/.env (nie committen)
```

| Dienst | Adresse | Zweck |
|---|---|---|
| `glitchtip` + `glitchtip-db` | `errors.<MONITOR_DOMAIN>` | Fehler-Tracking, empfaengt Events der Sentry-SDKs |
| `uptime-kuma` | `status.<MONITOR_DOMAIN>` | Checks von aussen, TLS-Ablauf, Push-Monitor fuer den Backup-Heartbeat |
| `beszel` | `hosts.<MONITOR_DOMAIN>` | Host- und Container-Werte von Prod, Agent auf Prod als systemd-Dienst |
| `caddy` | Ports 80/443 | TLS und Reverse-Proxy, einziger Dienst mit Host-Ports |

## Haertung

Gleiche Regeln wie im Prod-Stack, geprueft von
`apps/api/tests/test_monitor_compose.py`:

- An jedem Dienst Log-Deckel (3 x 10 MB), `no-new-privileges` und `mem_limit`.
  Die Summe der Deckel liegt unter 1,5 GB, damit Stufe A auf einem 2-GB-Server
  laeuft.
- Nur `caddy` veroeffentlicht Ports. `glitchtip-db` haengt nur an einem
  `internal`-Netz und ist weder vom Host noch von aussen erreichbar.
- Secrets kommen nur aus `deploy/monitor/.env`, jeweils mit `:?`-Guard. Fehlt
  ein Wert, bricht `docker compose config` ab.
- Images sind per Tag und Digest gepinnt.
- GlitchTip: Selbstregistrierung nach dem ersten Konto aus, Fehler-Events
  30 Tage (VVT V24). Beszel-Hub: keine SSH-Verbindung zu Prod, keine
  Container-Logs von Prod.
- Erster Start ohne `caddy`: die Admin-Konten aller drei Oberflaechen
  entstehen per SSH-Tunnel, bevor etwas oeffentlich erreichbar ist
  (RUNBOOK, Schritte 4–6).

## Pruefen ohne Start

```bash
cp deploy/monitor/.env.example /tmp/monitor.env
docker compose -f deploy/monitor/compose.yml --env-file /tmp/monitor.env config -q && echo ok
uv run pytest apps/api/tests/test_monitor_compose.py -q
```

## Nicht hier

- **SDKs in API, MCP und Web** (DSN, Scrubbing): Pakete A2/A3 der ADR-0062.
- **Metriken und Dashboards** (VictoriaMetrics + Grafana): Stufe B.
- **Prod-Compose und Prod-Caddyfile** bleiben unveraendert. Eine CSP-Erweiterung
  fuer die Tracker-Domain kommt gebuendelt im Infra-Paket.

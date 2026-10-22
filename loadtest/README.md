# Belastungstest-Suite (k6)

Lasttests für Who2Be nach [ADR-0062](../docs/adr/0062-stabilitaet-fehler-tracking-waechter-alarme.md)
§8 (Paket A4). Die Suite misst API und MCP-Server gegen die vorläufigen SLOs
(Weiche W8) und findet Knick- und Bruchpunkte. Ergebnisse trägt man in
[`REPORT_TEMPLATE.md`](REPORT_TEMPLATE.md) ein.

> **Nie gegen Produktion.** Die Skripte brechen ab, bevor ein Request
> rausgeht, wenn `BASE_URL` oder `MCP_URL` auf `who2be.de` oder eine Subdomain
> zeigt oder wenn `W2B_LOADTEST_CONFIRM=synthetic-non-production` fehlt.
> Daten sind ausschließlich synthetisch (Weiche W6): kein Prod-Dump, keine
> echten Personen.

## Aufbau

| Datei | Inhalt |
|---|---|
| `lib/common.js` | Prod-Schutz, Env-Konfiguration, Seed-Laden, getaggte API-Aufrufe, SLO-Schwellen, Web-Strecken (Lesen, Schreiben, Suche, Ingest, Gesundheit, Schreib-Burst) |
| `lib/mcp.js` | MCP-Client (Streamable HTTP, Token-Auth, JSON und SSE) und die Agenten-Strecke |
| `scenarios/agents.js` | T1, T2, T7, T8, T9, T10, T11: MCP-Agenten und das Gesamtsystem |
| `scenarios/web.js` | T3, T4, T5, T6: Web-Lesemix, Schreibstrecke, Suche, Ingest |
| `seed/seed.py` | Synthetische Seed-Daten über die öffentliche API (stdlib, kein uv nötig) |

Ausgaben (Seed-Datei mit Test-Tokens, Zusammenfassungen) gehören nach
`loadtest/results.local/`. Das Verzeichnis ist über `*.local` git-ignoriert.

## Voraussetzungen

- k6 ≥ 2.3. Ohne lokale Installation läuft das offizielle Image
  `docker.io/grafana/k6:2.3.0` (Beispiele unten).
- Eine **Testumgebung** mit bekanntem `JWT_SECRET`: lokal der Compose-Stack
  (`docker compose up`), für Messungen ein Server auf Zeit mit Prod-Stack
  (Bericht §4.2). k6 läuft dann auf einem **eigenen** Lastgenerator.
- In der Testumgebung: Test-Orgs auf Pro (sonst misst man das Plan-Limit statt
  der Kapazität) und fail2ban für den Lastgenerator aus. Die Limits prüft T11
  gezielt.

## Ablauf

### 1. Seed

```bash
export W2B_LOADTEST_CONFIRM=synthetic-non-production
export JWT_SECRET=...            # JWT-Secret der TESTUMGEBUNG
python3 loadtest/seed/seed.py --api-url http://localhost:8000 --profile smoke
# → loadtest/results.local/seed.json (0600, enthält gültige Test-Tokens)
```

`--profile full` legt 5 Orgs × 10 Workspaces mit je 40 Playbooks und 40
Resources, 4 Redakteuren und 4 Agent-Tokens an (Bericht §4.2: 2 000 Elemente,
200 Agent-Tokens). Jeder Workspace bekommt eine aktive Persona, einen
Agenten mit Lesezugriff auf alles und Schreibrecht in die eigene Area.

Cloud-Testumgebung (`WHO2BE_EDITION=cloud`): erst die Besitzer-IDs ausgeben,
in `WHO2BE_BILLING_OVERRIDE_OPERATORS` der Testumgebung eintragen, dann mit
`--pro-override` seeden. Dieselbe `--run-id` ergibt dieselben IDs.

```bash
python3 loadtest/seed/seed.py owners --run-id lt1 --profile full
python3 loadtest/seed/seed.py --api-url https://api.<DOMAIN> --run-id lt1 \
  --profile full --pro-override
```

Die Test-JWTs sind 12 h gültig (`--ttl-hours`).

### 2. Kurzmodus (Smoke, 1 VU je Strecke, 30 s)

```bash
cd loadtest
podman run --rm -i --network host --userns=keep-id --user "$(id -u):$(id -g)" \
  -v "$PWD:/loadtest:Z" -w /loadtest -e HOME=/tmp \
  -e BASE_URL=http://localhost:8000 -e MCP_URL=http://localhost:8765/mcp \
  -e W2B_LOADTEST_CONFIRM=synthetic-non-production \
  -e SEED_FILE=/loadtest/results.local/seed.json \
  docker.io/grafana/k6:2.3.0 run --summary-export results.local/agents-smoke.json \
  scenarios/agents.js
```

Mit Docker statt Podman: `--userns=keep-id` weglassen. Mit lokalem k6:
`k6 run -e BASE_URL=... -e SEED_FILE=$PWD/results.local/seed.json scenarios/web.js`.
`SEED_FILE` immer **absolut** angeben (k6 löst relative Pfade zur Moduldatei auf).

Im Kurzmodus gelten nur Funktionsschwellen: keine 5xx, alle Checks grün
(jede unerwartete 4xx-Antwort reißt `checks`). `THRESHOLDS=slo` erzwingt die
SLOs auch hier, `THRESHOLDS=off` schaltet alle Schwellen ab.

Der Kurzmodus von `agents.js` schickt einen Schreib-Burst über das Limit
(30/min je Token). Die Seed-JWTs sind fest, deshalb antwortet ein direkt
folgender Lauf eine Minute lang beim Schreiben mit 429 (`rate_limited`, kein
Fehler). Für saubere Zahlen eine Minute warten.

### 3. Messläufe

`PROFILE` wählt den Testfall (Bericht §4.3):

| Test | Aufruf | Erwartung |
|---|---|---|
| T1 Basislinie | `PROFILE=baseline` `agents.js` | Referenz-p50/p95 je `name` |
| T2 MCP-Agenten | `PROFILE=load` `agents.js` | bei 50 Sessions p95 `tools/call` < 500 ms, `initialize` < 300 ms |
| T3–T5 Web | `PROFILE=load` `web.js` | Lesen p95 < 300 ms, Speichern < 800 ms, Aktivieren < 1 s, Suche < 800 ms |
| T6 Ingest | `PROFILE=ingest` `web.js` | kein OOM im `api`, Lesen p95 < 2 × Basislinie (`READ_P95_LIMIT`) |
| T7 Dauerlast | `PROFILE=soak SOAK_VUS=<50 % Knick>` `agents.js` | RAM-Drift < 1 MiB/min |
| T8 Spitze | `PROFILE=spike` `agents.js` | nur 429/503, kein Neustart, Erholung < 2 min |
| T9 Bruchpunkt | `PROFILE=breakpoint` `agents.js` | Abbruch dokumentieren: VUs, Zeit, Komponente |
| T10 Teilausfall | `PROFILE=outage` `agents.js` | nach Neustart von `api`, dann `db`: Erholung < 60 s |
| T11 Limits | `PROFILE=limits` `agents.js` | 429 statt 5xx |

Weitere Schalter: `DURATION`, `THINK_MIN`/`THINK_MAX` (Denkzeit in s),
`REQUEST_TIMEOUT`, `INGEST_MB`, `SOAK_VUS`, `SOAK_DURATION`, `BREAKPOINT_VUS`,
`BREAKPOINT_DURATION`, `BURST`.

Neben jedem Messlauf auf dem **Zielserver** mitschreiben:

```bash
docker stats --format '{{.Name}};{{.CPUPerc}};{{.MemUsage}}' >> stats.csv  # Takt ≈ 1 s
docker events --filter event=die --filter event=oom                        # Neustarts, OOM
```

Bei T10 zur festen Minute `docker compose restart api`, nach der Erholung
`docker compose restart db`. Die Erholungszeit liest man an `health_ok` und an
den `errors` je Sekunde ab (`--out json=results.local/t10.json`).

## Metriken und Tags

Jeder Request trägt `kind` (Strecke, für die SLO-Schwellen) und `name`
(Routen-Vorlage ohne IDs). Eigene Metriken:

| Metrik | Bedeutung |
|---|---|
| `errors` | Anteil 5xx und Verbindungsfehler (Fehlerbudget < 0,5 %, 429 zählt nicht) |
| `rate_limited` | 429-Antworten: gewolltes Überlastverhalten |
| `conflicts` | 409 bei konkurrierendem Schreiben |
| `skipped` | Strecke in der Umgebung nicht verfügbar (Ingest ohne Blob-Store) |
| `mcp_session_failures` | `initialize` ohne Session |
| `mcp_tool_errors` | Werkzeug-Antwort mit `isError` |
| `mcp_tool_rate_limited` | Werkzeug-Fehler mit Limit-Hinweis |
| `health_ok` | Anteil erfolgreicher `GET /v1/health` (T10) |

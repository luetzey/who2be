# Belastungstest-Bericht: <Datum>

Vorlage zu [`README.md`](README.md). Kopie nach `results.local/` oder in die
private Ablage, dort ausfüllen; nur die bereinigte Fassung (ohne Hosts, IPs und
Tokens) gehört in ein Issue oder ADR.

## Umgebung

| Punkt | Wert |
|---|---|
| Commit / Image-Tags | |
| Zielserver (Typ, vCPU, RAM) | |
| Lastgenerator (Typ, Standort) | |
| Edition, Plan der Test-Orgs | |
| Seed (`--profile`, `--run-id`, Elemente) | |
| k6-Version | |
| Besonderheiten (fail2ban aus, Embeddings an/aus, Blob-Store) | |

## SLO-Abgleich (ADR-0062 §7, Bericht §4.5, vorläufig nach W8)

| Dienst | SLI | Ziel | Gemessen | Test | Erfüllt |
|---|---|---|---|---|---|
| Verfügbarkeit `app.`, `api.`, `mcp.` | erfolgreiche externe Checks | 99,5 %/Monat | (Wächter, nicht k6) | – | |
| API lesend | p95 / p99 | < 300 ms / < 1 s | | T3 | |
| API schreibend (Speichern, Aktivieren) | p95 | < 800 ms | | T4 | |
| Suche | p95 | < 800 ms | | T5 | |
| MCP `tools/call` | p95 / p99 | < 500 ms / < 1,5 s | | T2 | |
| MCP `initialize` + `tools/list` | p95 | < 500 ms | | T2 | |
| Fehlerquote | 5xx-Anteil ohne 429 | < 0,5 % | | alle | |

Empfehlung zu W8: Ziele bestätigen, verschärfen (Basislinie deutlich besser)
oder Arbeitsauftrag (Basislinie schlechter):

## Ergebnisse je Testfall

| Test | Profil | Ergebnis | Knick / Auffälligkeit |
|---|---|---|---|
| T1 Basislinie | `baseline` | p50/p95 je `name` | |
| T2 MCP-Agenten | `load` | p95 bei 10 / 50 / 100 Sessions | |
| T3 Lesemix | `load` (web) | p95 bei 20 / 100 VUs | |
| T4 Schreiben | `load` (web) | p95 Speichern / Aktivieren | |
| T5 Suche | `load` (web) | p95 bei 5 / 30 req/s | |
| T6 Ingest | `ingest` (web) | RAM-Spitze `api`, Lesen p95 | |
| T7 Dauerlast | `soak` | RAM-Drift `api`/`mcp` MiB/min, DB-Verbindungen | |
| T8 Spitze | `spike` | 429/503-Anteil, Neustarts, Erholungszeit | |
| T9 Bruchpunkt | `breakpoint` | VUs und Zeit beim Abbruch, Komponente | |
| T10 Teilausfall | `outage` | Erholung nach `api` / `db` (s), MCP-Fehlerbild | |
| T11 Limits | `limits` | 429 statt 5xx, fail2ban | |

## Engpässe (Bericht §4.4)

| Hypothese | Bestätigt? | Beleg (Metrik, Log, `docker stats`) |
|---|---|---|
| | | |

## Folgearbeiten

- [ ] …

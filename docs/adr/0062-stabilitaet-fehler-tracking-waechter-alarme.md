# ADR-0062 — Stabilität: Fehler-Tracking mit GlitchTip, Wächter-Server, MCP-Metriken, Alarme, SLOs

- Status: **Accepted** (Owner, 2026-10-20). Die Entscheidung steht im Wortlaut
  in Abschnitt 2.
- Datum: 2026-10-21
- Gemessen gegen: `origin/main` @ `de53f9d5`. Code-Aussagen tragen einen
  Symbolanker (Konvention `docs/code-references.md`).
- Grundlage: Recherchebericht „Stabilität der Who2Be-Cloud: Fehler-Tracking,
  Monitoring, Belastungstest“ (Karte t_77209d97, Stand 2026-10-20, außerhalb
  des Repos). „Bericht §n“ verweist auf dessen Abschnitte. Diese ADR entsteht
  auf Kanban-Karte t_9192f039 (Stabilität, Paket A0).
- Bezug: **ADR-0010** (Observability, Prometheus-Metriken über
  `/v1/internal`; diese ADR ist ihre Folge-ADR und revidiert sie teilweise,
  siehe Abschnitt 4), ADR-0007 (strukturierte Logs), ADR-0011 (Backup,
  Dead-Man's-Switch), ADR-0049 (genau ein API-Prozess), ADR-0057 (Worker,
  Laufprotokoll), ADR-0033 (OSS-Lizenzen).
- Umfang: **nur Dokumentation.** Diese ADR ändert keinen Code, kein Compose,
  kein Caddyfile und kein RUNBOOK. Umsetzung in den Paketen A1 bis A6 und
  B1 bis B7 (Abschnitt 9).

## Inhalt

1. Kontext und Befund
2. Entscheidung (Owner-Wortlaut)
3. Fehler-Tracking: GlitchTip über das Sentry-SDK
4. Verhältnis zu ADR-0010
5. Wächter-Server und Push-Architektur
6. Alarmwege
7. SLOs (vorläufig)
8. Belastungstest
9. Umsetzung in Paketen (Stufe A und B)
10. Verworfene Optionen
11. Konsequenzen

## 1. Kontext und Befund

Der Owner fragte am 2026-10-20, wie vor dem Cloud-Release ein richtiger
Belastungstest aussieht und ob dafür Sentry oder Grafana nötig ist. Die
Antwort des Berichts (§0): Es braucht beides, weil die Werkzeuge verschiedene
Fragen beantworten.

- **Fehler-Tracking** zeigt, *wo* es knallt: Stacktrace, Datei, Zeile,
  betroffene Route oder betroffenes MCP-Werkzeug.
- **Metriken und Alarme** zeigen, *wann und wie stark* es knallt: Latenz,
  Fehlerquote, RAM, Platte, Neustarts.
- Der **Belastungstest** liefert die Zahl, ab der es knallt. Ohne die ersten
  beiden Bausteine sieht man dabei nur „Timeout“.

### 1.1 ADR-0010 war bisher nicht umgesetzt

ADR-0010 steht seit 2026-05-26 auf „Akzeptiert“, umgesetzt ist sie bis heute
nur in einem Punkt: die 403-Sperre für `/v1/internal/*` im Hetzner-Caddyfile
(`deploy/hetzner/Caddyfile`, Matcher `@internal` und `@internal_alt`). Es
fehlen (Bericht §1, im Repo nachgesehen):

- das Modul `apps/api/src/who2be_api/core/metrics.py`,
- die Abhängigkeit `prometheus-fastapi-instrumentator` in
  `apps/api/pyproject.toml`,
- jeder Prometheus- oder Grafana-Dienst in einer Compose-Datei,
- das Dashboard unter `deploy/hetzner/grafana/`.

Auch `docs/architecture.md` beschrieb den Metrik-Stack bis zu dieser ADR so,
als liefe er. Heute gibt es in Who2Be weder Metriken noch Fehler-Tracking noch
Alarme außer dem Backup-Dead-Man's-Switch aus ADR-0011.

### 1.2 Weitere Befunde, die die Lösung begrenzen

- **Kein Fehler-Tracking.** Keine `sentry`- oder `glitchtip`-Abhängigkeit in
  `apps/*/pyproject.toml` oder `apps/web/package.json`. Das Web meldet Fehler
  nur per `console.error`
  (`apps/web/src/app/RouteErrorBoundary.tsx#ErrorBoundaryImpl`). Source-Maps
  sind nicht konfiguriert (`apps/web/vite.config.ts`).
- **CSP.** `connect-src` im Caddyfile erlaubt heute keinen externen
  Fehler-Tracker. Ein Web-SDK braucht also eine Infra-Änderung (Weiche W7).
- **ADR-0010 schließt den MCP-Server aus** („Keine Python-Aenderung im MCP“).
  Der MCP-Server ist aber die Strecke, über die Agenten arbeiten, und jeder
  Werkzeugaufruf erzeugt dort mindestens zwei API-Aufrufe
  (`apps/mcp/src/who2be_mcp/auth.py#Who2BeTokenVerifier`,
  `apps/mcp/src/who2be_mcp/client.py#ApiClient`). Aus API-Sicht allein ist
  nicht erkennbar, welches Werkzeug langsam ist.
- **Ein API-Prozess.** `--workers` ist per Start-Guard verboten (ADR-0049).
  Die gesamte API teilt sich eine Event-Loop.
- **DB-Pool ohne Grenzen und Timeouts.** `asyncpg.create_pool` ohne
  `max_size`, Acquire-Timeout und `command_timeout`
  (`apps/api/src/who2be_api/core/db.py#Database.connect`).
- **Alarm-Grundsatz im RUNBOOK.** Der Empfänger des Backup-Heartbeats soll
  self-hosted auf einer **zweiten, unabhängigen Maschine** laufen, kein
  gehosteter Dienst, weil der ein neuer Auftragsverarbeiter wäre
  (`deploy/hetzner/RUNBOOK.md` §Alarmweg (Dead-Man's-Switch)).
- **Speicherbudget.** Auf dem Prod-Server sind laut RUNBOOK etwa 6,2 von 8 GB
  belegt. Ein Metrik-Stack auf derselben Maschine kostet etwa 0,4–0,5 GB und
  stirbt mit dem Überwachten (Bericht §3.3).

## 2. Entscheidung (Owner-Wortlaut)

Owner-Entscheidung vom 2026-10-20 (Telegram, wörtlich): **„wie empfohlen,
Sicherheitskarte ok“**. Damit gelten die Empfehlungen aus Bericht §6, im
Wortlaut der Karte:

- **W1 = a:** GlitchTip selbst gehostet (Wechsel zu Sentry später per DSN).
- **W2 = ja:** zweiter Hetzner-Server als Wächter (6–10 €/Monat).
- **W3:** VictoriaMetrics + Grafana auf dem Wächter (Stufe B).
- **W4:** Telegram für Dringendes + Mail für alles.
- **W5:** Stufe A vor dem Cloud-Release (Ende November), Stufe B danach.
- **W6:** nur synthetische Testdaten.
- **W7:** CSP `connect-src` um die Tracker-Domain erweitern (Caddy/Compose
  nur mit Owner-Go, gebündelt in einem Infra-Paket).
- **W8:** SLOs aus Bericht §4.5 vorläufig übernehmen und nach dem Testlauf
  bestätigen.

„Sicherheitskarte ok“ bezieht sich auf den Nebenbefund, dass der
Dokploy-Stack kein Caddy hat und deshalb dort die `/v1/internal`-Sperre, die
Speicherdeckel und fail2ban fehlen. Das ist eine **eigene Karte** außerhalb
dieser ADR (Abschnitt 4.3).

## 3. Fehler-Tracking: GlitchTip über das Sentry-SDK

### 3.1 Entscheidung

- **GlitchTip, selbst gehostet auf dem Wächter-Server** (Abschnitt 5).
  GlitchTip steht unter MIT-Lizenz und spricht das Sentry-Protokoll.
- Angebunden werden API, MCP-Server und Web über die **offiziellen
  Sentry-SDKs** (`sentry-sdk` für Python, `@sentry/react` für das Web).
- **DSN-gesteuert.** Die Ziel-Adresse kommt ausschließlich aus einer
  Env-Variable. Ist sie leer, bleibt das SDK aus. On-Prem-Installationen
  bemerken dadurch nichts, und ein Wechsel zu Sentry SaaS ist ein DSN-Tausch
  ohne Code-Änderung (dann mit VVT-Eintrag und AVV, siehe Abschnitt 10).
- Der Name der Env-Variable und die Verdrahtung legen die Pakete A2 und A3
  fest, nicht diese ADR.

### 3.2 Datenschutz-Vorgaben für jedes SDK (Bericht §2.2)

Diese Vorgaben sind Teil der Entscheidung. Ein Paket, das ein SDK einbindet,
muss sie mit Tests belegen.

- `send_default_pii=False` bzw. `sendDefaultPii: false`: keine IP, keine
  Cookies, kein Nutzerobjekt.
- Eigene Denylist im Scrubber (mindestens `authorization`, Token-Präfix
  `w2b_`, `jwt`, `email`, `content`, `markdown`, `body`), rekursiv, dazu
  `before_send` bzw. `beforeSend` als letzte Schranke.
- Python: `include_local_variables=False`, weil in Stack-Locals
  Element-Inhalte und Tokens liegen können.
- MCP: Die MCP-Integration des SDK nur mit `include_prompts=False`.
  Werkzeug-Argumente und -Ergebnisse (Playbook- und Persona-Inhalte) sind
  Nutzerdaten und gehen nicht an den Tracker.
- Web: keine Session-Replays; `beforeSend` entfernt Query-Strings (OAuth-
  `code`, `token`), analog zur Log-Redaktion im RUNBOOK.
- Source-Maps werden beim Build hochgeladen und **nicht ausgeliefert**
  (`sourcemap: "hidden"`).
- Aufbewahrung der Fehler-Events: Die Frist legt Paket A1 im VVT fest
  (Bericht §2.2 schlägt 30–90 Tage vor).

### 3.3 Was man aufgibt

GlitchTip hat nicht die MCP-Auswertung von Sentry SaaS (Latenz und
Fehlerquote je Werkzeug). Diese Lücke schließt Stufe B mit eigenen Metriken
je Werkzeug (Abschnitt 4.1, Paket B3).

## 4. Verhältnis zu ADR-0010

ADR-0010 bleibt in ihrem Kern gültig: RED-Metriken (Rate, Errors, Duration)
der API über `prometheus-fastapi-instrumentator`, exponiert auf
`GET /v1/internal/metrics`, nie öffentlich, dazu der Zähler
`who2be_auth_token_attempts_total` für ADR-0008. Diese ADR **revidiert**
ADR-0010 in den folgenden Punkten.

### 4.1 MCP-Server einbezogen

Der Satz „Keine Python-Aenderung im MCP“ gilt nicht mehr. Der MCP-Server
bekommt eigene RED-Metriken: Zähler und Latenz-Histogramm **je Werkzeug** und
die Zahl offener Sessions (Paket B3). Labels tragen nur Werkzeugnamen und
Route-Vorlagen, nie IDs, Token oder Inhalte. Damit enthalten die Metriken
keine personenbezogenen Daten.

### 4.2 Push statt Scrape im selben Netz; Ablage auf dem Wächter

ADR-0010 sah Prometheus und Grafana als zwei Dienste im Prod-Compose vor,
Grafana über Caddy unter `app.<DOMAIN>/grafana/`. Das entfällt (Weiche W3):

- Auf dem Prod-Server läuft nur ein kleiner Metrik-Agent (vmagent oder
  Grafana Alloy). Er liest `/v1/internal/metrics` im internen Netz und
  schickt per `remote_write` **nach außen** an VictoriaMetrics auf dem
  Wächter.
- **VictoriaMetrics (single-node) und Grafana laufen auf dem Wächter**, nicht
  auf Prod. VictoriaMetrics spricht die Prometheus-API, Grafana bleibt
  unverändert nutzbar.
- Kein eingehender Metrik-Port auf Prod, kein Grafana hinter dem
  Prod-Caddy. Das Dashboard aus ADR-0010 zieht auf den Wächter um.
- Der Metrik-Agent ist eine Compose-Änderung und gehört deshalb in Paket B4
  mit Owner-Go; der Speicherbudget-Test
  (`apps/api/tests/test_compose_hardening.py`) wird dort angepasst.

### 4.3 `/v1/internal` auf dem Dokploy-Stack

ADR-0010 verlässt sich für die Sperre auf Caddy. Der Dokploy-Stack hat kein
Caddy, Routing und TLS übernimmt Traefik. Die Sperre dort regelt die
Sicherheitskarte, die der Owner mit „Sicherheitskarte ok“ freigegeben hat
(PR #1003, bei Abfassung offen: Sperre zusätzlich in der App, Härtung des
Dokploy-Stacks). Diese
ADR legt dafür nichts fest. Für die Metrik-Pakete gilt: Ein Metrik-Endpunkt
wird erst gebaut, wenn die Sperre auf **jedem** ausgelieferten Stack belegt
ist.

### 4.4 Alarmierung jetzt im Umfang

ADR-0010 schob Alarme auf „post-MVP“. Mit dem Cloud-Release gilt das nicht
mehr: Ohne Alarm bleibt ein Ausfall in Prod unbemerkt. Alarme sind Teil von
Stufe A (Erreichbarkeit, Host, Container, Fehler-Tracking) und Stufe B
(RED-Schwellen). Siehe Abschnitt 6.

## 5. Wächter-Server und Push-Architektur

### 5.1 Entscheidung

Ein **zweiter, kleiner Hetzner-Server** (Weiche W2, etwa 6–10 €/Monat) ist
der unabhängige Wächter. Er erfüllt den RUNBOOK-Grundsatz „Empfänger
self-hosted auf zweiter Maschine“ und bündelt drei Aufgaben, die heute
niemand erledigt:

| Stufe | Dienst | Aufgabe |
|---|---|---|
| A | GlitchTip (mit eigenem Postgres) | Fehler-Tracking für API, MCP, Web |
| A | Uptime Kuma | Erreichbarkeit von außen, TLS-Ablauf, Push-Monitore für Backup- und Worker-Heartbeat |
| A | Beszel-Hub | Host- und Container-Werte von Prod (RAM je Container, Neustarts, Platte) |
| B | VictoriaMetrics + Grafana | RED-Metriken von API und MCP, Dashboards, Alarmregeln |

Größe nach Bericht §3.4: Stufe A kommt mit etwa 1 GB RAM aus (kleinster Typ
reicht), Stufe B mit etwa 1,5 GB (nächstgrößerer Typ komfortabel). Der Typ
wird bei der Einrichtung gewählt, nicht hier.

### 5.2 Richtung der Verbindungen

- **Prod schickt, der Wächter empfängt.** Fehler-Events (SDK), Metriken
  (Agent, Stufe B) und Heartbeats (Backup-Skript, Worker) gehen von Prod nach
  außen zum Wächter.
- Der Wächter prüft Prod nur dort von außen, wo es auch ein Nutzer täte:
  HTTP-Checks auf `app.<DOMAIN>`, `api.<DOMAIN>/v1/health` und eine
  MCP-Initialize-Probe auf `mcp.<DOMAIN>`.
- Der Beszel-Agent auf Prod läuft als **Host-Dienst**, nicht im
  Prod-Compose (Paket A1).
- Auf dem Wächter sind Datenbanken nicht öffentlich erreichbar, Secrets
  kommen nur per Env (Akzeptanzkriterien von Paket A1).

### 5.3 Betrieb

- Eingerichtet wird der Wächter **vom Owner**; Agenten liefern Doku, eigenen
  Compose-Stack und eine nummerierte Schrittliste (Paket A1).
- Der Wächter braucht ein eigenes Backup für die GlitchTip-Konfiguration.
  Die Fehler-Events selbst sind entbehrlich.
- Fällt der Wächter aus, läuft Prod unverändert weiter: Alle SDKs und Agenten
  verwerfen Daten, die sie nicht loswerden, statt zu blockieren. Das belegen
  die Pakete A2 und A3 mit Tests.

## 6. Alarmwege

Weiche W4: **Telegram für Dringendes, Mail für alles.** Ein eigener Bot mit
einem privaten Chat genügt. Nachrichten nennen nur Dienstnamen und
Schwellen, keine Nutzerdaten. Mail läuft über den SMTP-Zugang, den die Cloud
ohnehin braucht.

Vorläufige Schwellen (Bericht §3.5). Die endgültigen Werte setzt das
jeweilige Paket; Abweichungen werden dort begründet.

| Alarm | Schwelle | Kanal | Stufe |
|---|---|---|---|
| `app.`/`api.`/`mcp.` nicht erreichbar | 2 Fehlchecks in Folge (≈ 1 min) | Telegram + Mail | A |
| TLS-Zertifikat läuft ab | < 14 Tage | Mail | A |
| Backup-Heartbeat aus | > 26 h (wie RUNBOOK) | Telegram + Mail | A |
| Worker-Heartbeat aus | > 2× längstes Routinenintervall | Mail | A |
| Platte | > 80 % Warnung, > 90 % kritisch | Telegram | A |
| Host-RAM | > 90 % für 5 min | Telegram | A |
| Container neu gestartet / OOM | jedes Ereignis | Telegram | A |
| Neuer Fehler-Typ (GlitchTip) | erstes Auftreten, danach gebündelt | Mail | A |
| 5xx-Quote API/MCP | > 1 % über 5 min | Telegram | B |
| p95-Latenz | > 2× SLO über 10 min | Mail | B |
| DB-Verbindungen | > 80 % von `max_connections` | Telegram | B |

## 7. SLOs (vorläufig)

Weiche W8: Die Ziele aus Bericht §4.5 gelten **vorläufig**. Sie werden nach
dem ersten Testlauf (Paket A5, Szenarien T1–T3) bestätigt, verschärft oder
als Arbeitsauftrag behandelt. Die Bestätigung kommt als Nachtrag zu dieser
ADR.

| Dienst | SLI | Ziel (vorläufig) |
|---|---|---|
| Verfügbarkeit `app.`, `api.`, `mcp.` | Anteil erfolgreicher externer Checks (1-min-Takt) | 99,5 %/Monat (≈ 3,6 h Budget; Neustarts durch Auto-Deploy zählen mit) |
| API lesend | p95 / p99 | < 300 ms / < 1 s |
| API schreibend (Speichern, Aktivieren) | p95 | < 800 ms |
| Suche | p95 | < 800 ms |
| MCP `tools/call` (`get_persona`, `fetch_playbook`) | p95 / p99 | < 500 ms / < 1,5 s |
| MCP `initialize` + `tools/list` | p95 | < 500 ms |
| Fehlerquote | 5xx-Anteil (ohne 429) | < 0,5 % je Tag |

Gemessen wird die Verfügbarkeit in Stufe A über Uptime Kuma, die Latenzen ab
Stufe B über die RED-Metriken. Bis dahin liefert nur der Belastungstest
Latenzwerte.

## 8. Belastungstest

- Werkzeug **k6** (Bericht §4.1). k6 steht unter AGPL-3.0, wird aber nur
  intern als Werkzeug ausgeführt und nicht weitergegeben oder ausgeliefert;
  es ist keine Abhängigkeit eines Who2Be-Artefakts (ADR-0033). Bericht §4.1
  wertet die Wahl gegenüber Locust als Geschmacksfrage, keine Owner-Weiche.
- **Nie gegen Prod.** Ziel ist ein Server auf Zeit desselben Typs und
  desselben Stack-Wegs wie Prod, der Lastgenerator läuft auf einem eigenen
  Server. Beide werden nach dem Lauf gelöscht.
- **Nur synthetische Testdaten** (Weiche W6), angelegt per Seed-Skript; keine
  Kopie von Prod-Daten, auch keine anonymisierte.
- Testfälle T1–T11 und Engpass-Hypothesen H1–H10 stehen in Bericht §4.3 und
  §4.4; die Suite (Paket A4) übernimmt sie ins Repo.

## 9. Umsetzung in Paketen (Stufe A und B)

Weiche W5: **Stufe A vor dem Cloud-Release (Ende November), Stufe B danach.**
Der Paketschnitt folgt Bericht §5. Compose- und Caddyfile-Änderungen liegen
nur in den dafür benannten Paketen und brauchen ein Owner-Go (Weiche W7).

### Stufe A (vor dem Release)

| Paket | Inhalt |
|---|---|
| A0 | diese ADR |
| A1 | Wächter-Stack: `deploy/monitor/` (README, eigener Compose), RUNBOOK-Abschnitt, Backup-Heartbeat auf den Wächter, Beszel-Agent als Host-Dienst, VVT-Frist für Fehler-Events |
| A2 | Fehler-Tracking Backend: Sentry-SDK in API und MCP nach Abschnitt 3 |
| A3 | Fehler-Tracking Web: `@sentry/react`, `RouteErrorBoundary` meldet, versteckte Source-Maps |
| Infra | gebündelte Compose-/Caddy-Änderungen aus A2/A3 (DSN-Env, CSP `connect-src`), **ein** Owner-Go |
| A4 | Belastungstest-Suite (k6, Seed, Anleitung, Berichtsvorlage) |
| A5 | Testlauf auf Servern auf Zeit, Ergebnisbericht; danach Bestätigung der SLOs (Abschnitt 7) |
| A6 | Härtung DB-Pool und MCP-Client (Pool-Größe, Timeouts, gemeinsamer HTTP-Client, Introspektions-Cache), **nach** der A5-Baseline |

### Stufe B (nach dem Release)

| Paket | Inhalt |
|---|---|
| B1 | ADR-0010-Nachtrag. Durch diese ADR erledigt: Die Punkte des Berichts (MCP, Push-Architektur, Dokploy-Sperre, Alarmierung) stehen in Abschnitt 4 |
| B2 | RED-Metriken API nach ADR-0010, dazu Pool-Gauges und Event-Loop-Lag |
| B3 | RED-Metriken MCP je Werkzeug, offene Sessions (Abschnitt 4.1) |
| B4 | Metrik-Stack: Agent auf Prod (Compose, Owner-Go) → VictoriaMetrics + Grafana auf dem Wächter; postgres_exporter |
| B5 | SLO-Dashboard und Alarmregeln (Abschnitte 6 und 7) |
| B6 | Regelmäßiger kurzer Last-Smoke (T1/T2) vor größeren Releases |
| B7 | Tracing (optional), nur wenn B2/B3 nicht reichen |

Die Pakete legt der PM als eigene Karten an; diese Liste ist ein Verweis,
keine Spezifikation.

## 10. Verworfene Optionen

### Fehler-Tracker (Weiche W1, Bericht §2.1)

- **Sentry SaaS (EU).** Bester Funktionsumfang, inklusive eigener
  MCP-Auswertung. Verworfen für den Start, weil Sentry ein neuer
  Auftragsverarbeiter wäre: DPA erlaubt Verarbeitung in den USA,
  Subprozessoren u. a. in den USA, VVT-Eintrag nötig; ab der zweiten Person
  kostenpflichtig. Bleibt per DSN-Tausch erreichbar.
- **GlitchTip gehostet (EU).** Datenort Deutschland, aber ebenfalls ein neuer
  Auftragsverarbeiter mit Vertrag; kein Vorteil gegenüber dem Eigenbetrieb
  auf dem ohnehin nötigen Wächter.
- **Bugsink.** Leichtgewichtig und Sentry-SDK-kompatibel, aber unter
  PolyForm Shield 1.0.0 (source-available, keine OSI-Lizenz); ohne Tracing.
- **Sentry self-hosted.** Nicht vertieft; für ein 8-GB-System erfahrungsgemäß
  zu schwer (Kafka, ClickHouse u. a.).
- **Highlight.io.** Am 2026-02-28 eingestellt, nicht mehr wählbar.

### Wächter (Weiche W2)

- **Alles auf dem Prod-Server.** Spart etwa 6–10 €/Monat, aber Wächter und
  Überwachtes sterben gemeinsam; bei Totalausfall kommt kein Alarm. Das
  widerspricht dem RUNBOOK-Grundsatz.

### Metrik-Ablage (Weiche W3, Bericht §3.3)

- **Prometheus + Grafana auf Prod (ADR-0010 wörtlich).** Kostet etwa
  0,5 GB RAM im ohnehin knappen Budget und alarmiert nicht bei Totalausfall.
- **Grafana Cloud Free.** Am bequemsten, aber ein weiterer Auftragsverarbeiter
  (USA-Konzern), widerspricht dem RUNBOOK-Grundsatz.
- **Netdata.** Nicht vertieft; RAM-hungriger als Beszel, der Cloud-Teil wäre
  ein weiterer Dienstleister.

### Weitere Weichen

- **W4 nur Mail:** zu langsam für Ausfälle in der Nacht.
- **W5 alles nach dem Release:** Ohne Stufe A wäre ein Absturz in Prod
  unsichtbar.
- **W6 anonymisierte Prod-Kopie:** DSGVO, Löschfristen und VVT; für einen
  Lasttest nicht nötig.
- **W7 Tunnel über die eigene API statt CSP-Erweiterung:** kostet API-Last
  und eigenen Code für eine Zeile CSP.
- **W8 SLOs erst nach dem Test festlegen:** Ohne vorläufige Ziele hat der
  Test kein Abbruchkriterium.
- **Variante „Voll“ (Bericht §0):** Sentry SaaS mit Tracing plus
  Prometheus/Alertmanager/Loki und OpenTelemetry. Übersteuert für einen
  Einzelserver, ggf. mit Prod-Upgrade; Tracing bleibt als B7 optional.

## 11. Konsequenzen

- ADR-0010 bekommt einen Nachtrag mit Verweis auf diese ADR. Ihr Status
  bleibt „Akzeptiert“, revidiert in den Punkten aus Abschnitt 4.
- `docs/architecture.md` beschreibt den Metrik-Stack nicht mehr als laufend,
  sondern verweist auf ADR-0010 und diese ADR.
- Neue laufende Kosten: ein Wächter-Server, etwa 6–10 €/Monat, dazu etwa 1 €
  je Testtag für Server auf Zeit.
- Neuer Betriebsaufwand: ein zweiter Server mit eigenem Backup, gepflegt vom
  Owner.
- Kein neuer Auftragsverarbeiter: Wächter und Testserver laufen bei Hetzner,
  das schon im VVT steht. Neu im VVT ist nur die Frist für Fehler-Events
  (Paket A1).
- Neue Abhängigkeiten kommen erst mit den Paketen (Sentry-SDKs, MIT) und
  durchlaufen dort das Lizenz-Gate (ADR-0033).
- On-Prem bleibt unberührt: ohne DSN kein Fehler-Tracking, ohne Wächter keine
  Alarme. Der Betreiber kann beides mit eigenen Zielen einschalten.
- Offen und außerhalb dieser ADR: Bestätigung der SLOs nach Paket A5
  (Nachtrag) und die Härtung des Dokploy-Stacks (Sicherheitskarte).

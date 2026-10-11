# ADR-0057 — Hintergrund-Routinen im Worker (eigener Dienst, Registry im Code, Laufprotokoll in Postgres)

- Status: **Accepted** (Owner, 2026-10-08). Die Entscheidung steht im Wortlaut
  in Abschnitt 2.
- Datum: 2026-10-09
- Gemessen gegen: `origin/main` @ `46ecbf52`. Code-Aussagen tragen einen
  Symbolanker (Konvention `docs/code-references.md`).
- Grundlage: Entscheidungsvorlage „Hintergrund-Routinen als eingebauter Worker
  statt Dokploy/Crontab“ (Karte t_ce217209, Stand 2026-10-08, außerhalb des
  Repos). „Vorlage §n“ verweist auf deren Abschnitte. Diese ADR entsteht auf
  Kanban-Karte t_19fc29c9 (Worker-Welle P0).
- Bezug: ADR-0049 (Tabellen-Store, Betriebsgrenze genau ein API-Container,
  Nachträge 2026-08-16 und 2026-09-26), ADR-0053 (Lernschleife, Verfall
  unbestätigten Gedächtnisses §3.1.3), ADR-0054 (Orchestrator, Who2Be ist kein
  Runtime-Host), ADR-0029 (Billing build-zeit-isoliert), ADR-0010
  (Observability).
- Umfang: **nur Dokumentation.** Diese ADR ändert keinen Code, kein Compose
  und kein RUNBOOK. Umsetzung in den Paketen P1 bis P6 (Abschnitt 9).

## Inhalt

1. Kontext und Befund
2. Entscheidung (Owner-Wortlaut)
3. Der Dienst `worker`
4. Registry und Zeitpläne
5. Genau ein Lauf: Slot-Claim und Advisory-Lock
6. Nachholen, Heartbeat, abgebrochene Läufe
7. Sichtbarkeit nur für Betreiber
8. Migrationspfad: externe Zeitpläne, CLIs bleiben
9. Umsetzung in Paketen
10. Abgrenzung zu ADR-0054 und ADR-0049
11. Ausbaupfad: pgqueuer
12. Verworfene Optionen
13. Konsequenzen

## 1. Kontext und Befund

Who2Be hat heute zwei wiederkehrende Routinen. Beide sind idempotent, laufen
über die Owner-Verbindung `DATABASE_URL` (RLS-Bypass) und nehmen einen
`now`-Parameter, sind also mit fester Uhr testbar:

- `who2be-purge`: DSGVO-Hard-Purge plus die Sweeps für WorkArea und KB
  (`apps/api/src/who2be_api/core/purge.py#run_retention_sweeps`).
- `who2be-memory-expire`: Verfall unbestätigten Gedächtnisses nach ADR-0053
  §3.1.3 (`apps/api/src/who2be_api/core/memory_expiry.py#expire_unconfirmed_memories`).

Ausgelöst werden sie außerhalb von Who2Be:

- Hetzner: Host-Crontab mit `docker compose … run --rm --no-deps api …`
  (`deploy/hetzner/RUNBOOK.md` §Retention-Cron).
- Dokploy: Compose-Schedules, die per `docker exec` in den laufenden
  api-Container gehen (`docs/cloud-erstinbetriebnahme.md` §Hintergrundjobs auf
  Dokploy einplanen, Checkliste 10b).
- Lokal: gar nicht.

Jeder Betreiber muss also selbst Hand anlegen. Vergisst er es, läuft weder der
Purge noch der Verfall, und niemand sieht es. Die ersten Verfälle nach
ADR-0053 sind am 2026-11-06 fällig.

Absehbar sind fünf bis zehn Zeitplan-Routinen (Purge, Verfall, Aufräumen des
eigenen Protokolls, eventuell ein Retrieval-Backfill-Nachtlauf, ein
Mollie-Abgleich) und **kein** Queue-Bedarf (Vorlage §1). Der erste echte
Queue-Fall wäre ein eigener Mail-Versand mit Retry; den gibt es nicht.

Zwei Klarstellungen aus der Vorlage (§0 Punkt 4 und 5), weil sie die Lösung
begrenzen:

- Das Redis in `docs/architecture.md` ist Speicher für das Rate-Limiting im
  Cloud-Overlay (`apps/api/src/who2be_api/core/rate_limit.py`), kein
  Job-Backend. On-Prem gibt es kein Redis.
- Procrastinate hängt an psycopg (LGPL-3.0-only), Dramatiq ist selbst
  LGPLv3+. Das Lizenz-Gate in der CI (`piplicenses --fail-on`) lehnt beide ab.

## 2. Entscheidung (Owner-Wortlaut)

Owner-Entscheidung vom 2026-10-08 (Telegram, wörtlich „1.a, 2.a, 3.a, 4.a“)
zu den Weichen in Vorlage §7. Übernommen im Wortlaut der Karte:

- **W1 Mechanismus = a:** eigener Compose-Dienst `worker` (gleiches Image wie
  api, Befehl `who2be-worker`), Routinen-Registry im Code, Laufprotokoll in
  Postgres (`routine_run`), genau ein Lauf über UNIQUE(routine, slot) plus
  Advisory-Lock. Einzige neue Abhängigkeit `croniter` (MIT). Kein Redis, keine
  Queue-Bibliothek. pgqueuer ist der Ausbaupfad beim ersten echten
  Queue-Fall. Procrastinate und Dramatiq sind ausgeschlossen (LGPL).
- **W2 Sichtbarkeit = a:** nur Betreiber (Cloud: Allowlist wie
  `WHO2BE_BILLING_OVERRIDE_OPERATORS`, nach core gehoben; On-Prem: Org-Admin
  der Bootstrap-Org). Keine Zähler in Kunden-Admin-Sichten.
- **W3 Zeitpläne = a:** im Code, per Env überschreibbar. Keine
  UI-Bearbeitung.
- **W4 Zeitpunkt = a:** Bau direkt nach Phase D. CLIs `who2be-purge` /
  `who2be-memory-expire` bleiben als manueller Auslöser und Notfallweg
  (Vorlage W4 „ja“).
- Nummern: ADR = 0057, Migration = 0102 (0097–0099 Orchestrator, 0100/0101
  Phase D).
- Ziel: Worker bis spätestens 2026-11-05 deployt (erste Verfälle am 6.11.),
  dann entfallen die Dokploy-Schedules.

Hinweis zur Nummerierung: W1 in der Vorlage hieß „B Eigener Runner“; die
Karte zählt die Optionen je Weiche mit a beginnend. Gemeint ist in beiden
Fällen der eigene Runner mit Postgres-Protokoll (Vorlage §4).

## 3. Der Dienst `worker`

- Eigener Compose-Dienst `worker`, **dasselbe Image wie `api`**, Befehl
  `who2be-worker`. Kein zweites Image, kein zweiter Build.
- Umgebung wie die heutigen Purge-Läufe: Owner-Verbindung `DATABASE_URL`,
  BlobStore-Variablen, Tabellen-Store-Volume, GoTrue-Service-Key
  (best-effort, wie heute im Purge).
- `depends_on` auf den erfolgreichen `migrate`-Lauf, `restart:
  unless-stopped`, Healthcheck `who2be-worker check` (eigener Heartbeat in der
  DB jünger als 2 min).
- Angelegt in jeder Compose, die heute `api` ausliefert (lokal, Dokploy,
  Hetzner, Cloud-Overlays, soweit sie api-Env überschreiben). In Dokploy
  erscheint der Dienst mit dem nächsten Deploy, ein UI-Schritt entfällt.
- **Genau ein Worker-Container**, kein `replicas`. Technisch wäre der Worker
  replikat-sicher (Abschnitt 5); die Begrenzung kommt vom Tabellen-Store
  (Abschnitt 10).
- Graceful Shutdown auf SIGTERM: laufende Routine bis zum Timeout zu Ende
  führen oder sauber als `failed` markieren, keine neuen Slots belegen.
- Global abschaltbar mit `WHO2BE_WORKER_ENABLED=false` (Muster Plausible
  `DISABLE_CRON`). Der Prozess läuft dann weiter und meldet Heartbeat, belegt
  aber keine Slots.

Modulort: `apps/api/src/who2be_api/worker/` mit Registry, Zeitplan-Berechnung,
Runner, Store und CLI (Vorlage §4.2). Die Routine-Funktionen selbst bleiben in
`core/` und werden nur angebunden.

## 4. Registry und Zeitpläne

**Registry im Code.** Routinen melden sich per Decorator an:

```python
@routine(
    "purge",
    schedule="30 3 * * *",
    timeout=timedelta(hours=1),
    catch_up=True,
    touches_tablestore=True,
)
async def purge(ctx: RoutineContext) -> dict[str, int]:
    # ruft die bestehende Logik mit now=ctx.slot, liefert nur Zaehler
    ...
```

- Ein Name ist eindeutig; ein doppelter Name ist ein Startfehler.
- `schedule` ist ein Cron-Ausdruck (ausgewertet mit `croniter`) oder ein
  einfaches Intervall.
- `timeout` begrenzt den einzelnen Lauf.
- `catch_up` regelt das Nachholen (Abschnitt 6).
- `touches_tablestore` kennzeichnet Routinen, die Tabellen-Store-Dateien
  anfassen (Abschnitt 10).
- Das Ergebnis einer Routine sind **nur Zähler**, keine Inhalte und keine
  personenbezogenen Daten.

**Zeitpläne im Code, per Env überschreibbar (W3 = a).** Der Code ist die
Wahrheit, wie bei Oban, sidekiq-cron und BullMQ (Vorlage §3). Ohne Rebuild
überschreibbar:

- `WHO2BE_ROUTINE_<NAME>_SCHEDULE`, z. B. `WHO2BE_ROUTINE_PURGE_SCHEDULE="0 4 * * *"`
- `WHO2BE_ROUTINE_<NAME>_ENABLED=false`
- global `WHO2BE_WORKER_ENABLED=false`

`<NAME>` ist der Routinen-Name in Großbuchstaben, Bindestrich wird zu
Unterstrich. Ein ungültiger Override-Ausdruck ist ein Startfehler, kein
stiller Rückfall auf den Default. Beim Start loggt der Worker die effektive
Tabelle (Name, Zeitplan, an/aus, Quelle `code` oder `env`). Zeitzone ist
immer UTC.

**Keine UI-Bearbeitung.** Zeitpläne in der DB oder in der UI würden ein
Rechtemodell und eine Validierung kosten und die Wahrheit aus dem Code
verlagern. Das kann später eine eigene ADR werden.

## 5. Genau ein Lauf: Slot-Claim und Advisory-Lock

Neue Migration **0102** (Nummer vor dem Anlegen gegen `origin/main` prüfen).
Die Tabellen liegen im Owner-Schema, ohne Tenant-Bezug und ohne RLS, weil sie
keine Mandantendaten tragen. `who2be_app` bekommt nur `SELECT` für den
Betreiber-Endpunkt (Abschnitt 7).

- `routine_run`: eine Zeile je Lauf mit `routine`, `slot`, `trigger`
  (`schedule`, `cli`, `manual`), `status` (`running`, `succeeded`, `failed`,
  `skipped`), `started_at`, `finished_at`, `heartbeat_at`, `result` (jsonb,
  nur Zähler), `error_class` (nur Exception-Klasse, kein Text mit Daten),
  `worker_id`. **UNIQUE (routine, slot).**
- `worker_heartbeat`: `worker_id`, `seen_at`, `version`.

Das genaue Spaltenschema legt P1 fest; verbindlich sind die Felder oben und
der UNIQUE-Schlüssel.

**Slot-Claim (die Exklusivität).** Je Tick (etwa alle 30 s) berechnet der
Runner für jede aktivierte Routine den jüngsten fälligen Slot ≤ jetzt und
belegt ihn:

```sql
INSERT INTO routine_run (routine, slot, trigger, status, worker_id)
VALUES ($1, $2, 'schedule', 'running', $3)
ON CONFLICT (routine, slot) DO NOTHING
RETURNING id;
```

Nur wer die Zeile zurückbekommt, führt die Routine aus. Das ist zustandslos,
hängt an keiner Session und hält auch hinter einem späteren Transaction-Pooler.
Es ist dasselbe Prinzip wie Procrastinates UNIQUE auf
`(task_name, periodic_id, defer_timestamp)` (Vorlage §2.1). CLI- und manuelle
Läufe tragen ihre Startzeit als `slot` und kollidieren damit nicht mit
geplanten Slots.

Abweichung von der Vorlage: Vorlage §4.3 skizziert UNIQUE (routine, slot,
trigger). Verbindlich ist die Owner-Fassung UNIQUE (routine, slot). Der
Unterschied ist folgenlos, weil CLI- und manuelle Läufe ihre Startzeit als
Slot tragen.

**Advisory-Lock (der zweite Gurt).** Während des Laufs hält der Ausführende
auf einer **dedizierten Direktverbindung** einen Session-Lock
`pg_try_advisory_lock(hashtextextended('who2be.routine.' || name, 0))`.
Derselbe Lock wird von den CLIs genommen (Abschnitt 8). Ist er belegt, weil
gerade ein CLI- oder manueller Lauf aktiv ist, wird der geplante Lauf mit
`status='skipped'` beendet.

Der Lock schützt nur gegen **Überlappung**, nicht die Exklusivität je Slot.
Geht er verloren (Verbindungsabbruch, später eingezogener Pooler, der
`pg_try_advisory_lock` still für zwei Halter wahr macht), ist die Folge
höchstens ein doppelter Lauf einer idempotenten Routine. Deshalb sitzt die
Exklusivität im UNIQUE-Slot und nicht in einer Advisory-Leader-Wahl (Vorlage
§2.1, Belege PostgreSQL-Doku §13.3.5 und die dort zitierte Pooler-Falle).

## 6. Nachholen, Heartbeat, abgebrochene Läufe

**catch_up.** `catch_up=True` heißt: Ist beim Start des Workers der letzte
erfolgreiche Lauf älter als eine Periode, läuft die Routine **einmal** sofort,
nicht einmal je verpasstem Slot. Für Purge und Verfall ist das richtig, weil
die DSGVO-Frist sonst um einen Ausfall verschoben würde. Ein Verwerfen
verspäteter Läufe (Procrastinate verwirft Läufe, die mehr als 10 min zu spät
sind) wäre für Nachtläufe falsch.

**Heartbeat.** Der Worker aktualisiert `worker_heartbeat.seen_at` je Tick und
während eines Laufs `routine_run.heartbeat_at` etwa alle 30 s. Der
Healthcheck des Containers prüft den eigenen Heartbeat (jünger als 2 min).

**Abgebrochene Läufe.** `running`-Zeilen mit `heartbeat_at` älter als 5 min
gelten als abgebrochen und werden auf `failed` mit
`error_class='Abandoned'` gesetzt. Der nächste Slot läuft regulär. Ein
gezieltes Nachholen ist dank Idempotenz nicht nötig; `catch_up` greift beim
nächsten Start ohnehin.

**Aufräumen.** Eine eigene Routine `routine-run-retention` löscht
`routine_run`-Zeilen, die älter als 90 Tage sind.

## 7. Sichtbarkeit nur für Betreiber

Die Routinen sind workspace-übergreifend, ihre Zähler betreffen alle
Mandanten. Deshalb sehen sie **nur Betreiber** (W2 = a):

- **Cloud:** eine Operator-Allowlist aus User-UUIDs nach dem Muster von
  `WHO2BE_BILLING_OVERRIDE_OPERATORS`
  (`packages/billing/src/who2be_billing/router.py#_override_operator_ids`):
  kommaseparierte Liste, Default leer, fail-closed, unparsbare Einträge
  werden geloggt und verworfen. Die Prüfung wird **nach `core` gehoben**,
  weil der Kern keine billing-only-Konfiguration tragen darf (ADR-0029). Wie
  Variable und Funktion im Kern heißen und ob Billing auf die Kern-Prüfung
  umzieht, legt P4 fest; die Semantik (fail-closed, pro Aufruf gelesen) ist
  verbindlich.
- **On-Prem:** Org-Admin der Bootstrap-Org. *Ersetzt durch den Nachtrag
  2026-10-10 unten: On-Prem nutzt dieselbe Allowlist wie die Cloud.*
- **Keine Zähler in Kunden-Admin-Sichten.** Ein Org-Admin einer
  Kunden-Organisation sieht weder Routinen noch Laufprotokoll.

Was sichtbar wird (Paket P4/P5):

- ein lesender Endpunkt mit Name, Zeitplan, an/aus, letztem Lauf (Status,
  Dauer, Zähler, Fehlerklasse), nächstem Termin, letztem Erfolg und „Worker
  zuletzt gesehen“;
- ein Health-Feld `worker` mit `stale`, wenn der Heartbeat älter als 5 min
  ist. `/v1/health` bleibt dabei grün; der Hinweis dient als Dead-Man-Signal
  auch ohne UI;
- Prometheus-Metriken nach ADR-0010, z. B.
  `who2be_routine_last_success_timestamp_seconds{routine}` und
  `who2be_routine_runs_total{routine,status}`;
- im Web ein nur lesender Abschnitt „Hintergrund-Routinen“, nur für
  Betreiber.

Ein manuell ausgelöster Lauf aus der UI (`trigger='manual'`) ist möglich, aber
nicht Teil dieser ADR; er käme in einem späteren Paket und nimmt denselben
Lock.

### Nachtrag 2026-10-10 — Betreiber On-Prem über dieselbe Allowlist

Owner-Entscheidung vom 2026-10-10 (Telegram, „E2a“). Gilt für beide
Editionen und ersetzt die On-Prem-Regel oben.

**Befund.** Die Regel „Org-Admin der Bootstrap-Org“ lässt sich im Code nicht
eindeutig bestimmen:

- `services/bootstrap_service.py` legt die Bootstrap-Org als Personal-Org mit
  einem aus `WHO2BE_BOOTSTRAP_ADMIN_EMAIL` abgeleiteten Slug an. Sie trägt
  keinen dauerhaften Marker; wiederfinden lässt sie sich nur, solange die
  Variable gesetzt bleibt, und ohne die Variable gibt es keine Bootstrap-Org.
- Mitglied der Org ist eine abgeleitete User-ID, die kein echter Login
  bekommt. Ein Login landet in einer eigenen Personal-Org. Heute wäre also
  niemand Betreiber nach dieser Regel (eigene Karte zur Login-Zuordnung).
- „Die älteste Org“ als Ersatz wäre eine Vermutung, die nach Löschung oder
  Übertragung einer Org auf die falsche zeigt.

**Entscheidung.** Betreiber ist in Cloud **und** On-Prem, wer in der
Allowlist `WHO2BE_OPERATORS` steht. Die Semantik ist die aus Abschnitt 7:
kommaseparierte User-UUIDs, Default leer, fail-closed, je Aufruf gelesen,
unparsbare Einträge geloggt und verworfen, API-Tokens nie Betreiber.

**Umsetzung (P4a).** `apps/api/src/who2be_api/core/operators.py` trägt den
einzigen Allowlist-Parser (`parse_uuid_allowlist`), `is_operator` und die
Dependency `require_operator` (403 wie das Billing-Gate). Billing ruft den
Kern-Parser für seine unveränderte Variable
`WHO2BE_BILLING_OVERRIDE_OPERATORS` auf
(`packages/billing/src/who2be_billing/router.py#_override_operator_ids`);
damit gibt es keine zweite Fassung (Abschnitt 13). Die beiden Listen bleiben
getrennt: Betreiber zu sein gibt kein Override-Recht. Weil die Regel in beiden
Editionen gilt, reichen die drei Basis-Composes (`docker-compose.yml`,
`deploy/dokploy/docker-compose.yml`, `deploy/hetzner/who2be/docker-compose.yml`)
die Variable an `api` durch; die Cloud-Overlays erben sie.

**Ausbau.** Ist die Login-Zuordnung zur Bootstrap-Org behoben, kann die
ursprüngliche Regel zusätzlich gelten. Sie würde die Allowlist ergänzen,
nicht ersetzen.

*Stand:* Die Login-Zuordnung ist inzwischen behoben
(`bootstrap_service.claim_bootstrap_org`, erster `/v1/me` mit bestätigter
Adresse). Die Bootstrap-Org trägt weiterhin keinen dauerhaften Marker; die
Betreiber-Regel bleibt deshalb unverändert die Allowlist.

## 8. Migrationspfad: externe Zeitpläne, CLIs bleiben

**CLIs bleiben (W4).** `who2be-purge` und `who2be-memory-expire` bleiben als
manueller Auslöser und Notfallweg. Sie laufen künftig über denselben Store
(`trigger='cli'`) und nehmen denselben Advisory-Lock wie der Worker. Ein
Host-Cron oder Dokploy-Schedule, der noch neben dem Worker läuft, ist damit
harmlos: Beide Routinen sind idempotent, und Überlappung endet als
`skipped`.

Ablauf (Vorlage §5):

1. Worker ausliefern (P1 bis P3). Bestehende externe Zeitpläne laufen
   unverändert weiter.
2. **Externe Zeitpläne erkennen.** Gibt es `trigger='cli'`-Läufe einer Routine
   an mindestens zwei aufeinanderfolgenden Tagen, schreibt der Worker eine
   WARN-Logzeile, und der Betreiber-Endpunkt meldet „Externer Zeitplan erkannt
   (Crontab/Dokploy). Kann entfernt werden.“
3. Doku umstellen (P6): RUNBOOK §Retention-Cron und §Verfall auf „entfällt,
   bestehende Zeile entfernen“ samt Prüfbefehl, Cloud-Inbetriebnahme
   §Hintergrundjobs auf „Schedules löschen“, Checklisten 7b/10b auf „Worker
   healthy, erster Lauf sichtbar“.
4. Betreiber entfernen die Einträge. Wer es vergisst, hat keinen Schaden, nur
   No-op- oder `skipped`-Läufe.

**Frist.** Ist der Worker bis spätestens 2026-11-05 deployt, muss der Owner
die Dokploy-Schedules für die Verfälle am 2026-11-06 gar nicht erst anlegen.
Fällt der Worker-Start knapp aus, holt `catch_up` einen ausgefallenen Lauf
einmal nach.

**Unverändert außerhalb des Workers:** das Backup (`backup.sh`, Host-Cron)
und die Access-Log-Rotation. Beide brauchen Host-Zugriff, Docker-Socket,
`pg_dump` und restic; das RUNBOOK legt sie bewusst als Host-Cron fest. Ob ein
Backup-Status in die Betreiber-Sicht kommt, ist eine eigene Frage.

## 9. Umsetzung in Paketen

Schnitt aus Vorlage §6, je Paket höchstens acht Dateien:

| Paket | Inhalt | Abhängig von |
|---|---|---|
| P1 Worker-Kern | Migration 0102 (`routine_run`, `worker_heartbeat`), `worker/`-Module, Script `who2be-worker`, Abhängigkeit `croniter`, Unit- und DB-Tests (nebenläufiger Slot-Claim) | — |
| P2 Routinen anbinden | Registrierung von Purge, Verfall, `routine-run-retention`; CLIs über Store und Lock | P1 |
| P3 Compose und Drift | Dienst `worker` in allen Deploy-Composes, Drift-Test (genau ein `worker`, kein `replicas`, Tabellen-Store-Volume), Deploy-Assertion | P1 |
| P4 Sichtbarkeit API | Betreiber-Endpunkt, Operator-Prüfung in `core`, Health-Feld `worker`, Metriken | P2 |
| P5 Sichtbarkeit Web | nur lesender Abschnitt für Betreiber, i18n de/en | P4 |
| P6 Doku | RUNBOOK, Cloud-Inbetriebnahme, `architecture.md` (Dienstliste, Redis-Klarstellung) | P3 |

Reihenfolge: P1, dann P2 und P3 parallel, dann P6, danach P4 und P5. Mit P1
bis P3 und P6 muss kein Betreiber mehr etwas einrichten; P4 und P5 liefern
die Sichtbarkeit nach.

Tests, die die Entscheidung absichern (Vorlage §4.6): zwei Runner auf
denselben Slot ergeben genau eine `succeeded`-Zeile; ein CLI-Lauf während
eines Worker-Laufs ergibt `skipped`; ein Lauf ohne Heartbeat ergibt
`Abandoned`; Env-Overrides und ungültige Ausdrücke; doppelter Routinen-Name;
jede Routine mit `touches_tablestore=True` ruft nur karenzgeschützte
Funktionen (Allowlist).

## 10. Abgrenzung zu ADR-0054 und ADR-0049

**ADR-0054 (Orchestrator) braucht den Worker nicht.** ADR-0054 §3 hält fest:
„Who2Be startet keinen Task, zählt keine Parallelität mit und bricht nichts
ab.“ Delegationsobjekt, `run_limits`, Stall-Schwelle und Budget sind
Deklarationen, die die Laufzeit (Hermes, Claude Agent SDK, A2A-Client)
befolgt. Der Worker ist daher **kein** Ausführungsort für Orchestrator-Tasks,
und diese ADR öffnet die Grenze „Who2Be ist kein Runtime-Host“ nicht. Der
Worker führt ausschließlich Who2Be-eigene Wartungsroutinen aus, ohne
LLM-Aufrufe.

**ADR-0049 (genau ein API-Container) bleibt unberührt.** Die Betriebsgrenze
aus dem Nachtrag 2026-08-16 („genau EIN Schreib-Prozess je Area“, RUNBOOK
§Betriebsgrenze: genau EIN API-Container) gilt weiter, samt Start-Guard,
Drift-Test (`apps/api/tests/test_single_writer_guard.py`) und
Deploy-Assertion. Der Worker ist kein zweiter API-Container und **schreibt nie
in Tabellen-Store-Dateien**. Neu ist daraus diese Regel:

- Worker-Routinen dürfen Tabellen-Store-Dateien nur über karenzgeschützte
  Sweeps anfassen (heute `apps/api/src/who2be_api/core/purge.py#cleanup_deleted_area_stores`
  mit der 24-h-`mtime`-Karenz aus dem Nachtrag 2026-09-26). Das Attribut
  `touches_tablestore` plus Test erzwingt das.
- Neu ist der Zugriff selbst nicht: Der Purge läuft heute schon als eigener
  Container (Hetzner, `run --rm`) bzw. als eigener Prozess im api-Container
  (Dokploy).
- Der Drift-Test wird auf `worker` ausgedehnt (genau ein Worker), solange ein
  Tabellen-Store-Sweep im Worker liegt.

Kommt später eine Mehr-Replikat-API mit area-affinem Routing, ändert sich am
Worker nichts, weil die Exklusivität in Postgres liegt; die
Tabellen-Store-Regel ist dann neu zu bewerten.

## 11. Ausbaupfad: pgqueuer

Der Runner trennt das **Was** (Registry, Routine-Funktion) vom **Wann und Wer**
(Runner, Store). Kommt der erste echte Queue-Fall (ereignisgetriebene Arbeit
mit Retry, z. B. eigener Mail-Versand), ist `pgqueuer` (MIT, asyncpg-nativ,
Postgres-Backend) der vorgesehene Ausbau:

- im selben Worker-Prozess, Schema per `pgq sql install` als SQL ausgegeben
  und als Who2Be-Migration übernommen;
- die Zeitplan-Routinen bleiben in der eigenen Registry, Queue-Entry-Points
  kommen hinzu.

Die Entscheidung fällt erst dann, mit dem dann aktuellen Wartungsstand. Vorher
offen zu prüfen: die Scheduler-Interna von pgqueuer (in der Vorlage nur aus
der Doku belegt) und der Bus-Faktor (ein Hauptmaintainer, Vorlage §2.1).
Bleibt der Bedarf klein, ist eine eigene `job`-Tabelle mit
`FOR UPDATE SKIP LOCKED` die Alternative; den Mechanismus nutzt
`core/memory_expiry.py` bereits. Procrastinate und Dramatiq bleiben wegen LGPL
ausgeschlossen.

## 12. Verworfene Optionen

Kurzfassung aus Vorlage §2.2:

- **Supercronic-Container:** spart Code, liefert aber keine Sichtbarkeit und
  keinen Schutz gegen Doppelläufe neben einem noch eingetragenen Host-Cron.
- **pgqueuer sofort:** heute Mehr-Abhängigkeit ohne Gegenwert, Fremdschema
  würde zum Vertrag der Betreiber-Sicht. Bleibt Ausbaupfad (Abschnitt 11).
- **pg_cron:** führt nur SQL aus; Purge braucht Python (BlobStore,
  SQLite-Dateien, GoTrue-Admin). Dazu `shared_preload_libraries` und „nur eine
  Datenbank pro Cluster“.
- **Redis-Queues (arq, Celery beat, RQ, taskiq):** On-Prem gibt es kein Redis;
  ein neuer zustandsbehafteter Dienst nur für Jobs.
- **Procrastinate, Dramatiq:** LGPL, am CI-Lizenz-Gate.
- **APScheduler 3 als Kern:** löst nur das Timing, keine Exklusivität über
  Prozesse (eigene FAQ); APScheduler 4 ist Alpha.
- **Scheduler im API-Prozess:** schwere Sweeps liefen in der Event-Loop der
  Requests, jeder Deploy verschiebt Läufe; der Owner will einen eigenen
  Worker-Bereich.
- **Status quo plus Doku:** genau der Betreiber-Handgriff, der wegfallen soll.

## 13. Konsequenzen

Positiv:

- Betreiber richten nichts mehr ein: `docker compose up` bzw. ein
  Dokploy-Deploy bringt die Routinen mit. Crontab-Zeilen und
  Dokploy-Schedules für Purge und Verfall entfallen.
- Genau ein Lauf je Slot, unabhängig von Session-Zustand und Poolern;
  Überlappung mit CLI-Läufen endet als `skipped`.
- Ausfälle werden sichtbar (Laufprotokoll, Health-Feld, Metriken), ohne dass
  Kunden mandantenübergreifende Zähler sehen.
- Neue Routinen kosten einen Decorator und eine Funktion.

Negativ und Kosten:

- Ein zusätzlicher Dienst in jeder Compose und ein zusätzlicher Prozess im
  Betrieb.
- Rund 300 bis 500 Zeilen eigener Runner-Code, den Who2Be selbst pflegt
  (Einschätzung der Vorlage).
- Eine neue Abhängigkeit (`croniter`, MIT) mit Lizenz-Scan beim Hinzufügen.
- Keine Queue: ereignisgetriebene Arbeit braucht später den Ausbaupfad.
- Die Operator-Prüfung wandert nach `core`; Billing und Kern dürfen danach
  nicht zwei abweichende Fassungen tragen (Single Source of Truth, in P4 zu
  klären).

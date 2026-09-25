# Deploy-Korruptionsfenster: laufen beim Neustart kurz zwei API-Container?

Karte `t_95da585b` · Branch `who2be/t_95da585b-deploy-korruptionsfenster-laufen-beim-ne`
Anlass: Bericht `t_3f8f7a69` §1.3 — dort ausdruecklich als **offene Frage** markiert.

## Frage

Der Tabellen-Store (ADR-0049) vertraegt genau **einen** schreibenden Prozess je
Area-Datei. Kann `deploy/hetzner/scripts/deploy.sh` beim Redeploy kurzzeitig
zwei laufende `api`-Container erzeugen?

## Antwort: Nein — fuer den `up`-Pfad belegt

`deploy.sh:216-217` ruft ausschliesslich:

```bash
"${COMPOSE[@]}" up -d --wait --remove-orphans
```

Keine `--scale`, kein `--no-recreate`, kein `--force-recreate`; die Compose-Files
tragen weder `deploy.replicas` noch `scale` (verifiziert, siehe
`apps/api/tests/test_single_writer_guard.py::test_compose_repliziert_die_api_nicht`).
`up` ist damit der Standard-Recreate-Pfad.

### Beleg 1 — Compose-Quelle, `recreateContainer`

Der Recreate eines Service-Containers laeuft in Compose v2 in dieser
Reihenfolge (`pkg/compose/convergence.go`, Funktion `recreateContainer`):

1. `createMobyContainer(... tmpName ...)` — der neue Container wird unter einem
   temporaeren Namen **erzeugt**. Diese Funktion ruft `ContainerCreate` (+ ggf.
   `NetworkConnect`) und **kein** `ContainerStart` (v2.39.1, `convergence.go:692-768`).
2. `ContainerStop(replaced.ID, …)` — der ALTE Container wird gestoppt.
3. `ContainerRemove(replaced.ID)`.
4. `ContainerRename(tmpName → name)`.

Der neue Container ist zwischen (1) und (4) im Zustand `created`, nicht
`running`. Gestartet wird erst in der nachfolgenden Start-Phase: `Up()` ruft
`s.create(...)` und danach `s.start(...)` (`pkg/compose/up.go:38-48`) — und die
Start-Phase startet nur Container, die nicht bereits laufen
(`convergence.go:896-925`).

Damit gilt: **der alte Container ist gestoppt, bevor der neue startet.** Es gibt
kein Fenster mit zwei laufenden API-Prozessen.

Geprueft ueber drei Compose-Versionen — die Sequenz ist in allen identisch:

| Version | create → stop → remove → rename, kein Start dazwischen |
|---|---|
| v2.20.0 | ja |
| v2.29.0 | ja |
| v2.39.1 | ja |

### Beleg 2 — `start-first` ist nicht aktiv

Ein Overlap entstuende nur mit `deploy.update_config.order: start-first`
("new task is started first, and the running tasks briefly overlap",
Compose Deploy Specification). Der Default ist `stop-first`, und **keine** der
Compose-Dateien setzt `update_config` ueberhaupt. Nachweis kommt jetzt aus einem
Test, nicht aus Lektuere (s. u.).

### Was Beleg ist und was Ableitung

- **Beleg:** die Aufrufform in `deploy.sh`, die Abwesenheit von `replicas`/
  `scale`/`update_config` in den Compose-Dateien, die Recreate-Sequenz im
  Compose-Quellcode dreier Versionen, die Default-Semantik von `order` in der
  Compose-Deploy-Spezifikation.
- **Ableitung:** dass die auf dem Hetzner-Host **installierte** Compose-Version
  eine dieser drei ist. Das RUNBOOK fixiert nur „v2.x" (`RUNBOOK.md:71`); die
  Box installiert per `get.docker.com`, also das jeweils aktuelle Release. Der
  Bereich v2.20 – v2.39 verhaelt sich nachweislich gleich, aber eine kuenftige
  Version ist damit nicht belegt.
- **Nicht getestet:** auf dieser Maschine laeuft kein Docker-Daemon. Es wurde
  **kein** Deploy und **kein** `docker compose up` ausgefuehrt. Alles oben ist
  Quellcode- und Dokumentationsanalyse.

Genau diese Ableitungs-Luecke schliesst Punkt 2.

## Umsetzung

### 1. Nach-Deploy-Assertion in `deploy.sh` (statt `stop` vor `up`)

**Kein** explizites `stop api` vor dem `up`. Das ist eine **Abwaegung**, keine
Wirkungslosigkeit — und die Reihenfolge der beiden Argumente ist wichtig:

- Ein Vorab-`stop api` **wuerde** die verbleibende Versions-Annahme
  vollstaendig schliessen. Ist der alte Container vor dem `up` gestoppt, kann
  **keine** Recreate-Reihenfolge zwei laufende API-Container erzeugen, auch
  `start-first` nicht: es gibt keinen laufenden Task, mit dem der neue
  ueberlappen koennte. Es ist der einzige der beiden Mechanismen, der
  versionsunabhaengig **das Fenster** schliesst.
- Er kostet dafuer bei **jedem** Deploy Downtime in Hoehe eines vollen Starts
  samt Healthcheck-`start_period`. Dem steht ein kleines Restrisiko gegenueber:
  die Recreate-Sequenz ist ueber v2.20 – v2.39 im Quellcode belegt, und der
  Drift-Test verbietet `update_config`/`start-first` in allen acht
  Compose-Dateien mit `api`-Dienst. Deshalb: verworfen.

Zusaetzlich prueft das Skript **nach** dem `up`, dass genau ein `api`-Container
laeuft, und bricht sonst mit Exit-Code 3 ab. Diese Pruefung ist **kein Ersatz**
fuer den Vorab-Stop: sie laeuft nach `--wait`, misst also den **Endzustand** und
nicht das Recreate-Fenster — eine durch eine kuenftige Compose-Version
verursachte Ueberlappung waere transient und zum Messzeitpunkt vorbei. Was sie
zuverlaessig faengt, sind **dauerhafte** Zweitinstanzen: ein verwaister
Container aus einem frueheren Bringup, eine von Hand gestartete zweite Instanz,
ein gar nicht gestarteter api-Container.

Die Messung zaehlt ausschliesslich Container-IDs aus **stdout**; `compose ps`
schreibt seine Diagnose in eine getrennte Datei. `--quiet` garantiert nur die
Reinheit von stdout, und Compose meldet im `--env-file`-Pfad regelmaessig nicht
gesetzte Variablen auf stderr — landeten diese Zeilen in derselben Variable,
zaehlte jede als „Container": ein gesunder Deploy braeche ab, und bei **null**
laufenden Containern plus einer Hinweiszeile ergaebe die Zaehlung `1` und der
Deploy liefe durch. Genau deshalb ist dieser Block **ausfuehrbar** getestet
(`test_deploy_zaehlt_nur_container_ids_kein_stderr`): der Messblock wird aus
`deploy.sh` ausgeschnitten und gegen ein `compose ps`-Stub laufen gelassen, das
IDs auf stdout und Rauschen auf stderr schreibt — fuenf Faelle, kein
Docker-Daemon noetig. Die Negativ-Probe (stderr wieder in die gezaehlte
Variable) macht vier davon rot, darunter den Durchwink-Fall.

### 2. Dateibasierte Sperre (`flock`) — geprueft, verworfen

Gefragt war, ob ein Lockfile auf dem gemeinsamen Volume der robustere zweite
Riegel waere. Antwort: **nein, nicht in dieser Form.** Gruende:

1. **Falsche Granularitaet.** Ein `flock` auf dem Volume-Root waere ein
   prozessweiter Ausschluss — er wuerde auch die legitimen zweiten Prozesse
   sperren, die der Betrieb **braucht**: `docker compose run --rm api
   who2be-purge` (Retention-Cron, RUNBOOK §Retention-Cron) schreibt via
   `cleanup_deleted_area_stores` → `delete_area_store` in denselben Store, und
   der Backup-Pfad (`docker compose exec api … snapshot_to`) oeffnet die
   Area-Dateien rw fuer `VACUUM INTO`. Ein Boot-Lock wuerde Backup und Purge
   gegen eine laufende API blockieren.
2. **Die Sperre schuetzte den falschen Zeitpunkt.** Ein Lock, das beim Boot
   genommen und ueber die Prozesslebensdauer gehalten wird, faellt beim
   regulaeren Recreate ohnehin — der alte Container gibt es ab, der neue nimmt
   es. Es verhindert nur den Fall „zwei dauerhaft laufende API-Container", also
   genau den, den die Nach-Deploy-Assertion **belegt** ausschliesst.
3. **`flock` auf dem Volume ist kein starker Beweis.** Die Docker-Volumes liegen
   hier lokal (`local`-Driver), da funktioniert `flock` — auf einem
   Netz-Dateisystem aber nicht zuverlaessig, und das ist genau die Richtung, in
   die eine spaetere Skalierung ginge. Ein Riegel, der beim naechsten
   Infrastrukturschritt still aufgeht, ist schlechter als kein Riegel.

Was **statt** eines Locks noch fehlte, war Sichtbarkeit: dass das Ergebnis
gemessen wird (Punkt 1) und dass die Grenze dort steht, wo jemand sie liest
(Punkt 3).

Der *echte* offene Punkt, den diese Analyse gefunden hat, ist ein anderer als
der gesuchte — er wird als eigene Karte vorgeschlagen (Abschnitt „Fund").

### 3. Drift-Tests ausgeweitet

`apps/api/tests/test_single_writer_guard.py` prueft bisher zwei Compose-Dateien
und kein `update_config`. Ausgeweitet auf:

- **alle** Compose-Dateien der Deploy-Pfade, inkl. `docker-compose.cloud.yml`
  (Hetzner-Overlay), `docker-compose.local.yml` und die Root-Composes — heute
  koennte ein `replicas: 2` im Cloud-Overlay unbemerkt landen;
- `update_config`/`order: start-first` als eigene verbotene Form;
- `deploy.sh`: kein `--scale`, und die Nach-Deploy-Assertion existiert.

### 4. RUNBOOK

Neuer Abschnitt **„Betriebsgrenze: genau EIN API-Container"** weit oben — vor
den Provisioning-Schritten, nicht hinten bei den Backups. Ein Betreiber, der
skalieren will, liest oben nach, nicht in §Tabellen-Store-Backup.

### 5. Changelog

Fragment in `CHANGELOG.md` §Unreleased.

## Fund (eigene Karte vorgeschlagen)

Die gesuchte Ueberlappung entsteht beim Deploy **nicht**. Bei der Pruefung von
Punkt 3 fiel aber auf: es gibt zwei **dokumentierte Betriebspfade**, die einen
zweiten schreibenden Prozess auf denselben Area-Dateien oeffnen, waehrend die
API laeuft — der Retention-Cron (`docker compose run --rm api who2be-purge`,
schreibt via `delete_area_store`) und der Backup-Snapshot
(`docker compose exec api … snapshot_to`, oeffnet rw fuer `VACUUM INTO`). Beide
laufen ausserhalb des API-Prozesses und sehen dessen `asyncio.Lock` nicht; was
bleibt, ist SQLite-eigenes Locking plus `busy_timeout=5000`
(`tablestore/engine.py:447-454`).

Das ist eine andere Frage als die dieser Karte (kein Deploy-Fenster, sondern
gleichzeitiger Betrieb) und gehoert nicht in diesen Scope. Bewertung, ob
`busy_timeout` dafuer genuegt oder ein Koordinationsmechanismus noetig ist:
eigene Karte.

## Verifikation

```bash
uv run pytest apps/api/tests/test_single_writer_guard.py -q
uv run ruff check . && uv run ruff format --check .
uv run mypy apps/api/src
bash -n deploy/hetzner/scripts/deploy.sh
```

Nicht moeglich (kein Docker-Daemon auf dieser Maschine): ein echter
`deploy.sh`-Lauf, `docker compose up`, oder eine Messung der Container-Anzahl
waehrend eines Recreate.

**Was seit der ersten Fassung dazugekommen ist:** die Zaehl-Logik selbst laeuft
jetzt im Test wirklich (Stub statt Daemon), inklusive des Fehlerpfads, wenn
`compose ps` selbst scheitert. Die frueher hier benannte Grenze „der neue
`if`-Zweig ist nur `bash -n`-geprueft" gilt damit nicht mehr; dass Compose sich
gegenueber dem Stub genau so verhaelt (IDs auf stdout, Meldungen auf stderr),
bleibt Ableitung aus der Compose-Dokumentation zu `--quiet`.

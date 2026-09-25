# W8/S1–S3: Access-Logs mit Rotation, no-new-privileges, mem_limit

Karte: `t_a8ffa436` · Branch: `who2be/t_a8ffa436-w8-s1-s3-…` · Stand: 2026-09-25

## Ausgangslage

Der Hetzner-Prod-Stack hatte bisher keine HTTP-Access-Logs und damit keine
Datengrundlage, um einen Vorfall im Nachhinein zu rekonstruieren. Dazu fehlten
zwei Compose-Haertungen, die je eine Zeile kosten:
`security_opt: ["no-new-privileges:true"]` und `mem_limit`.

## Normlage (selbst nachgeschlagen, woertlich)

BSI IT-Grundschutz-Kompendium, Baustein **SYS.1.6 Containerisierung**:

- **SYS.1.6.A7 Persistenz von Protokollierungsdaten der Container (B)** —
  Basis-Anforderung: „Die Speicherung der Protokollierungsdaten der Container
  MUSS ausserhalb des Containers, mindestens auf dem Container-Host, erfolgen."
  → Das ist ein **MUSS**, aber es fordert **nicht** die Existenz von
  HTTP-Access-Logs; es fordert, dass *vorhandene* Protokolldaten den Container
  ueberleben. Die Kartenannahme „Access-Logs sind A7-MUSS" ist also nur zur
  Haelfte richtig und wird so **nicht** uebernommen. Was A7 fordert, erfuellen
  wir trotzdem: das Access-Log landet auf einem Volume (Host), nicht im
  Container-Dateisystem.
- **SYS.1.6.A15 Limitierung der Ressourcen pro Container (S)** —
  Standard-Anforderung (SOLLTE): „Fuer jeden Container SOLLTEN Ressourcen auf
  dem Host-System, wie CPU, fluechtiger und persistenter Speicher sowie
  Netzbandbreite, angemessen reserviert und limitiert werden. Es SOLLTE
  definiert und dokumentiert sein, wie das System im Fall einer Ueberschreitung
  dieser Limitierungen reagiert."
  → Deckt `mem_limit` **und** verlangt die Dokumentation des
  Ueberschreitungsverhaltens (RUNBOOK).
- **SYS.1.6.A17 Ausfuehrung von Containern ohne Privilegien (S)** — SOLLTE:
  „Die Container-Runtime und alle instanziierten Container SOLLTEN nur von
  einem nicht-privilegierten System-Account ausgefuehrt werden, der ueber keine
  erweiterten Rechte fuer den Container-Dienst und das Betriebssystem des
  Host-Systems verfuegt **oder diese Rechte erlangen kann**."
  → `no-new-privileges` adressiert den Teilaspekt „oder diese Rechte erlangen
  kann": es sperrt den Rechtezuwachs ueber setuid-/setgid-Binaries und
  Datei-Capabilities. Der Geltungsbereich von A17 ist breiter als dieser
  Teilaspekt — die Karte weist die Massnahme deshalb bewusst als Beitrag zu
  A17 aus und nicht als A17-Konformitaet, damit spaetere Leser den Umfang
  nicht ueberschaetzen. Die Anforderungen A21/A23 (H) gehoeren zu einem
  eigenen Zuschnitt und sind laut Karte nicht Teil dieser Aenderung.

Quelle, selbst aufgeschlagen und woertlich abgeglichen: BSI
IT-Grundschutz-Kompendium, Baustein SYS.1.6 Containerisierung, **Edition
2023**, Einzel-PDF `SYS_1_6_Containerisierung_Edition_2023.pdf`
(bsi.bund.de), A7 im Abschnitt Basis-Anforderungen, A15/A17 im Abschnitt
Standard-Anforderungen. Die Edition 2022 traegt bei A7 und A15 denselben
Wortlaut; bei A17 weicht sie nur sprachlich ab („für … bzw. das
Betriebssystem" statt „und das Betriebssystem").

**Was die Karte annahm und was davon bleibt:** Die Karte stuft Access-Logs als
A7-MUSS ein. Das ist nach dem gepruefen Wortlaut **nicht haltbar** — A7 sagt
nichts darueber, dass Access-Logs existieren muessen, sondern nur, wo
Protokollierungsdaten liegen muessen, wenn es sie gibt. Der Access-Log wird
hier also nicht wegen einer MUSS-Pflicht eingefuehrt, sondern wegen des
fachlichen Befunds aus `t_3f8f7a69`; A7 bestimmt lediglich die Ablage (Volume
statt Container-Dateisystem).

## Datenschutz (Aufgabe 1, zweiter Teil)

`docs/compliance/vvt.md` fuehrt Server-Logs bereits als **V12
(Betrieb/Missbrauchsabwehr, Art. 6 Abs. 1 lit. f)** und listet die Datenkategorie
„Server-Logs/Zugriffsdaten: IP, User-Agent, Zeitstempel … Caddy/App-Logs" mit
Quelle `deploy/hetzner/Caddyfile`. Die Verarbeitung ist also **bereits
vorgesehen** — neu ist nur, dass sie tatsaechlich stattfindet.

Offen war ausschliesslich die Frist: §7 VVT und
`data-retention-and-erasure.md` §5/§6 tragen dort einen Platzhalter
`<PLATZHALTER: konkrete Log-Retention (z. B. 7–30 Tage) + Rotationsverfahren>`.

**Entscheidung ohne Rueckfrage: 14 Tage.** Begruendung: die Spanne 7–30 Tage ist
im Repo bereits als Rahmen dokumentiert, die Frist wird also nicht frei erfunden,
sondern innerhalb eines schon abgesteckten Korridors konkretisiert (Mitte). Das
ist keine Owner-Weiche, sondern das Ausfuellen eines Platzhalters durch einen
Wert, den das Dokument selbst vorschlaegt. Wer laenger aufbewahren will, aendert
eine Zahl im Caddyfile.

Zusaetzlich, ohne dass die Karte es verlangt:

- Caddy redigiert `Cookie`, `Set-Cookie`, `Authorization` und
  `Proxy-Authorization` **per Default** als `REDACTED` (Doku `log`-Direktive).
  Der Schalter `log_credentials`, der das abschaltet, wird nicht gesetzt.
- Query-Parameter werden gefiltert: `api.<DOMAIN>` traegt den
  OAuth-Authorization-Endpunkt, damit stehen `code`/`token`-Werte in der URL.
  Ein `format filter` ersetzt sie durch `REDACTED`, bevor etwas auf Platte geht.

## Arbeitsschritte

1. `deploy/hetzner/Caddyfile`: Snippet `(access_log)`, in alle vier Site-Bloecke
   importiert. Output `file /var/log/caddy/access.log` (Volume → Host, A7),
   `roll_size 10MiB`, `roll_keep 10`, `roll_keep_for 336h` — Groessengrenzen fuer
   Caddys **eigene** Generationen; Query-Redaction via `format filter`. Die
   14-Tage-Frist traegt das Skript aus Schritt 7, nicht diese Direktiven.
2. `deploy/hetzner/who2be/docker-compose.yml`: `caddy-logs`-Volume;
   `logging:`-Limits (`json-file`, `max-size 10m`, `max-file 3`),
   `security_opt`, `mem_limit` an **allen** Diensten inkl. Profil-Diensten.
3. `deploy/hetzner/supabase/docker-compose.yml`: dieselben drei Blöcke an allen
   Diensten inkl. `studio`-Profil.
4. Doku: VVT §7, `data-retention-and-erasure.md` §5/§6, RUNBOOK
   (Log-Zugriff + Verhalten bei Limit-Ueberschreitung, A15-Satz 2).
5. Test `apps/api/tests/test_compose_hardening.py`: erzwingt Vollstaendigkeit
   (jeder Dienst in beiden Hetzner-Files traegt alle drei Bloecke) — damit ist
   „vollstaendig, nicht stichprobenhaft" nicht nur heute wahr. Dazu
   `deploy/hetzner/tests/test_access_log_rotation.sh`, das die **Wirkung** des
   Rotationsverfahrens ausfuehrt statt Zeichenketten zu suchen; im CI-Job
   `compose-smoke` verdrahtet, weil nur dort ein Docker-Daemon laeuft.
6. Verifikation: `caddy validate` mit dem echten 2.8.4-Binary,
   YAML-Parse + Test-Suite, ruff/mypy. Zusaetzlich das Rotationsverfahren
   aus Schritt 7 real gegen einen laufenden `caddy:2.8-alpine`-Container.
7. **`deploy/hetzner/scripts/rotate-access-log.sh`** + Host-Cron im RUNBOOK: die
   Caddy-Direktiven deckeln Groesse, nicht Zeit, also braucht die Frist einen
   eigenen Ausloeser (dasselbe Muster wie bei Backup und Retention-Purge). Ein
   Skript und keine Kommandokette, weil die drei Teile unterschiedlich
   fehlschlagen duerfen: die Rotation hat an einem Tag ohne Anfragen nichts zu
   tun (Caddy legt `access.log` erst beim ersten Request an), die Loeschung muss
   trotzdem laufen. Sie deckt beide Generationen-Namensklassen ab. Ein
   Fehlschlag endet rot, schreibt keinen Erfolgsstempel und pingt keinen
   Heartbeat.
8. Changelog-Fragment unter `changelog.d/<slug>.security.md` — **nicht** direkt
   in `CHANGELOG.md`. Das Fragment-Verfahren aus CONTRIBUTING.md (#587) ist
   nicht Stilfrage, sondern vom CI-Job `changelog-guard` erzwungen; ein
   direkter Eintrag in die Sammeldatei faellt dort hart durch. Lokal
   nachpruefbar mit
   `uv run python scripts/changelog_fragments.py guard --base origin/main`.

## Scope-Grenze (bewusst)

Nur die **Hetzner-Prod-Stacks**. `docker-compose.yml` (Repo-Root, lokale
Entwicklung), `deploy/dokploy/*` (Staging) und die Cloud-Overlays bleiben
unangetastet: die `mem_limit`-Werte sind auf die Owner-Entscheidung „CX32,
8 GB" geeicht und waeren auf einer beliebigen Entwicklermaschine oder in
Dokploys eigener Ressourcenverwaltung eine willkuerliche Fremdvorgabe. Die
Log-Limits lokal zu kappen wuerde ausserdem das Debuggen verschlechtern,
wofuer die volle Historie dort gerade erwuenscht ist.

## mem_limit — die Werte

Budget: CX32 = 8 GB, 4 vCPU (Owner-Entscheidung 2026-09-25). Beide Stacks
laufen auf **derselben** Maschine.

Grundsatz: `mem_limit` ist ein **Deckel gegen Ausreisser**, keine Reservierung
(`mem_reservation` wird nicht gesetzt). Die Summe der Deckel darf das RAM
ueberschreiten, solange die Summe der *typischen* Nutzung deutlich darunter
liegt — sonst waere jeder Deckel so knapp, dass er im Normalbetrieb zuschlaegt,
und das waere schlechter als der heutige Zustand.

| Dienst | Limit | Begruendung |
|---|---|---|
| `db` (Postgres) | 3g | Groesster legitimer Verbraucher (shared_buffers + work_mem je Verbindung + Page-Cache-Druck). Bewusst der hoechste Deckel: der Befund nennt genau den Fall „OOM-Killer trifft Postgres im Schreiben" — mit Deckeln an den anderen Diensten ist Postgres nicht mehr der groesste Brocken und damit kein bevorzugtes Opfer des Host-OOM-Killers mehr. |
| `api` | 1g | Python/uvicorn, ein Prozess (ADR-0049-Nachtrag verbietet `--workers`). Spitzen: Ingest bis 20 MiB Nutzdaten + Base64-Rahmen, SQLite-Abfragen mit eigenem Groessenbudget. 1g ist ein Vielfaches davon. |
| `seaweedfs` | 1g | Volume-Index + S3-Gateway im selben Prozess (`weed server`); Index waechst mit der Objektzahl. |
| `auth` (GoTrue) | 512m | Go-Dienst, zustandslos, JWT/Session-Arbeit; typisch zweistellige MB. |
| `caddy` | 256m | Go-Reverse-Proxy; neu ist nur der Log-Writer (gepufferte Datei). |
| `web` (nginx) | 256m | Statisches SPA-Bundle + Proxy; nginx belegt typisch einstellige MB. |
| `auth-gateway` (nginx) | 128m | Reiner Header-/Pfad-Proxy ohne Dateiauslieferung. |
| `migrate` | 512m | One-Shot im API-Image; laeuft nur beim Deploy. |
| `db-roles` | 128m | One-Shot, ein `psql`-Aufruf. |
| `blobstore-bootstrap` | 512m | One-Shot im API-Image (S3-SDK). |
| `mcp`, `mcp-http` | 512m | Profil-Dienste, Python wie `api`, aber ohne Ingest-Pfad. |
| `backup` | 1g | `pg_dump | gpg` plus restic: restic haelt Index und Pack-Puffer im Speicher, deutlich mehr als die anderen One-Shots. Laeuft nachts allein. |
| `meta` | 512m | Profil `studio`, default aus. |
| `studio` | 1g | Profil `studio`, Next.js — default aus, deshalb nicht im Dauerbudget. |

Summe der **standardmaessig laufenden** Dienste:
3g + 1g + 1g + 512m + 256m + 256m + 128m = **6,15 GiB** Deckel bei 8 GB RAM,
also ~1,8 GB Luft fuer Host, Kernel-Page-Cache und Docker selbst. Die
One-Shots laufen nur beim Deploy (Deckel greifen dann zusaetzlich, aber `api`
startet ohnehin erst danach), die Profil-Dienste sind aus.

**Verhalten bei Ueberschreitung** (A15 Satz 2, ins RUNBOOK): Der Kernel-OOM-Killer
beendet den Prozess **innerhalb** des betroffenen Containers; `restart:
unless-stopped` startet ihn neu. Der Host und die uebrigen Container bleiben
unberuehrt — genau das ist der Zweck. Sichtbar wird es als `OOMKilled: true`
in `docker inspect`.

## Testgrenzen (ehrlich)

Auf dieser Maschine laeuft **kein Docker-Daemon**. Das Compose-CLI selbst
braucht fuer `config` keinen Daemon, also war die Schema-Validierung doch
moeglich — mehr als erwartet ist verifiziert:

- **Verifiziert:**
  - Caddyfile gegen das echte `caddy` **2.8.4** (dieselbe Minor-Version wie das
    Image `caddy:2.8-alpine`): `caddy validate --adapter caddyfile` → „Valid
    configuration", und `caddy adapt` zeigt, dass Rotation, Filter und
    Logger-Zuordnung je Subdomain tatsaechlich im JSON landen.
  - **Dabei ein echter Fund:** ein zunaechst gesetztes `mode 640` kennt Caddy
    2.8 nicht, und der file-Writer verwirft unbekannte Unterbefehle **still**
    (`validate` meldet nichts, `adapt` laesst sie einfach weg). Die Zeile waere
    ein wirkungsloser Platzhalter gewesen — entfernt und im Caddyfile
    kommentiert.
  - `docker compose config` fuer **beide** Hetzner-Stacks inkl. aller Profile
    (`studio`, `mcp`, `mcp-http`, `backup`): parst, Anchor/Merge-Key loest auf.
  - Das **gerenderte** Ergebnis gegengezaehlt: alle 15 Dienste tragen
    `mem_limit`, `no-new-privileges` und `logging`-Limits; `caddy-logs` ist als
    Volume deklariert und auf `/var/log/caddy` gemountet.
  - Suite: `pytest apps/api/tests/test_compose_hardening.py` → 50/50.
    **Negativnachweis selbst gefuehrt:** ein entfernter `<<: *hardening` am
    `caddy`-Dienst faerbt genau die zwei zugehoerigen Faelle rot, ein
    entferntes `import access_log` genau den Site-Fall — die Tests koennen also
    rot werden.
  - `ruff check`, `ruff format --check`, `mypy` (465 Dateien): gruen.
- **Nicht verifiziert:** ein echter Start der beiden **Hetzner**-Stacks als
  Ganzes und ob die gewaehlten `mem_limit`-Werte im Dauerbetrieb reichen.
  Letzteres laesst sich ohne Produktionslast grundsaetzlich nicht messen —
  deshalb sind die Deckel grosszuegig gewaehlt und das RUNBOOK sagt, woran man
  einen zu knappen Deckel erkennt (dauerhaft > 80 %) und wie man ihn anhebt.
  **Kein CI-Job schliesst diese Luecke:** `compose-smoke` startet
  `docker compose up` ohne `-f`, also das Root-`docker-compose.yml` der lokalen
  Entwicklung; die Compose-Dateien unter `deploy/hetzner/` laufen in keinem
  Workflow (nur `deploy.yml` referenziert sie, und das erst auf der
  Zielmaschine). Der gruene `compose-smoke` belegt fuer diese Aenderung nur,
  dass der lokale Stack weiterhin startet — nicht den Startpfad der geaenderten
  Stacks. **Ausnahme, und nur diese:** der Job faehrt zusaetzlich
  `test_access_log_rotation.sh` gegen das echte `caddy:2.8-alpine`. Das belegt
  das Rotationsverfahren, nicht den Stack-Start.

- **Rotationsverfahren dagegen real geprueft** (podman, `caddy:2.8-alpine`,
  Binary v2.8.4), weil es die Frist traegt:
  - `roll_keep_for` erfasst die **aktive** Datei nicht: ohne Rotationsereignis
    bleibt sie bestehen — der Grund, warum das Rotations-Skript existiert. Es
    erfasst zudem nur Caddys **eigene** Generationen (`access-<ts>.log.gz`),
    nicht die des Skripts (`access.log.<ts>.gz`): gemessen blieb eine 2000 Tage
    alt datierte `access.log.*`-Datei nach zwei echten Rotationen liegen,
    dieselbe im lumberjack-Namensformat wurde geloescht. Deshalb raeumt das
    Skript beide Klassen und `roll_keep_for` ist **kein** Rueckfall fuer die
    Frist.
  - `copytruncate` (kopieren + `truncate -s 0`) erzeugt eine Datei voller
    Nullbytes: der Writer schreibt am alten Offset weiter. Deshalb `mv`.
  - Weder `USR1` noch `HUP` noch `caddy reload` oeffnen die Datei neu.
    Deshalb der Container-Neustart; gemessene Unterbrechung **0,7 s**.
  - **Caddy legt `access.log` erst beim ersten Request an**, nicht beim Start.
    Eine `&&`-Kette liess deshalb an einem Tag ohne Anfragen auch die Loeschung
    ausfallen — der Grund, warum das Verfahren ein Skript mit drei getrennt
    fehlschlagenden Teilen ist und keine Kommandokette.
  - busybox-`gzip` erhaelt die mtime des Originals **nicht**: die Generation
    traegt den Rotations-, nicht den Schreibzeitpunkt. Das ist der konservative
    Bezugspunkt; zusammen mit der `-mtime +N`-Semantik (greift ab N+1 Tagen)
    liegt die Loeschschwelle zwei Tage unter der Frist, damit 14 Tage die
    Obergrenze sind.
  - Das gesamte Verfahren laeuft jetzt als Test:
    `deploy/hetzner/tests/test_access_log_rotation.sh`, im CI-Job
    `compose-smoke`. Jeder der Faelle wurde einzeln **rot** gefahren (Loeschung
    an der Rotation aufgehaengt, Loeschmuster auf eine Namensklasse reduziert,
    Schwelle auf die Frist gesetzt).
- **Coverage-Gate lokal:** `pytest --cov --cov-fail-under=85` scheitert hier
  mit 63,40 %, weil ohne erreichbare DB 485 Integrationstests uebersprungen
  werden. Gegenprobe auf `main`: identische 63,40 % und dieselben 485 Skips bei
  1418 statt 1468 passed — die Differenz sind exakt die 50 neuen Tests, kein
  neuer Skip. Das Gate ist eine Umgebungsgrenze, keine Regression; in CI laeuft
  ein Postgres-Service.

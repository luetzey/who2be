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
- **SYS.1.6.A17 Ausfuehrung von Containern ohne Privilegien (S)** — SOLLTE,
  passt zu `no-new-privileges`. `cap_drop`/`read_only` liegen unter A21/A23 (H)
  und sind laut Karte out of scope.

Quelle: it-grundschutzkompendium.de/sys_it-systeme/sys.1.6_containerisierung
(Edition 2023, Abschnitte Basis- bzw. Standard-Anforderungen).

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
   `roll_size 10MiB`, `roll_keep 10`, `roll_keep_for 336h` (14 Tage),
   `mode 640`; Query-Redaction via `format filter`.
2. `deploy/hetzner/who2be/docker-compose.yml`: `caddy-logs`-Volume;
   `logging:`-Limits (`json-file`, `max-size 10m`, `max-file 3`),
   `security_opt`, `mem_limit` an **allen** Diensten inkl. Profil-Diensten.
3. `deploy/hetzner/supabase/docker-compose.yml`: dieselben drei Blöcke an allen
   Diensten inkl. `studio`-Profil.
4. Doku: VVT §7, `data-retention-and-erasure.md` §5/§6, RUNBOOK
   (Log-Zugriff + Verhalten bei Limit-Ueberschreitung, A15-Satz 2).
5. Test `apps/api/tests/test_compose_hardening.py`: erzwingt Vollstaendigkeit
   (jeder Dienst in beiden Hetzner-Files traegt alle drei Bloecke) — damit ist
   „vollstaendig, nicht stichprobenhaft" nicht nur heute wahr.
6. Verifikation: `caddy validate` mit dem echten 2.8.4-Binary,
   YAML-Parse + Test-Suite, ruff/mypy.
7. CHANGELOG (Unreleased).

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
- **Nicht verifiziert:** ein echter Stack-Start, das tatsaechliche Schreiben
  der Logdatei ins Volume, das Rotationsverhalten unter Last, und ob die
  gewaehlten `mem_limit`-Werte im Dauerbetrieb reichen. Letzteres laesst sich
  ohne Produktionslast grundsaetzlich nicht messen — deshalb sind die Deckel
  grosszuegig gewaehlt und das RUNBOOK sagt, woran man einen zu knappen Deckel
  erkennt (dauerhaft > 80 %) und wie man ihn anhebt.
- **Coverage-Gate lokal:** `pytest --cov --cov-fail-under=85` scheitert hier
  mit 63,40 %, weil ohne erreichbare DB 485 Integrationstests uebersprungen
  werden. Gegenprobe auf `main`: identische 63,40 % und dieselben 485 Skips bei
  1418 statt 1468 passed — die Differenz sind exakt die 50 neuen Tests, kein
  neuer Skip. Das Gate ist eine Umgebungsgrenze, keine Regression; in CI laeuft
  ein Postgres-Service.

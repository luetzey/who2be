# ADR-0048 — Content-addressed Blob-Storage (MinIO/S3)

- Status: Akzeptiert
- Datum: 2026-08-13
- Kontext: Teil des Vorhabens „Agent WorkArea + Knowledge Base" (ADR-0047);
  Plan: `.claude/plan/2026-08-13-1200_agent-workarea-knowledge-base.md`.
  Die Ingest-Pipeline (PDF/HTML/Text → Blob + abgeleitetes Doc-Artifact)
  braucht Objekt-Speicher; das Repo hat bisher keinen.
- Bezug: ADR-0047 (Umbrella), ADR-0033 (OSS-Lizenz-Gates), ADR-0029
  (Build-Isolation — hier bewusst NICHT als Vorbild), ADR-0046
  (Port-/Adapter-Muster `embeddings/`)

## Kontext

Ingest lädt Dateien (Limit `WHO2BE_INGEST_MAX_BYTES`, Default 20 MB) oder
URLs, extrahiert Text in memory und persistiert Original + Ableitung. Die
Originale (PDFs, HTML-Snapshots) gehören nicht in Postgres-Zeilen, sondern in
einen Objekt-Store. User-Entscheidung 3 (2026-08-13): MinIO/S3-kompatibel,
content-addressed (SHA-256), als neuer Compose-Dienst.

Lizenz-Randbedingung (ADR-0033, fail-closed): Der MinIO-**Server** steht
unter AGPL; das Lizenz-Gate des Repos prüft aber gelinkte
Python-Dependencies. Das minio-**SDK** ist Apache-2.0 und damit zulässig.

## Optionen

- **A (gewählt): minio-SDK als Kern-Dependency hinter einem Port.**
  `apps/api/src/who2be_api/blobstore/{port,service,adapters/minio,adapters/memory}`
  nach dem embeddings-Vorbild (ADR-0046). Der Port dient **Testbarkeit und
  Austauschbarkeit** (jeder S3-kompatible Store), nicht Optionalität — Blob-
  Storage ist ein Kern-Feature der WorkArea.
- **B: Optionale Dependency-Gruppe (analog `--group embeddings`).**
  Verworfen — fragmentiert ein Kern-Feature; „Ingest geht nur mit
  Extra-Install" ist kein sinnvoller Produktzustand.
- **C: Separates Paket (billing-Muster, ADR-0029).** Verworfen — das
  billing-Muster ist eine **Lizenz-/Editionsgrenze**; hier gibt es keinen
  Editions-Bezug, die physische Isolation wäre reiner Overhead.

## Entscheidung

1. **Port + Adapter:** `BlobStorePort` mit minio-Adapter (Produktion) und
   memory-Adapter (Tests, Port-Contract-Tests gegen beide Semantiken).
   minio wird reguläre Kern-Dependency (+ mypy-Override).
2. **Key-Layout `blobs/{workspace_id}/{sha256}`** — content-addressed
   innerhalb des Workspace. Der Workspace-Präfix macht GDPR-Purge und
   Art.-20-Export trivial (Prefix-Listing/-Delete). **Bewusst KEIN
   Cross-Workspace-Dedup:** Tenancy-Isolation geht vor Speicherersparnis;
   ein workspace-übergreifend geteiltes Objekt wäre ein verdeckter Kanal
   zwischen Mandanten.
3. **Degradation statt Startabbruch:** Ohne Blobstore-Konfiguration liefern
   **nur** Ingest und Blob-Reads 503 `blobstore_unconfigured`; alles andere
   (Docs, Tables, KB, Suche) läuft voll. Env:
   `WHO2BE_BLOBSTORE_{ENDPOINT,ACCESS_KEY,SECRET_KEY,BUCKET,SECURE}`.
4. **Compose:** Dienst `minio` + One-Shot `minio-bootstrap` (legt den Bucket
   an und terminiert; Muster `set-app-role-password`). **AGPL-Einordnung
   (ADR-0033):** MinIO läuft ausschließlich als eigenständiger Dienst im
   Container — wie Postgres — und wird nicht gelinkt; lizenzrechtlich
   unkritisch. Im Code liegt nur das Apache-2.0-SDK.
5. **Konsistenz-Reihenfolge:** SHA-256 + Dedup-Lookup (`wa_blob`) vor dem
   PUT; Blob-PUT **vor** dem DB-Commit (content-addressed → Doppel-PUT
   harmlos, gleicher Key = gleicher Inhalt); danach EINE
   Postgres-Transaktion. Scheitert sie, bleibt höchstens ein MinIO-Orphan.

## Konsequenzen

- Neues Package `blobstore/`, neue Dependency `minio` (Apache-2.0,
  pip-licenses-Gate grün), Compose-Dienste `minio` + `minio-bootstrap`,
  `.env.example`-Erweiterung.
- **Orphan-Sweep** als `who2be-purge`-Erweiterung: Objekte > 24 h ohne
  `wa_blob`-Row werden geräumt.
- **Backup/Purge per Workspace-Prefix:** RUNBOOK dokumentiert MinIO-Backup;
  Workspace-Löschung räumt `blobs/{workspace_id}/` komplett;
  GDPR-Export zieht Blobs über denselben Prefix.
- Manuelle Compose-Verifikation (WP3-DoD): minio healthy → Bootstrap legt
  Bucket an → ohne Env 503 `blobstore_unconfigured` → mit Env
  PDF-Ingest-Smoke, Objekt unter `blobs/{ws}/{sha}`, Doppel-Ingest ohne
  zweites Objekt.

## Bewusst nicht entschieden / Ausblick

- **Presigned-URLs / direkter Client-Download** — im MVP laufen Blob-Reads
  durch die API (Gates + Zugriffslog); direkte Auslieferung erst, wenn
  Größen/Last es fordern.
- **Alternative S3-Provider in der Cloud** (Hetzner Object Storage o. ä.) —
  der Port lässt jeden S3-kompatiblen Store zu; die Hosting-Entscheidung ist
  bewusst nicht Teil dieses ADR.
- **Lifecycle-Policies/Tiering** im Store selbst — Retention läuft im MVP
  über `retention_days` + `who2be-purge`, nicht über MinIO-Lifecycle-Regeln.

## Addendum 2026-09-19 — SeaweedFS statt MinIO (Community Edition eingestellt)

MinIO hat seine Community Edition eingestellt. README wörtlich: „The MinIO
community edition is now distributed as source code only. We will no longer
provide pre-compiled binary releases for the community version." Zeitstrahl:
letzter Community-Push 2025-09-07 (exakt unser bisheriger Image-Pin) ·
source-only ab Okt 2025 (letztes Release `RELEASE.2025-10-15T17-29-55Z`) ·
Repository **archiviert** Apr 2026 · Docker Hub entfernt den `minio`-Namespace
~10.–13.09.2026 → CI repo-weit rot. Gegengeprüft an der Registry-API:
`minio/minio` und `minio/mc` liefern beide `object not found`, Kontrolle
`library/postgres` meldet `active`.

Drei Gründe lösten den Wechsel gemeinsam aus:

1. **Verfügbarkeit** — `compose-smoke`, `e2e`, `e2e-billing-cloud` sterben am
   Image-Pull, vor jedem Testkörper; trifft jeden PR und `main`.
2. **Sicherheit** — `RELEASE.2025-09-07` trägt **CVE-2025-62506** (CVSS 8.1,
   Privilege Escalation via Session-Policy-Bypass), gefixt erst in
   `RELEASE.2025-10-15`; MinIO patcht Container nicht mehr. Einzuordnen, nicht
   zu dramatisieren: für unsere Nutzung ist die Lücke **nicht erreichbar** —
   sie setzt ein bereits vorhandenes, eingeschränktes Service-Account- oder
   STS-Credential voraus, und wir nutzen weder Service Accounts noch STS (im
   Code geprüft), sondern ein einziges Root-Credential-Paar.
3. **Lizenz** — MinIO ist AGPLv3. Dieser ADR zieht in Entscheidungspunkt 4 die
   Randbedingung aus ADR-0033 heran, deren Deny-Liste „mit besonderem Fokus
   auf die AGPL-Netzwerkfalle" gilt, weil Who2Be als Cloud-SaaS **und**
   On-Prem verteilt wird.

**Ersetzt durch SeaweedFS**, Apache-2.0 — an der LICENSE-Datei verifiziert:
kein Copyleft, keine Netzwerk-Klausel. Dieselbe Lizenz, in die Who2Be selbst
per `FSL-1.1-Apache-2.0` übergeht. Damit **entfällt die Begründungslast**, die
Entscheidungspunkt 4 oben für AGPL trug („MinIO läuft ausschließlich als
eigenständiger Dienst im Container — wie Postgres — und wird nicht gelinkt;
lizenzrechtlich unkritisch"): es gibt schlicht kein Copyleft mehr, das
eingeordnet werden müsste. Siehe auch das Addendum in ADR-0033.

**Was gleich bleibt** (Muster-Entscheidung, s. Plan
`.claude/plan/2026-09-19-0758_seaweedfs-statt-minio.md`):

- **Port + Adapter aus Entscheidungspunkt 1 sind unverändert.** Die App
  spricht S3 über das Apache-2.0-SDK `minio` (Python-Paket), nicht das
  MinIO-Protokoll — `MinioBlobStore` funktioniert unverändert gegen
  SeaweedFS, kein neuer Adapter, keine App-Code-Änderung.
- **Die Bucket-Trennung aus Entscheidungspunkt 4 bleibt bestehen: den Bucket
  legt weiterhin der Compose-One-Shot an, nie die App** — gewechselt hat nur
  der Server dahinter (Dienst `seaweedfs` statt `minio`, One-Shot
  `blobstore-bootstrap` statt `minio-bootstrap`).

**Was sich ändert:**

- **All-in-One statt Vier-Service-Stack.** SeaweedFS' eigene Compose-Vorlage
  fährt `master`+`volume`+`filer`+`s3` als vier Container; für einen Bucket
  wäre das ein schlechter Tausch gegen den einen bisherigen MinIO-Container.
  Stattdessen ein Prozess: `server -s3 -s3.config=... -dir=/data`.
- **Ports.** S3 auf **8333** (vorher MinIO: 9000), Master-HTTP auf **9333**.
- **Healthcheck NICHT auf `8333/healthz`.** Bekannter Fallstrick
  (seaweedfs#8243): der S3-Handler interpretiert `/healthz` als Bucket-Namen
  und antwortet 404. Funktionierend ist der Master-Port:
  `http://.../9333/cluster/status`.
- **Credentials sind ein Sicherheits-Gate, keine Kür.** SeaweedFS-Doku
  wörtlich: „By default, if no credentials are configured, SeaweedFS allows
  anonymous access to all S3 operations." Ohne `-s3.config` stünde der Store
  offen — es gibt kein einfaches `MINIO_ROOT_USER`/`MINIO_ROOT_PASSWORD`-
  Env-Paar wie bei MinIO mehr, nur noch eine `s3.json`
  (`identities[].credentials[].accessKey/secretKey`, `actions: [...]`). Lokal
  (WP1) ist das eine statische, eingecheckte
  `scripts/seaweedfs-s3.json`, per Volume gemountet; Prod rendert dieselbe
  Datei stattdessen bei jedem Container-Start aus den Env-Variablen (Docker
  substituiert in gemounteten Dateien nichts). Beide Wege speisen sich aus
  denselben zwei Variablen: `SEAWEEDFS_S3_ACCESS_KEY`/`SEAWEEDFS_S3_SECRET_KEY`
  (Dev-Default `who2be-dev`/`who2be-dev-secret` — in Prod niemals diese
  Defaults verwenden; Details siehe RUNBOOK).

**Migration bestehender Daten ist bewusst NICHT Teil dieses Wechsels.**
Vorhandene Blobs im `minio-data`-Volume eines laufenden Hetzner-Hosts wandern
nicht automatisch in den neuen `seaweedfs`-Bucket — das ist ein eigener,
manueller Schritt, siehe `deploy/hetzner/RUNBOOK.md`
§„SeaweedFS-/BlobStore-Backup" und §„Betrieb der Compose-Dienste".

Bezug: Issue #525 (Entscheidung), #528 (WP1 — Compose/Credentials/Bootstrap),
#531 (diese Dokumentation).

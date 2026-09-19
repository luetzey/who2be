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

## Addendum 2026-09-19 — Der Bucket-Bootstrap braucht kein CLI-Image

**Anlass.** Das Image `minio/mc`, das der One-Shot `minio-bootstrap` zog, ist
von Docker Hub verschwunden (`object not found`, #525). Der Pull-Fehler riss
`compose-smoke`, `e2e` und `e2e-billing-cloud` repo-weit ab — vor jedem
Testkörper.

**Entscheidung.** Der One-Shot fährt jetzt das **API-Image** und ein kleines
Skript (`scripts/minio-bootstrap.py`) statt eines eigenen CLI-Images. Das
Apache-2.0-SDK `minio` ist ohnehin Kern-Dependency der API — die Lizenz-Grenze
oben (AGPL-**Server** nur als Container, im Code nur das SDK) bleibt davon
unberührt, weil der Bootstrap nichts anderes tut als die API auch: er spricht
S3 über das SDK.

**Was ausdrücklich NICHT geändert wurde:** die Trennung „Den Bucket legt der
Compose-One-Shot an — nie die App." Sie war der naheliegende Ort, um beim
Umbau Aufwand zu sparen (ein `make_bucket` im API-Start hätte den Service ganz
erspart), und genau deshalb steht sie hier: der Bootstrap bleibt ein eigener,
terminierender Service, `api` hängt weiter per
`service_completed_successfully` daran. Gewechselt hat nur das Image.

**Idempotenz.** `mc mb --ignore-existing` erledigte das in einem Flag. Mit dem
SDK sind es zwei Schritte (`bucket_exists`, dann `make_bucket`), und die sind
**nicht atomar**: Deshalb fängt das Skript zusätzlich
`BucketAlreadyOwnedByYou`/`BucketAlreadyExists` ab. Jeder andere `S3Error`
propagiert und lässt den One-Shot scheitern — er ist das Gate vor dem
API-Start, ein stiller Erfolg wäre dort das Schlimmste.

**Compose-Anchor.** `api` und `minio-bootstrap` teilen den Build über
`x-api-build`. Zwei gleich aussehende `build:`-Blöcke wären kompakter zu
schreiben gewesen, würden aber beim nächsten Wechsel von
`${API_BUILD_TARGET}` auseinanderlaufen.

**Nicht behoben.** Das Image des `minio`-**Servers** ist genauso verschwunden;
dieser Schritt macht die CI deshalb noch nicht grün. Offen in #525. Ebenfalls
unberührt: der Healthcheck `mc ready local` — dieses `mc` stammt aus dem
Server-Image selbst und ist kein eigener Pull.

**Verifizierung:** `apps/api/tests/test_minio_bootstrap.py` — Idempotenz
(zweiter Lauf, verlorenes Rennen), Propagierung echter S3-Fehler, und die
Compose-Verdrahtung (kein eigenes Image am One-Shot; `api` wartet weiter auf
ihn). Ein echter Compose-Lauf steht aus, solange das Server-Image fehlt.

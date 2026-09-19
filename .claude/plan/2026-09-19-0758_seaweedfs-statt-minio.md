# Weg von MinIO: SeaweedFS als S3-Dienst

_Angelegt: 2026-09-19 07:58 UTC — Branch `feat/seaweedfs-statt-minio`_

## Warum (belegt, nicht vermutet)

MinIO hat die Community Edition **eingestellt**:

> „The MinIO community edition is now distributed as source code only. We will
> no longer provide pre-compiled binary releases for the community version."

| Wann | Was |
|---|---|
| 2025-09-07 | letzter Community-Push auf quay.io — exakt unser Pin |
| Okt 2025 | source-only; letztes Release `RELEASE.2025-10-15T17-29-55Z` |
| Apr 2026 | `minio/minio`-Repository **archiviert** |
| ~10.–13.09.2026 | Docker Hub entfernt den `minio`-Namespace → CI repo-weit rot |

Drei Probleme auf einmal, die dieser Umbau löst:

1. **CI ist repo-weit rot** — `compose-smoke`, `e2e`, `e2e-billing-cloud`
   sterben am Image-Pull, vor jedem Testkörper.
2. **Ungepatchte CVE.** `RELEASE.2025-09-07` trägt **CVE-2025-62506**
   (CVSS 8.1, Privilege Escalation via Session-Policy-Bypass). Gefixt erst in
   `RELEASE.2025-10-15`, und MinIO patcht Container nicht mehr. Für unsere
   Nutzung derzeit nicht erreichbar (kein Service-Account-/STS-Gebrauch, im
   Code geprüft) — aber auf einem eingefrorenen Stand bleibt das Glück.
3. **Lizenz.** MinIO ist AGPLv3. ADR-0033 zieht eine fail-closed Deny-Liste
   (`GPL;AGPL;LGPL;SSPL;…`) „mit besonderem Fokus auf die AGPL-Netzwerkfalle",
   weil Who2Be als Cloud-SaaS **und** On-Prem verteilt wird.

## Zielbild

**SeaweedFS**, Apache-2.0 — verifiziert an der LICENSE-Datei: kein Copyleft,
keine Netzwerk-Klausel, kommerzielle und SaaS-Nutzung uneingeschränkt. Es ist
zugleich die Lizenz, in die Who2Be selbst übergeht (`FSL-1.1-Apache-2.0`).
Damit entfällt auch die Begründungslast, die ADR-0048 heute für AGPL trägt.

Image: `chrislusf/seaweedfs:4.22`
Digest: `sha256:84429e5f21fad82246f5cfae7b39e9a17da18afb62f2b79c25ccd364ab02793b`

## Design-Entscheidungen (verbindlich für alle Arbeitspakete)

**1. All-in-One, nicht der Vier-Service-Stack.** SeaweedFS' eigene
Compose-Vorlage fährt `master` + `volume` + `filer` + `s3` als vier Container.
Für einen Bucket wäre das ein schlechter Tausch gegen den einen
MinIO-Container. Stattdessen `command: server -s3 -dir=/data -ip.bind=0.0.0.0`
— ein Prozess, ein Container.

**2. Credentials sind ein Sicherheits-Gate, keine Kür.** Wörtlich aus der
Doku: *„By default, if no credentials are configured, SeaweedFS allows
**anonymous access** to all S3 operations."* Ohne `-s3.config` stünde der
Store offen. Die Identität wird über eine `s3.json` gesetzt
(`identities[].credentials[].accessKey/secretKey`, `actions: ["Admin"]`), per
Volume gemountet — dasselbe Muster wie `set-app-role-password`.

**3. Healthcheck NICHT auf `/healthz` am S3-Port.** Bekannter Fallstrick
(seaweedfs#8243): der S3-Handler interpretiert `/healthz` als Bucket-Namen und
antwortet 404. Funktionierend ist der Master-Port:
`http://localhost:9333/cluster/status`.

**4. Ports ändern sich.** S3 liegt auf **8333** (MinIO: 9000). Master 9333.
Wie bisher nur an Loopback binden (Security-Review 2026-08-13 L3).

**5. Der Anwendungscode bleibt unberührt.** Das Apache-2.0-SDK `minio` spricht
S3, nicht MinIO — `MinioBlobStore` funktioniert unverändert gegen SeaweedFS.
Ebenso der Bucket-Bootstrap: `CreateBucket`/`HeadBucket` sind unterstützt,
also tragen `bucket_exists` + `make_bucket` weiter.

**Muster-Entscheidung:** _Port-and-Adapter bleibt unverändert_ — der Wechsel
des Backends findet ausschließlich in der Compose-/Config-Schicht statt, nicht
im Adapter. Beleg für die Variabilität: ADR-0048 hat den BlobStore-Port genau
für diesen Fall eingeführt (`port.py` + austauschbare Adapter `minio.py` /
`memory.py`). Die kompaktere Alternative — ein eigener SeaweedFS-Adapter —
wurde verworfen, weil beide Backends dasselbe S3-API sprechen und ein zweiter
Adapter nur Duplikat wäre.

## Arbeitspakete (datei-disjunkt)

### Welle 1 — Fundament

**WP1 · Compose, Credentials, Bootstrap** — *starkes Modell*
- `docker-compose.yml`: `minio` + `minio-bootstrap` → `seaweedfs` +
  `blobstore-bootstrap` (All-in-One, Digest-Pin, Healthcheck auf 9333,
  Ports 8333/9333 an Loopback, Volume `seaweedfs-data`)
- `scripts/seaweedfs-s3.json` (neu) — Identität mit `actions: ["Admin"]`
- `scripts/minio-bootstrap.py` → `scripts/blobstore-bootstrap.py`
- `.env.example`

_Hier fallen alle Design-Entscheidungen zusammen (Credential-Gate,
Healthcheck-Fallstrick, Port-Wechsel). Ein Fehler hier pflanzt sich in alle
Folgepakete fort — deshalb das stärkste Modell._

### Welle 2 — parallel, strikt datei-disjunkt

**WP2 · Deploy-Stacks** — *mittleres Modell*
`deploy/hetzner/who2be/docker-compose.yml`, `deploy/dokploy/docker-compose.yml`,
`deploy/hetzner/.env.example`.
_Mechanische Übertragung des in WP1 festgelegten Musters auf zwei weitere
Compose-Dateien — kein neuer Entwurf._

**WP3 · API-Konfiguration + Tests** — *mittleres Modell*
`apps/api/src/who2be_api/core/config.py` (Default-Endpoint), `apps/api/tests/**`
(`test_blobstore.py`, `test_minio_bootstrap.py` → umbenennen/anpassen),
`apps/api/pyproject.toml` (nur der SDK-Kommentar).
_Klar umrissen, aber Tests verlangen Urteilsvermögen: sie müssen weiter in
beide Richtungen belegen._

**WP4 · Dokumentation** — *mittleres Modell*
`docs/adr/0048-*` (Addendum), `docs/adr/0033-*` (Lizenz-Einordnung),
`deploy/hetzner/RUNBOOK.md`, `CLAUDE.md`, `README.md`, `CHANGELOG.md`,
`docs/compliance/vvt.md`, `docs/compliance/data-retention-and-erasure.md`.
_Viel Text, wenig Logik — aber die ADR-Qualität ist die Begründung für
künftige Leser, deshalb nicht das kleinste Modell._

`.claude/context/` (STATE/DECISIONS) pflege ich am Ende selbst — drei Agenten
auf derselben Datei wäre ein garantierter Konflikt.

## Ausdrücklich NICHT in diesem Umbau

- Kein neuer BlobStore-Adapter (s. Muster-Entscheidung).
- Keine Änderung an `blobstore/port.py`, `service.py`, `wa_ingest.py`,
  `gdpr_export_service.py` — die kennen nur den Port.
- **Prod-Datenmigration.** Existierende Blobs auf dem Hetzner-Host wandern
  nicht automatisch mit; das ist ein eigener, manueller Schritt (RUNBOOK) und
  gehört nicht in einen Code-PR.

## DoD

`uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy .`,
`uv run pytest`. Ein echter Compose-Lauf ist hier nicht möglich (kein
Docker-Daemon in dieser Umgebung) — das muss im PR offen stehen, und die CI
(`compose-smoke`, `e2e`) ist die eigentliche Probe.

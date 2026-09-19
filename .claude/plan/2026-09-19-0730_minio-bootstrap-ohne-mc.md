# `minio-bootstrap` ohne das `mc`-Image

_Angelegt: 2026-09-19 07:30 UTC — Branch `fix/minio-bootstrap-without-mc`_

## Auftrag

Owner-Entscheidung zu #525, Option B: „mc rauswerfen, SDK ist eh schon drin."

## Ausgangslage (belegt)

`docker-compose.yml:289` zieht `minio/mc:RELEASE.2025-08-13T08-35-41Z` nur,
um **einen Bucket anzulegen**:

```
mc alias set local http://minio:9000 "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD" &&
mc mb --ignore-existing local/who2be-blobs
```

Das Image ist von Docker Hub verschwunden (`object not found`). Das
Apache-2.0-SDK `minio>=7.2` ist dagegen bereits Kern-Dependency von
`apps/api` (`apps/api/pyproject.toml:26`) und steckt im gebauten API-Image.

## Wichtige Leitplanke — ADR-0048

> „Den Bucket legt der Compose-One-Shot `minio-bootstrap` (Dev) bzw. die
> Provisionierung (Prod) an — **nie die App**."
> (`blobstore/adapters/minio.py`, Modul-Docstring)

Die Bucket-Anlage darf also **nicht** in den API-Start wandern. Der One-Shot
bleibt ein eigener, terminierender Service — nur sein Image wechselt. Das ist
der Unterschied zwischen „das Image tauschen" und „die Architektur ändern";
nur Ersteres ist beauftragt.

## Repo-Konvention — `set-app-role-password`

Der Compose-Kommentar nennt diesen One-Shot ausdrücklich als Muster
(`docker-compose.cloud.yml:47`):

```yaml
set-app-role-password:
  image: postgres:16                                   # Image, das das Werkzeug schon hat
  entrypoint: ["/bin/sh", "/scripts/set-app-role-password.sh"]
  volumes:
    - ./scripts/set-app-role-password.sh:/scripts/…:ro  # Skript per Mount, nicht im Image
```

Dasselbe Muster, ein Feld anders: statt `postgres:16` (bringt `psql` mit)
das **API-Image** (bringt das `minio`-SDK mit).

## Umsetzung

1. `scripts/minio-bootstrap.py` — legt den Bucket über das SDK idempotent an.
   Idempotenz ausdrücklich wie `mc mb --ignore-existing`: `bucket_exists` ist
   nicht atomar, deshalb wird `BucketAlreadyOwnedByYou`/`BucketAlreadyExists`
   zusätzlich gefangen.
2. `docker-compose.yml` — `minio-bootstrap` nutzt denselben Build wie `api`,
   Skript per Volume-Mount. `depends_on`/`restart: "no"` bleiben unverändert,
   ebenso das `service_completed_successfully` von `api`.
3. Doku: ADR-0048-Addendum, CHANGELOG.

**Muster-Entscheidung:** YAML-Anchor (`x-api-build`) für den geteilten
Build-Block. Die kompaktere Alternative wäre, die vier `build:`-Zeilen zu
duplizieren. Dagegen entschieden, weil zwei getrennte Build-Blöcke
auseinanderlaufen können, sobald sich das Target ändert — und `target:`
ist hier bereits variabel (`${API_BUILD_TARGET:-runtime}`). Der Anchor ist
Standard-YAML und macht die Absicht explizit: *dasselbe Artefakt*, nicht
*zufällig gleich konfiguriert*. Das Repo nutzt bisher keine Anchors; der
Block bekommt deshalb einen erklärenden Kommentar.

## Ausdrücklich NICHT in diesem PR

- **Der `minio`-Server-Service.** Sein Image ist genauso verschwunden — das
  ist die größere, noch offene Frage aus #525. Dieser PR macht die CI
  deshalb **nicht** grün; er beseitigt eines von zwei toten Images.
- **Der Healthcheck `mc ready local`** im `minio`-Service. Das `mc` darin
  stammt aus dem Server-Image und ist kein eigener Pull — kein
  Supply-Chain-Problem. Es mit anzufassen hieße, den Server-Service zu
  ändern, über den noch entschieden wird.

## DoD

`uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy .`,
`uv run pytest`. Compose lässt sich hier nicht fahren — kein Docker-Daemon
in dieser Umgebung, und das `minio`-Image wäre ohnehin nicht ziehbar. Das
muss im PR offen stehen, statt als „verifiziert" behauptet zu werden.

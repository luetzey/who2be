"""Hard-Purge-Job fuer abgelaufene Soft-Deletes (Track O, Plan §3.2).

Raeumt nach Ablauf der 30-Tage-Grace endgueltig ab:
  * **Organizations** mit `deleted_at IS NOT NULL AND purge_after <= now` →
    `DELETE FROM organization` (CASCADE loescht die ganze Tenant-Hierarchie).
  * **Accounts** (`account_deletion`, `purge_after <= now`) → Personal-Org +
    API-Tokens + Memberships werden geloescht, danach der GoTrue-User
    (Service-Key, best-effort), zuletzt `purged_at` gesetzt.

Dazu die **WorkArea-/KB-Retention** (WP20, ADR-0047/0048/0049) — drei
voneinander unabhaengige Sweeps, die NICHT an einem Loeschwunsch haengen,
sondern laufend Muell abraeumen:
  * `cleanup_expired_artifacts` — Artifacts in Areas mit `retention_days`.
  * `cleanup_orphan_blobs` — `wa_blob`-Zeilen ohne Artifact + Objekte ohne
    Zeile (ADR-0048).
  * `cleanup_deleted_area_stores` — SQLite-Dateien geloeschter Areas
    (ADR-0049).

Laeuft als **Owner-Connection** (`DATABASE_URL`, RLS-Bypass) wie der
Migrations-Runner, damit die CASCADE-Deletes workspace-uebergreifend
durchgreifen. Als Cron einplanbar (`who2be-purge`); idempotent — ein zweiter
Lauf ohne faellige Eintraege ist ein No-op.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

import asyncpg

from who2be_api.blobstore import (
    BlobAgeSource,
    BlobStorePort,
    build_blob_store,
    workspace_prefix,
)
from who2be_api.core.config import get_settings
from who2be_api.integrations.gotrue_admin import delete_auth_user
from who2be_api.repositories.account_repository import (
    AccountPurgeRepository,
    PgAccountPurgeRepository,
)
from who2be_api.services.tablestore_provider import get_table_store
from who2be_api.tablestore import TableStore

logger = logging.getLogger(__name__)

# Schonfrist fuer Blob-Muell (ADR-0048). Der Ingest schreibt das Objekt VOR
# der Postgres-Transaktion (`services/wa_ingest.py`, Schritt 6) — zwischen
# PUT und COMMIT existiert ein Objekt ohne Katalog-Zeile ganz regulaer.
# 24 h liegen um Groessenordnungen ueber jeder Ingest-Dauer und machen den
# Sweep damit unabhaengig von der Laufzeit einzelner Ingests.
ORPHAN_BLOB_GRACE = timedelta(hours=24)

# Deckel des Objekt-Sweeps (Teil 2 von `cleanup_orphan_blobs`). Der Sweep
# listet ein Praefix vollstaendig — auf einem grossen Bucket ist das teuer,
# und der Purge ist ein Cron-Job neben dem Live-Betrieb, kein Wartungsfenster.
# Beide Grenzen sind bewusst weich: was ein Lauf liegen laesst, nimmt der
# naechste (der Sweep ist idempotent und Muell laeuft nicht weg).
ORPHAN_OBJECT_SCAN_LIMIT = 50_000
ORPHAN_OBJECT_DELETE_LIMIT = 500

# Artifacts, deren Area eine Frist traegt. `retention_days` haengt an der
# AREA, nicht am Artifact (Migration 0073) — ohne Frist (NULL) wird nie
# geloescht, auch nicht in privaten Areas (Plan-Default). Gerechnet wird auf
# `created_at`: das Artifact ist ab seiner Entstehung im System, `occurred_at`
# ist der fachliche Zeitpunkt und darf beliebig weit zurueckliegen.
# `wa_chunk` haengt per FK-CASCADE (0076) und verschwindet mit.
#
# `$1::timestamptz` MUSS gecastet werden: ohne Cast bleibt der Parameter fuer
# den Planer unbekannt, er leitet ihn aus `$1 - interval` als `interval` ab und
# der Vergleich scheitert an „timestamptz < interval".
_EXPIRED_ARTIFACTS_SQL = """
DELETE FROM wa_artifact a
USING work_area area
WHERE a.area_id = area.id
  AND area.retention_days IS NOT NULL
  AND a.created_at < $1::timestamptz - make_interval(days => area.retention_days)
RETURNING a.id
"""

# Katalog-Zeilen ohne referenzierendes Artifact. Zwei Referenzwege (0074):
# `content_ref` traegt beim blob-Artifact den sha256, `blob_sha256` die
# Ingest-Provenance des abgeleiteten doc-Artifacts — eine Zeile ist erst
# verwaist, wenn KEINER von beiden mehr auf sie zeigt.
_ORPHAN_BLOB_ROWS_SQL = """
DELETE FROM wa_blob b
WHERE b.created_at < $1
  AND NOT EXISTS (
      SELECT 1 FROM wa_artifact a
      WHERE a.workspace_id = b.workspace_id
        AND (a.content_ref = b.sha256 OR a.blob_sha256 = b.sha256)
  )
RETURNING b.workspace_id, b.storage_key
"""


@dataclass(frozen=True)
class PurgeResult:
    """Zaehlt, was ein Purge-Lauf abgeraeumt hat."""

    organizations: int
    accounts: int
    anonymized_audit_rows: int = 0
    cleaned_invitations: int = 0
    cleaned_oauth_rows: int = 0
    # --- WorkArea-/KB-Retention (WP20) ---
    expired_artifacts: int = 0
    orphan_blob_rows: int = 0
    orphan_blob_objects: int = 0
    deleted_area_stores: int = 0
    # Kein BlobStore konfiguriert (ADR-0048: der NORMALFALL, kein Fehler) —
    # die Katalog-Zeilen werden trotzdem abgeraeumt, nur die Objekte nicht.
    blobstore_skipped: bool = False
    # Verzeichnisse im Tabellen-Store ohne zugehoerigen Workspace. Werden
    # bewusst NICHT geloescht (s. `cleanup_deleted_area_stores`), nur gemeldet.
    unknown_store_dirs: int = 0


async def purge_expired(
    repo: AccountPurgeRepository,
    now: datetime | None = None,
) -> PurgeResult:
    """Raeumt faellige Org- und Account-Loeschungen ab. Liefert die Zaehlung.

    Die GoTrue-User-Loeschung ist best-effort: schlaegt sie fehl, wird der
    DB-seitige Purge dennoch finalisiert (`purged_at` gesetzt) — ein erneuter
    Lauf wuerde den Account sonst endlos wieder aufgreifen.
    """
    reference = now or datetime.now(UTC)

    org_ids = await repo.expired_organizations(reference)
    for org_id in org_ids:
        await repo.purge_organization(org_id)
        logger.info("Org %s endgueltig geloescht (Grace abgelaufen).", org_id)

    user_ids = await repo.expired_accounts(reference)
    purged_accounts = 0
    anonymized_rows = 0
    for user_id in user_ids:
        # Daten zuerst (idempotent), dann die GoTrue-Identitaet. `purged_at` wird
        # NUR gesetzt, wenn die Identitaet erfolgreich entfernt ist — sonst bleibt
        # der Account pending und der naechste Lauf versucht die Erasure erneut
        # (DSGVO: die Loeschung gilt erst als abgeschlossen, wenn auch die
        # Auth-Identitaet weg ist).
        anonymized_rows += await repo.purge_account_data(user_id)
        if await delete_auth_user(user_id):
            await repo.mark_account_purged(user_id)
            purged_accounts += 1
            logger.info("Account %s endgueltig geloescht (Grace abgelaufen).", user_id)
        else:
            logger.warning(
                "Account %s: Auth-Identitaet konnte nicht geloescht werden — "
                "Purge wird beim naechsten Lauf erneut versucht.",
                user_id,
            )

    # Generische Cleanup-Schritte: PII abgelaufener/akzeptierter Invitations
    # (WP-D, P7) und abgelaufene/konsumierte OAuth-Codes/-Refresh-Tokens
    # (CMP-1, Datenminimierung). Laufen unabhaengig von Account-/Org-Purges;
    # beide idempotent.
    cleaned_invitations = await repo.cleanup_expired_invitations(reference)
    cleaned_oauth_rows = await repo.cleanup_expired_oauth(reference)

    return PurgeResult(
        organizations=len(org_ids),
        accounts=purged_accounts,
        anonymized_audit_rows=anonymized_rows,
        cleaned_invitations=cleaned_invitations,
        cleaned_oauth_rows=cleaned_oauth_rows,
    )


async def cleanup_expired_artifacts(
    conn: asyncpg.Connection,
    now: datetime | None = None,
) -> int:
    """Loescht Artifacts, deren Area-Frist (`retention_days`) abgelaufen ist.

    ADR-0047: die Frist ist eine Eigenschaft der WorkArea, nicht des einzelnen
    Artifacts. `retention_days IS NULL` heisst unbegrenzt und ist der Default —
    auch fuer private Areas (Plan-Entscheidung). Ein Artifact ist faellig, wenn
    sein `created_at` aelter ist als `now - retention_days`.

    `wa_chunk` haengt per FK-CASCADE am Artifact (Migration 0076) und wird
    mitgeloescht — die Suche verliert die Passagen im selben Zug.

    Idempotent: ein zweiter Lauf findet dieselbe Menge nicht mehr vor.
    Liefert die Zahl der geloeschten Artifacts.
    """
    reference = now or datetime.now(UTC)
    rows = await conn.fetch(_EXPIRED_ARTIFACTS_SQL, reference)
    if rows:
        logger.info("Retention: %d abgelaufene(s) Artifact(s) geloescht.", len(rows))
    return len(rows)


async def cleanup_orphan_blobs(
    conn: asyncpg.Connection,
    store: BlobStorePort | None,
    now: datetime | None = None,
) -> tuple[int, int, bool]:
    """Raeumt Blob-Muell in beide Richtungen ab (ADR-0048).

    Zwei Sweeps, weil Katalog (`wa_blob`) und Objekt-Storage getrennt sind und
    jede Seite ohne die andere zurueckbleiben kann:

    1. **Zeile ohne Artifact** — nichts referenziert den Blob mehr (weder
       `content_ref` noch `blob_sha256`) und die Zeile ist aelter als
       `ORPHAN_BLOB_GRACE`. Die Zeile faellt, danach das Objekt. Diese
       Reihenfolge ist Absicht: bleibt das Objekt liegen (Store nicht
       erreichbar), faengt es Sweep 2 spaeter ein — umgekehrt zeigte eine
       ueberlebende Zeile auf ein fehlendes Objekt und jeder Read liefe ins
       Leere.
    2. **Objekt ohne Zeile** — Rueckstand einer gescheiterten
       Ingest-Transaktion (PUT liegt VOR dem COMMIT, `wa_ingest.py`). Hier
       gibt es keinen Datenbank-Zeitstempel, also braucht der Sweep das Alter
       vom Store: nur ein Store, der `BlobAgeSource` erfuellt, wird
       aufgeraeumt. Ohne Zeitquelle waere ein laufender Ingest nicht von Muell
       zu unterscheiden und der Sweep loeschte einen Blob, den die Transaktion
       Sekunden spaeter referenziert.

    Ist `store` `None` (ADR-0048: Installation ohne Objekt-Storage, der
    NORMALFALL und kein Fehler), laeuft nur Sweep 1 — die Katalog-Zeilen
    verschwinden, die Objekte bleiben unberuehrt, das Ergebnis vermerkt es.

    Liefert `(geloeschte Zeilen, geloeschte Objekte, store_uebersprungen)`.
    """
    reference = now or datetime.now(UTC)
    cutoff = reference - ORPHAN_BLOB_GRACE

    rows = await conn.fetch(_ORPHAN_BLOB_ROWS_SQL, cutoff)
    if store is None:
        if rows:
            logger.warning(
                "Retention: %d verwaiste wa_blob-Zeile(n) geloescht, aber kein "
                "BlobStore konfiguriert — die Objekte bleiben liegen.",
                len(rows),
            )
        return len(rows), 0, True

    # Kandidaten-Workspaces VOR dem Objekt-Sweep einsammeln: Workspaces, deren
    # letzte Zeile gerade gefallen ist, tauchen in `wa_blob` nicht mehr auf,
    # haben aber genau jetzt Objekte zum Abraeumen.
    workspaces: set[UUID] = {row["workspace_id"] for row in rows}

    deleted_objects = 0
    for row in rows:
        await store.delete(row["storage_key"])
        deleted_objects += 1

    catalog_rows = await conn.fetch("SELECT DISTINCT workspace_id FROM wa_blob")
    workspaces.update(row["workspace_id"] for row in catalog_rows)

    deleted_objects += await _sweep_orphan_objects(conn, store, workspaces, cutoff)
    if rows or deleted_objects:
        logger.info(
            "Retention: %d verwaiste wa_blob-Zeile(n), %d Objekt(e) geloescht.",
            len(rows),
            deleted_objects,
        )
    return len(rows), deleted_objects, False


async def _sweep_orphan_objects(
    conn: asyncpg.Connection,
    store: BlobStorePort,
    workspaces: set[UUID],
    cutoff: datetime,
) -> int:
    """Sweep 2 aus `cleanup_orphan_blobs`: Objekte ohne Katalog-Zeile.

    Gescopet auf Workspaces, die im Katalog vorkommen (bzw. gerade
    vorkamen) — ein Praefix-Listing pro Workspace statt eines Bucket-Scans.
    **Bekannte Luecke:** ein Workspace, dessen ALLERERSTER Ingest scheitert,
    hat nie eine `wa_blob`-Zeile und faellt damit aus dem Scope; sein einzelnes
    Objekt bleibt liegen. Bewusst in Kauf genommen — die Alternative waere ein
    Listing ueber den gesamten Bucket bei jedem Cron-Lauf.
    """
    if not isinstance(store, BlobAgeSource):
        logger.info(
            "Retention: BlobStore %s liefert kein Objekt-Alter — Sweep 2 "
            "(Objekte ohne Katalog-Zeile) uebersprungen.",
            type(store).__name__,
        )
        return 0

    deleted = 0
    for workspace_id in sorted(workspaces, key=str):
        if deleted >= ORPHAN_OBJECT_DELETE_LIMIT:
            logger.warning(
                "Retention: Objekt-Sweep bei %d Loeschungen gedeckelt — der "
                "naechste Lauf macht weiter.",
                ORPHAN_OBJECT_DELETE_LIMIT,
            )
            break
        known = {
            row["sha256"]
            for row in await conn.fetch(
                "SELECT sha256 FROM wa_blob WHERE workspace_id = $1", workspace_id
            )
        }
        keys = await store.list_keys(workspace_prefix(workspace_id))
        if len(keys) > ORPHAN_OBJECT_SCAN_LIMIT:
            logger.warning(
                "Retention: Workspace %s hat mehr als %d Objekte — Sweep 2 "
                "betrachtet nur das erste Fenster.",
                workspace_id,
                ORPHAN_OBJECT_SCAN_LIMIT,
            )
            keys = keys[:ORPHAN_OBJECT_SCAN_LIMIT]
        for key in keys:
            if deleted >= ORPHAN_OBJECT_DELETE_LIMIT:
                break
            if key.rsplit("/", 1)[-1] in known:
                continue
            written_at = await store.last_modified(key)
            # Kein Alter = kein Beweis fuer Muell (s. Docstring) — stehen lassen.
            if written_at is None or written_at >= cutoff:
                continue
            await store.delete(key)
            deleted += 1
            logger.info("Retention: verwaistes Blob-Objekt %s geloescht.", key)
    return deleted


async def cleanup_deleted_area_stores(
    conn: asyncpg.Connection,
    store: TableStore,
) -> tuple[int, int]:
    """Loescht SQLite-Dateien, deren WorkArea es nicht mehr gibt (ADR-0049).

    Der Tabellen-Store liegt im Dateisystem
    (`{WHO2BE_TABLESTORE_DIR}/{workspace_id}/{area_id}.sqlite`) und haengt an
    keinem FK — ein `DELETE FROM work_area` laesst die Datei stehen. Dieser
    Sweep ist der Gegenpart dazu.

    **Defensiv, absichtlich zurueckhaltend:** angefasst wird ein
    Workspace-Verzeichnis nur, wenn sein Name eine UUID ist UND ein Workspace
    mit dieser ID existiert. Alles andere bleibt unberuehrt und wird nur
    gezaehlt/geloggt. Grund ist der teuerste denkbare Fehlfall: liefe der
    Purge versehentlich gegen die falsche (z. B. frisch migrierte, leere)
    Datenbank, saehe JEDES Verzeichnis wie ein geloeschter Workspace aus — die
    Regel „unbekannt heisst Finger weg" macht aus einem Konfigurationsfehler
    eine Warnzeile statt eines Totalverlusts. Die Kehrseite: nach einem
    Org-/Workspace-Hard-Purge bleiben die Dateien liegen und muessen vom
    Betreiber entfernt werden (siehe `docs/compliance/data-retention-and-erasure.md`).

    Idempotent (`delete_area_store` ist ein No-op auf fehlende Dateien).
    Liefert `(geloeschte Area-Stores, unbekannte Verzeichnisse)`.
    """
    base_dir = store.base_dir
    if not base_dir.is_dir():
        return 0, 0

    removed = 0
    unknown_dirs = 0
    for workspace_dir in sorted(base_dir.iterdir(), key=lambda path: path.name):
        if not workspace_dir.is_dir():
            continue
        workspace_id = _as_uuid(workspace_dir.name)
        if workspace_id is None:
            unknown_dirs += 1
            logger.warning(
                "Retention: %s ist kein Workspace-Verzeichnis (keine UUID) — unberuehrt gelassen.",
                workspace_dir,
            )
            continue
        workspace_exists = await conn.fetchval(
            "SELECT 1 FROM workspace WHERE id = $1", workspace_id
        )
        if workspace_exists is None:
            unknown_dirs += 1
            logger.warning(
                "Retention: Workspace %s existiert nicht (mehr) — Tabellen-Store "
                "%s bleibt liegen und ist manuell zu pruefen.",
                workspace_id,
                workspace_dir,
            )
            continue
        removed += await _remove_dangling_area_files(conn, store, workspace_id, workspace_dir)
    if removed:
        logger.info("Retention: %d verwaiste(r) Area-Store(s) geloescht.", removed)
    return removed, unknown_dirs


async def _remove_dangling_area_files(
    conn: asyncpg.Connection,
    store: TableStore,
    workspace_id: UUID,
    workspace_dir: Path,
) -> int:
    """Dateien EINES Workspace-Verzeichnisses ohne `work_area`-Zeile loeschen."""
    area_rows = await conn.fetch("SELECT id FROM work_area WHERE workspace_id = $1", workspace_id)
    known_areas = {row["id"] for row in area_rows}
    removed = 0
    # Nur `*.sqlite`; die WAL-/SHM-Seitendateien raeumt `delete_area_store` mit
    # ab, und alles andere im Verzeichnis geht den Purge nichts an.
    for path in sorted(workspace_dir.glob("*.sqlite")):
        area_id = _as_uuid(path.stem)
        if area_id is None or area_id in known_areas:
            continue
        await store.delete_area_store(workspace_id, area_id)
        removed += 1
        logger.info("Retention: Tabellen-Store der geloeschten Area %s entfernt.", area_id)
    return removed


def _as_uuid(value: str) -> UUID | None:
    """`UUID` oder `None` — Pfadnamen sind untrusted, `UUID()` wirft sonst."""
    try:
        return UUID(value)
    except ValueError:
        return None


async def run_retention_sweeps(
    conn: asyncpg.Connection,
    result: PurgeResult,
    now: datetime | None = None,
) -> PurgeResult:
    """Haengt die drei WorkArea-/KB-Sweeps an ein Purge-Ergebnis (WP20).

    Bewusst NACH `purge_expired`: der Org-/Account-Purge loescht ganze
    Workspaces per CASCADE und hinterlaesst dabei genau die Blob-Zeilen und
    Area-Dateien, die diese Sweeps abraeumen sollen — in einem Lauf statt erst
    im naechsten.

    Die Sweeps sind voneinander unabhaengig und laufen bewusst NICHT in einer
    gemeinsamen Transaktion: jeder ist fuer sich idempotent, und ein Fehler im
    Objekt-Storage soll den Artifact-Sweep nicht zurueckrollen.
    """
    reference = now or datetime.now(UTC)
    expired = await cleanup_expired_artifacts(conn, reference)
    blob_rows, blob_objects, store_skipped = await cleanup_orphan_blobs(
        conn, build_blob_store(), reference
    )
    area_stores, unknown_dirs = await cleanup_deleted_area_stores(conn, get_table_store())
    return replace(
        result,
        expired_artifacts=expired,
        orphan_blob_rows=blob_rows,
        orphan_blob_objects=blob_objects,
        blobstore_skipped=store_skipped,
        deleted_area_stores=area_stores,
        unknown_store_dirs=unknown_dirs,
    )


async def _run() -> PurgeResult:
    try:
        conn = await asyncpg.connect(get_settings().database_url)
    except (asyncpg.PostgresError, OSError) as exc:
        raise SystemExit(f"Datenbank nicht erreichbar: {exc}") from exc
    try:
        result = await purge_expired(PgAccountPurgeRepository(conn))
        return await run_retention_sweeps(conn, result)
    finally:
        await conn.close()


def cli() -> None:
    """Console-Entrypoint fuer `who2be-purge` (Cron)."""
    result = asyncio.run(_run())
    blob_note = " (kein BlobStore konfiguriert)" if result.blobstore_skipped else ""
    dir_note = (
        f", {result.unknown_store_dirs} unbekannte(s) Store-Verzeichnis(se) gemeldet"
        if result.unknown_store_dirs
        else ""
    )
    print(
        f"Purge: {result.organizations} Org(s), {result.accounts} Account(s) "
        f"geloescht; {result.anonymized_audit_rows} Audit-Zeile(n) anonymisiert, "
        f"{result.cleaned_invitations} Invitation(s) bereinigt, "
        f"{result.cleaned_oauth_rows} OAuth-Zeile(n) geloescht.\n"
        f"Retention: {result.expired_artifacts} Artifact(s) abgelaufen, "
        f"{result.orphan_blob_rows} Blob-Zeile(n) + {result.orphan_blob_objects} "
        f"Objekt(e) verwaist{blob_note}, "
        f"{result.deleted_area_stores} Area-Store(s) entfernt{dir_note}."
    )


if __name__ == "__main__":
    cli()

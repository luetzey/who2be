"""Integrationstests der Artifact-Speicher-Quota gegen eine ECHTE Datenbank.

Die Waechter in `test_artifact_storage_quota.py` sind DB-frei — sie belegen, dass
das Gate verdrahtet und `content_bytes` in jeder Schreib-SQL genannt ist, aber
nicht, dass Postgres die SQL akzeptiert und richtig rechnet. Genau das prueft
diese Datei (Karte W8/P5, Owner-Entscheidung 2026-09-24 „ein Limit fuer alles"):

- `content_bytes` wird bei create/append/patch tatsaechlich gefuehrt, und zwar
  als GESAMTGROESSE der Zeile — dadurch zaehlt `append` den ZUWACHS.
- Ein Zeichen ist nicht ein Byte: Umlaute/CJK schlagen mit mehr Bytes zu Buche
  als `len(markdown)`.
- `STORAGE_USED_SQL` summiert Blob- UND Artifact-Bytes in einer Anweisung.
- Die Free-Grenze loest an JEDER Artifact-Schreibroute `402` aus, ohne einen
  einzigen Blob — die Luecke, durch die 15 MB/min liefen.
- Der „kein Datenverlust"-Vertrag bleibt: ueber der Grenze sind Read, Export
  und DELETE weiter offen. DELETE ist zugleich der Weg zurueck darunter.
"""

from collections.abc import Callable
from typing import Any, Literal
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from who2be_api.main import app
from who2be_api.services.storage_quota_service import STORAGE_USED_SQL
from who2be_api.testing.api_helpers import db_execute, db_fetchval, shared_area
from who2be_api.testing.workspace_setup import (
    cleanup_workspaces,
    fresh_user_id,
    setup_workspace,
)

AuthFactory = Callable[[UUID], dict[str, str]]


def _patch_quota(
    monkeypatch: pytest.MonkeyPatch,
    *,
    limit_bytes: int | None,
    edition: Literal["cloud", "onprem"] = "cloud",
) -> None:
    """Haengt ein Entitlement mit `limit_bytes` an das Gate (ohne Billing-DB).

    Wortgleich zum Muster in `test_wa_ingest._patch_storage_quota`.
    """
    from who2be_api.core.config import Settings
    from who2be_api.licensing.entitlement import Entitlement
    from who2be_api.services import storage_quota_service

    class _FakePort:
        async def resolve(self, _org_id: UUID) -> Entitlement:
            return Entitlement(
                status="active",
                features=frozenset({"core"}),
                storage_quota_bytes=limit_bytes,
            )

    monkeypatch.setattr(storage_quota_service, "get_settings", lambda: Settings(edition=edition))
    monkeypatch.setattr(
        storage_quota_service, "build_entitlement_port", lambda _pool, _settings: _FakePort()
    )


def _create(
    client: TestClient, prefix: str, auth: dict[str, str], area_id: str, **overrides: Any
) -> Any:
    body: dict[str, Any] = {
        "title": "Notiz",
        "content_md": "Erster Absatz.",
        "occurred_at": "2026-08-01T12:00:00Z",
    }
    body.update(overrides)
    return client.post(f"{prefix}/work-areas/{area_id}/artifacts", json=body, headers=auth)


def _content_bytes(artifact_id: str) -> int:
    return int(
        db_fetchval("SELECT content_bytes FROM wa_artifact WHERE id = $1::uuid", artifact_id) or 0
    )


def _tatsaechliche_bytes(artifact_id: str) -> int:
    """Die WIRKLICHE Groesse der Zeile, aus dem Content selbst berechnet.

    Unabhaengige Referenz gegen `content_bytes`: nur so kann ein Test merken,
    dass die Spalte etwas ANDERES traegt als die Gesamtgroesse (z. B. bloss den
    letzten Zuwachs). Ein Vergleich `content_bytes` gegen Differenzen von
    `content_bytes` kann das nicht — er ist wahr, was auch drinsteht.

    Teuer (detoastet die Zeile) und deshalb bewusst nur im Test: genau aus
    diesem Grund fuehrt die Produktion die materialisierte Spalte.
    """
    return int(
        db_fetchval(
            "SELECT octet_length(content::text) FROM wa_artifact WHERE id = $1::uuid", artifact_id
        )
        or 0
    )


def _used(workspace_id: UUID) -> int:
    """Der Verbrauch, wie das Gate ihn sieht — dieselbe Konstante, echtes SQL."""
    return int(db_fetchval(STORAGE_USED_SQL, workspace_id) or 0)


@pytest.mark.integration
@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db")
def test_content_bytes_traegt_gesamtgroesse_und_append_zaehlt_zuwachs(
    make_auth_headers: AuthFactory,
) -> None:
    """Zaehlweise-Entscheidung 2, gegen Postgres: die Spalte traegt die
    Gesamtgroesse, die SUMME waechst um den Zuwachs, Schrumpfen gibt frei."""
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = make_auth_headers(owner)
    prefix = f"/v1/workspaces/{ws}"
    try:
        with TestClient(app) as client:
            area_id = shared_area(client, prefix, auth, "Bytes-Area")

            created = _create(client, prefix, auth, area_id)
            assert created.status_code == 201, created.text
            artifact_id = created.json()["id"]

            after_create = _content_bytes(artifact_id)
            # Die jsonb-Serialisierung traegt Block-Overhead — sie ist GROESSER
            # als der rohe Markdown. Genau deshalb zaehlt die Quota die
            # gespeicherte Groesse und nicht `len(content_md)`.
            assert after_create > len("Erster Absatz.")
            assert after_create == _tatsaechliche_bytes(artifact_id)
            assert _used(ws) == after_create, (
                "Die Verbrauchssumme muss den Artifact-Text enthalten — ohne einen einzigen Blob."
            )

            # ZWEI Appends, jeder deutlich groesser als der Ursprungstext. Zwei,
            # weil sich „Gesamtgroesse" und „letzter Zuwachs" erst ab dem
            # zweiten unuebersehbar unterscheiden; deutlich groesser, damit kein
            # Assert daran haengt, dass der angehaengte Text zufaellig laenger
            # ist als der erste Absatz.
            gemessen = [after_create]
            letzte = created
            for i in range(2):
                letzte = client.post(
                    f"{prefix}/wa-artifacts/{artifact_id}/append",
                    json={"content_md": f"Angehaengter Absatz {i}. " + "x" * 500},
                    headers=auth,
                )
                assert letzte.status_code == 200, letzte.text
                jetzt = _content_bytes(artifact_id)

                # AK „append zaehlt den Zuwachs", gegen eine UNABHAENGIGE
                # Referenz: die Spalte muss die tatsaechliche Gesamtgroesse der
                # Zeile tragen. Traegt sie stattdessen nur den angehaengten
                # Block, faellt genau hier — und zwar beim ersten Append schon.
                assert jetzt == _tatsaechliche_bytes(artifact_id), (
                    f"content_bytes ({jetzt}) muss die Gesamtgroesse der Zeile "
                    f"({_tatsaechliche_bytes(artifact_id)}) tragen, nicht den Zuwachs — "
                    f"sonst zaehlt die Quota nach n Appends nur den letzten."
                )
                # Die SUMME waechst um den Zuwachs, nicht um die Gesamtgroesse
                # (das waere Doppelzaehlung).
                zuwachs = jetzt - gemessen[-1]
                assert zuwachs > 500, f"Append {i}: Zuwachs {zuwachs} B, erwartet > 500 B"
                assert _used(ws) == jetzt
                gemessen.append(jetzt)

            after_append = gemessen[-1]
            # Monoton gewachsen und jeder Schritt vollstaendig erhalten: der
            # erste Append ist nicht vom zweiten ueberschrieben worden.
            assert gemessen == sorted(gemessen) and len(set(gemessen)) == 3
            assert after_append > 2 * 500

            # Patch, der SCHRUMPFT: gibt Platz frei. Ein additiver Zaehler
            # koennte das nicht — er stiege monoton.
            blocks = letzte.json()["blocks"]
            deleted = client.patch(
                f"{prefix}/wa-artifacts/{artifact_id}",
                json={
                    "expected_rev": letzte.json()["rev"],
                    "anchor": blocks[-1]["block_id"],
                    "op": "delete",
                },
                headers=auth,
            )
            assert deleted.status_code == 200, deleted.text
            assert _content_bytes(artifact_id) < after_append
            assert _content_bytes(artifact_id) == _tatsaechliche_bytes(artifact_id)
            assert _used(ws) == _content_bytes(artifact_id)
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db")
def test_mehrbyte_zeichen_zaehlen_mehr_als_zeichen(make_auth_headers: AuthFactory) -> None:
    """Zaehlweise-Entscheidung 1, gegen Postgres: Bytes, nicht Zeichen.

    Zwei Artifacts mit GLEICHER Zeichenzahl, verschiedener Byte-Laenge. Zaehlte
    die Quota Zeichen, waeren beide gleich gross — und ein Kunde mit CJK-Text
    bekaeme das Dreifache an Platz.
    """
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = make_auth_headers(owner)
    prefix = f"/v1/workspaces/{ws}"
    try:
        with TestClient(app) as client:
            area_id = shared_area(client, prefix, auth, "UTF8-Area")
            ascii_md = "a" * 40
            cjk_md = "\u6f22" * 40  # je 3 Bytes in UTF-8
            assert len(ascii_md) == len(cjk_md)

            a = _create(client, prefix, auth, area_id, title="ascii", content_md=ascii_md)
            b = _create(client, prefix, auth, area_id, title="cjk", content_md=cjk_md)
            assert a.status_code == 201 and b.status_code == 201

            ascii_bytes = _content_bytes(a.json()["id"])
            cjk_bytes = _content_bytes(b.json()["id"])
            assert cjk_bytes > ascii_bytes, (
                f"CJK ({cjk_bytes} B) muss mehr zaehlen als ASCII ({ascii_bytes} B) "
                f"— sonst zaehlt die Quota Zeichen statt Bytes."
            )
            assert _used(ws) == ascii_bytes + cjk_bytes
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db")
def test_bestandsdaten_zaehlen_nach_backfill_mit(make_auth_headers: AuthFactory) -> None:
    """Aufgabe 3: vorhandene Artifacts zaehlen ab sofort mit.

    Der Bestand wird nachgestellt, indem `content_bytes` auf den alten
    Vor-Migrations-Zustand (0) zurueckgesetzt und dann der Backfill-UPDATE aus
    0087 gefahren wird — dieselbe Anweisung, die beim Deploy laeuft.
    """
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = make_auth_headers(owner)
    prefix = f"/v1/workspaces/{ws}"
    try:
        with TestClient(app) as client:
            area_id = shared_area(client, prefix, auth, "Bestand-Area")
            created = _create(client, prefix, auth, area_id, content_md="Alter Bestand.")
            assert created.status_code == 201, created.text
            artifact_id = created.json()["id"]
            gezaehlt = _content_bytes(artifact_id)
            assert gezaehlt > 0

            # Vor-Migrations-Zustand: die Spalte stand auf dem Default 0, der
            # Text zaehlte unter KEIN Kontingent.
            db_execute(
                "UPDATE wa_artifact SET content_bytes = 0 WHERE id = $1::uuid",
                artifact_id,
            )
            assert _used(ws) == 0, "Vor dem Backfill zaehlt der Bestand nicht mit."

            # Der Backfill aus Migration 0087, wortgleich.
            db_execute(
                "UPDATE wa_artifact SET content_bytes = octet_length(content::text) "
                "WHERE content IS NOT NULL AND content_bytes = 0"
            )
            assert _content_bytes(artifact_id) == gezaehlt
            assert _used(ws) == gezaehlt, "Nach dem Backfill zaehlt der Bestand mit."
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db")
def test_free_grenze_loest_402_an_jeder_artifact_schreibroute(
    monkeypatch: pytest.MonkeyPatch, make_auth_headers: AuthFactory
) -> None:
    """Der Kern der Karte, Ende zu Ende: ohne einen einzigen Blob reicht
    Artifact-Text fuer 402 — an create, create-ohne-Area, append und patch.

    Und der „kein Datenverlust"-Vertrag haelt: Read, Export und DELETE bleiben
    offen, DELETE fuehrt zurueck unter die Grenze.
    """
    # Erst ohne Grenze aufbauen, damit der Bestand ueberhaupt entsteht.
    _patch_quota(monkeypatch, limit_bytes=None)
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = make_auth_headers(owner)
    prefix = f"/v1/workspaces/{ws}"
    try:
        with TestClient(app) as client:
            area_id = shared_area(client, prefix, auth, "Limit-Area")
            first = _create(client, prefix, auth, area_id, content_md="Bestand." * 20)
            assert first.status_code == 201, first.text
            artifact_id = first.json()["id"]
            rev = first.json()["rev"]
            block_id = first.json()["blocks"][0]["block_id"]

            belegt = _used(ws)
            assert belegt > 0
            # Kein Blob im Spiel: der Verbrauch stammt AUSSCHLIESSLICH aus
            # Artifact-Text — genau die zuvor ungedeckelte Quelle.
            assert db_fetchval("SELECT count(*) FROM wa_blob WHERE workspace_id = $1", ws) == 0

            # Grenze unter den Bestand ziehen ⇒ jeder weitere Write ist 402.
            _patch_quota(monkeypatch, limit_bytes=belegt)

            blocked_create = _create(client, prefix, auth, area_id, content_md="Noch mehr.")
            assert blocked_create.status_code == 402, blocked_create.text
            assert blocked_create.json()["reason"] == "storage_quota_exceeded"
            assert blocked_create.json()["params"]["limit"] == belegt

            blocked_append = client.post(
                f"{prefix}/wa-artifacts/{artifact_id}/append",
                json={"content_md": "Angehaengt."},
                headers=auth,
            )
            assert blocked_append.status_code == 402, blocked_append.text

            blocked_patch = client.patch(
                f"{prefix}/wa-artifacts/{artifact_id}",
                json={
                    "expected_rev": rev,
                    "anchor": block_id,
                    "op": "replace",
                    "content_md": "Ersetzt.",
                },
                headers=auth,
            )
            assert blocked_patch.status_code == 402, blocked_patch.text

            # `POST /artifacts` (private Area) laeuft ueber dasselbe Gate; ein
            # Mensch bekaeme dort 422, deshalb genuegt hier der Beleg, dass das
            # Gate VOR der Semantikpruefung greift — 402, nicht 422.
            human_private = client.post(
                f"{prefix}/artifacts",
                json={
                    "title": "Privat",
                    "content_md": "x",
                    "occurred_at": "2026-08-01T12:00:00Z",
                },
                headers=auth,
            )
            assert human_private.status_code == 402, human_private.text

            # Kein Datenverlust: Lesen, Exportieren, Listen bleiben offen.
            assert (
                client.get(f"{prefix}/wa-artifacts/{artifact_id}", headers=auth).status_code == 200
            )
            assert (
                client.get(f"{prefix}/wa-artifacts/{artifact_id}/export", headers=auth).status_code
                == 200
            )

            # Und der Weg zurueck unter die Grenze ist offen.
            assert (
                client.delete(f"{prefix}/wa-artifacts/{artifact_id}", headers=auth).status_code
                == 204
            )
            assert _used(ws) == 0
            assert _create(client, prefix, auth, area_id).status_code == 201
    finally:
        cleanup_workspaces([owner])

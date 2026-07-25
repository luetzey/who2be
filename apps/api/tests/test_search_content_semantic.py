"""Semantische Passage-Suche (ADR-0046, Welle 2) — gegen echtes pgvector.

Diese Tests belegen, was MEIN Code leistet: „gegeben brauchbare Vektoren, wird
die richtige Passage gefunden, gerankt und ausgeliefert". Was sie NICHT
belegen, ist die Qualitaet eines konkreten Modells — das ist eine Eigenschaft
des Modells, keine des Retrievals.

Deshalb liefert der Stub-Port hier HANDGESCHRIEBENE Vektoren mit bekannter
Geometrie. Das ist bewusst kein Ersatz-Modell, sondern ein Messinstrument: die
Beziehungen zwischen den Vektoren sind exakt bekannt, also ist auch die
erwartete Trefferlage exakt bekannt — und die Tests laufen ohne Modell-Download
und ohne Netz.

Abgedeckt: semantischer Treffer ohne jede Wortueberschneidung, cross-linguale
Trefferlage, die Aehnlichkeitsschwelle (kein Zufallstreffer bei unpassender
Frage), Hybrid-Fusion, Degradation ohne Port und Best-Effort im Schreibpfad.
"""

import asyncio
import math
import zlib
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import asyncpg
import jwt
import pytest
from fastapi.testclient import TestClient

from who2be_api.core import security
from who2be_api.core.config import Settings, get_settings
from who2be_api.core.migrations import MIGRATIONS_DIR, apply_migrations
from who2be_api.embeddings import reset_embedding_port, set_embedding_port
from who2be_api.main import app
from who2be_api.repositories.content_chunk_repository import reset_vector_support
from who2be_api.testing.workspace_setup import cleanup_workspaces, fresh_user_id, setup_workspace

_TEST_SECRET = "integration-test-jwt-secret-padding-0123456789"
_DIMS = 384
# Hintere Achsen fuer „unbekannte Themen" — reichlich, damit zwei
# verschiedene Fremdtexte praktisch nie kollidieren.
_UNKNOWN_AXES = 100

# Themen-Achsen: jeder Text bekommt einen Vektor auf genau einer Achse, damit
# die Cosinus-Aehnlichkeit zwischen zwei Texten exakt vorhersagbar ist —
# 1.0 innerhalb einer Achse, 0.0 zwischen verschiedenen Achsen.
_AXES = {
    "kontakt": 0,
    "versand": 1,
    "eskalation": 2,
}


def _axis_vector(axis: int) -> list[float]:
    vector = [0.0] * _DIMS
    vector[axis] = 1.0
    return vector


class _StubEmbedder:
    """Deterministischer Port: bildet Text ueber Stichworte auf Themen-Achsen ab.

    Kein Modell, keine Zufallszahlen — die Achse ergibt sich aus dem Text, und
    damit ist jede erwartete Aehnlichkeit im Test nachrechenbar.
    """

    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    @property
    def dimensions(self) -> int:
        return _DIMS

    @staticmethod
    def _axis_for(text: str) -> int:
        lowered = text.lower()
        # Deutsche UND englische Stichworte auf DIESELBE Achse — genau das
        # macht ein multilinguales Modell, und genau das kann Volltext nicht.
        if any(w in lowered for w in ("kontakt", "e-mail", "email", "erreicht", "contacted")):
            return _AXES["kontakt"]
        if any(w in lowered for w in ("versand", "lieferung", "shipping", "delivery")):
            return _AXES["versand"]
        if any(w in lowered for w in ("eskalation", "teamleitung", "escalat")):
            return _AXES["eskalation"]
        # Unbekanntes Thema: eine aus dem Text abgeleitete Achse im hinteren
        # Bereich. Wichtig, dass sie TEXTABHAENGIG ist — landeten alle
        # unbekannten Texte auf derselben Achse, waeren zwei voellig
        # verschiedene Themen laut Stub identisch, und der Schwellwert-Test
        # wuerde etwas anderes messen, als er behauptet. `crc32` statt `hash`,
        # weil Pythons String-Hash pro Prozess randomisiert ist.
        return _DIMS - 1 - (zlib.crc32(lowered.encode()) % _UNKNOWN_AXES)

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        self.calls.append(list(texts))
        return [_axis_vector(self._axis_for(t)) for t in texts]


class _BrokenEmbedder:
    """Port, der immer scheitert — fuer den Best-Effort-Nachweis."""

    @property
    def dimensions(self) -> int:
        return _DIMS

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        raise RuntimeError("Modell nicht ladbar")


@pytest.fixture(autouse=True)
def _clean_port() -> Any:
    reset_embedding_port()
    reset_vector_support()
    yield
    reset_embedding_port()
    reset_vector_support()


def _db_reachable() -> bool:
    async def _check() -> bool:
        try:
            conn = await asyncpg.connect(get_settings().database_url)
        except (asyncpg.PostgresError, OSError):
            return False
        await conn.close()
        return True

    return asyncio.run(_check())


def _prepare_db() -> None:
    async def _run() -> None:
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            await apply_migrations(conn, MIGRATIONS_DIR)
        finally:
            await conn.close()

    asyncio.run(_run())


def _auth(owner_id: UUID) -> dict[str, str]:
    token = jwt.encode(
        {
            "sub": str(owner_id),
            "aud": "authenticated",
            "role": "authenticated",
            "exp": datetime.now(UTC) + timedelta(hours=1),
        },
        _TEST_SECRET,
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


def _para(block_id: str, text: str) -> dict[str, Any]:
    return {
        "id": block_id,
        "type": "paragraph",
        "content": [{"type": "text", "text": text, "styles": {}}],
    }


def _heading(block_id: str, text: str) -> dict[str, Any]:
    return {
        "id": block_id,
        "type": "heading",
        "props": {"level": 1},
        "content": [{"type": "text", "text": text, "styles": {}}],
    }


def _activate(client: TestClient, base: str, entity_id: str, auth: dict[str, str]) -> None:
    for to in ("review", "active"):
        r = client.post(f"{base}/{entity_id}/versions/1/transition", json={"to": to}, headers=auth)
        assert r.status_code in (200, 201), r.text


def _seed_resource(
    client: TestClient, prefix: str, auth: dict[str, str], name: str, blocks: list[dict[str, Any]]
) -> str:
    rid = client.post(
        f"{prefix}/resources",
        json={
            "name": name,
            # Nicht leer: der Promote-Validator verlangt eine Beschreibung.
            # Bewusst ohne Wort aus irgendeiner Testanfrage.
            "content": {"description": "Interne Dokumentation", "blocks": blocks, "tags": []},
        },
        headers=auth,
    ).json()["id"]
    _activate(client, f"{prefix}/resources", rid, auth)
    return str(rid)


def _vector_count(entity_id: str) -> int:
    async def _run() -> int:
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            count: int = await conn.fetchval(
                "SELECT count(*) FROM content_chunk "
                "WHERE entity_id = $1 AND content_vector IS NOT NULL",
                UUID(entity_id),
            )
            return count
        finally:
            await conn.close()

    return asyncio.run(_run())


@pytest.mark.integration
def test_semantic_hit_without_any_shared_word(monkeypatch: pytest.MonkeyPatch) -> None:
    """Der Kernfall: die Frage teilt KEIN Wort mit der Passage.

    Volltext kann das strukturell nicht — es gibt keinen gemeinsamen Wortstamm.
    Der Vektor-Zweig findet die Passage trotzdem.
    """
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()
    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    set_embedding_port(_StubEmbedder())

    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = _auth(owner)
    prefix = f"/v1/workspaces/{ws}"

    try:
        with TestClient(app) as client:
            rid = _seed_resource(
                client,
                prefix,
                auth,
                "Handbuch",
                [
                    _heading("h-kontakt", "Kontaktpraeferenz"),
                    _para("p1", "Der Kunde wird per E-Mail benachrichtigt."),
                    _heading("h-versand", "Versand"),
                    _para("p2", "Die Lieferung erfolgt immer freitags."),
                ],
            )
            assert _vector_count(rid) > 0, "Aktivierung haette Vektoren schreiben muessen"

            # „wie wird der Kunde erreicht" teilt mit der Zielpassage kein
            # inhaltstragendes Wort — im Volltext also kein Treffer.
            text_only = client.get(
                f"{prefix}/search/content",
                params={"q": "wie wird der Kunde erreicht", "mode": "text"},
                headers=auth,
            ).json()
            assert [h["block_id"] for h in text_only] == []

            semantic = client.get(
                f"{prefix}/search/content",
                params={"q": "wie wird der Kunde erreicht", "mode": "semantic"},
                headers=auth,
            )
            assert semantic.status_code == 200, semantic.text
            assert [h["block_id"] for h in semantic.json()] == ["h-kontakt"]
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
def test_cross_lingual_hit(monkeypatch: pytest.MonkeyPatch) -> None:
    """Deutsche Anfrage findet englischen Inhalt — das Argument fuer Vektoren.

    Volltext kann das prinzipiell nicht: 'german' und 'english' teilen keine
    Wortstaemme, und `'simple'` teilt keine Woerter.
    """
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()
    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    set_embedding_port(_StubEmbedder())

    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = _auth(owner)
    prefix = f"/v1/workspaces/{ws}"

    try:
        with TestClient(app) as client:
            _seed_resource(
                client,
                prefix,
                auth,
                "Handbook",
                [
                    _heading("h-en", "Contact policy"),
                    _para("p1", "The customer is contacted by email."),
                ],
            )

            assert (
                client.get(
                    f"{prefix}/search/content",
                    params={"q": "Kontaktweg des Kunden", "mode": "text"},
                    headers=auth,
                ).json()
                == []
            )

            found = client.get(
                f"{prefix}/search/content",
                params={"q": "Kontaktweg des Kunden", "mode": "semantic"},
                headers=auth,
            ).json()
            assert [h["block_id"] for h in found] == ["h-en"]
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
def test_unrelated_question_returns_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Die Aehnlichkeitsschwelle verhindert Beinahe-Zufallstreffer.

    Ohne Schranke liefert eine Vektor-Suche IMMER die k naechsten Passagen —
    der Agent bekaeme auf jede Frage etwas und wuerde es fuer eine Antwort
    halten. Genau das ist hier ausgeschlossen.
    """
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()
    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    set_embedding_port(_StubEmbedder())

    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = _auth(owner)
    prefix = f"/v1/workspaces/{ws}"

    try:
        with TestClient(app) as client:
            _seed_resource(
                client,
                prefix,
                auth,
                "Handbuch",
                [_heading("h-kontakt", "Kontakt"), _para("p1", "Per E-Mail erreichbar.")],
            )

            res = client.get(
                f"{prefix}/search/content",
                params={"q": "Bilanzierung nach HGB", "mode": "semantic"},
                headers=auth,
            )
            assert res.status_code == 200, res.text
            assert res.json() == []
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
def test_hybrid_fuses_both_rankings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Hybrid findet die Vereinigung — was NUR lexikalisch und NUR semantisch trifft."""
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()
    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    set_embedding_port(_StubEmbedder())

    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = _auth(owner)
    prefix = f"/v1/workspaces/{ws}"

    try:
        with TestClient(app) as client:
            _seed_resource(
                client,
                prefix,
                auth,
                "Handbuch",
                [
                    # Semantischer Treffer (Thema Kontakt), ohne das Suchwort.
                    _heading("h-kontakt", "Kontaktpraeferenz"),
                    _para("p1", "Der Kunde wird per E-Mail benachrichtigt."),
                    # Lexikalischer Treffer: enthaelt das Suchwort woertlich,
                    # gehoert aber thematisch woanders hin.
                    _heading("h-woertlich", "Sonderfall Grosskunde"),
                    _para("p2", "Ein Grosskunde erreicht uns ueber den Key-Account."),
                ],
            )
            query = "Grosskunde erreicht"

            text_hits = {
                h["block_id"]
                for h in client.get(
                    f"{prefix}/search/content",
                    params={"q": query, "mode": "text"},
                    headers=auth,
                ).json()
            }
            semantic_hits = {
                h["block_id"]
                for h in client.get(
                    f"{prefix}/search/content",
                    params={"q": query, "mode": "semantic"},
                    headers=auth,
                ).json()
            }
            hybrid_hits = {
                h["block_id"]
                for h in client.get(
                    f"{prefix}/search/content",
                    params={"q": query, "mode": "hybrid", "limit": 20},
                    headers=auth,
                ).json()
            }

            assert "h-woertlich" in text_hits
            assert "h-kontakt" in semantic_hits
            # Der Punkt von RRF: die Vereinigung, nicht der Schnitt.
            assert text_hits <= hybrid_hits
            assert semantic_hits <= hybrid_hits
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
def test_without_a_port_everything_degrades_to_text(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ohne Embedding-Port bleibt alles nutzbar — nur eben lexikalisch.

    Das ist der Normalfall einer Installation ohne die optionale
    Dependency-Gruppe und darf sich nie als Fehler zeigen.
    """
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()
    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    set_embedding_port(None)

    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = _auth(owner)
    prefix = f"/v1/workspaces/{ws}"

    try:
        with TestClient(app) as client:
            rid = _seed_resource(
                client,
                prefix,
                auth,
                "Handbuch",
                [_heading("h1", "Eskalation"), _para("p1", "Ab Stufe drei die Teamleitung.")],
            )
            # Kein Port ⇒ keine Vektoren, aber sehr wohl Passagen.
            assert _vector_count(rid) == 0

            for mode in ("auto", "text", "semantic", "hybrid"):
                res = client.get(
                    f"{prefix}/search/content",
                    params={"q": "Teamleitung", "mode": mode},
                    headers=auth,
                )
                assert res.status_code == 200, (mode, res.text)
                assert [h["block_id"] for h in res.json()] == ["h1"], mode
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
def test_failing_embedder_does_not_block_activation(monkeypatch: pytest.MonkeyPatch) -> None:
    """Best-Effort: ein kaputtes Modell darf keine Aktivierung verhindern.

    Der Statuswechsel ist die fachliche Handlung; der Vektor nur eine
    Beschleunigung des Suchens.
    """
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()
    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    set_embedding_port(_BrokenEmbedder())

    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = _auth(owner)
    prefix = f"/v1/workspaces/{ws}"

    try:
        with TestClient(app) as client:
            rid = _seed_resource(
                client,
                prefix,
                auth,
                "Handbuch",
                [_heading("h1", "Eskalation"), _para("p1", "Ab Stufe drei die Teamleitung.")],
            )
            # Aktivierung ist durchgelaufen, Passagen sind da, Vektoren nicht.
            assert _vector_count(rid) == 0
            found = client.get(
                f"{prefix}/search/content", params={"q": "Teamleitung"}, headers=auth
            ).json()
            assert [h["block_id"] for h in found] == ["h1"]
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
def test_backfill_fills_missing_vectors(monkeypatch: pytest.MonkeyPatch) -> None:
    """Der Backfill holt Vektoren nach, die beim Schreiben ausgefallen sind."""
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()
    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    set_embedding_port(_BrokenEmbedder())

    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = _auth(owner)
    prefix = f"/v1/workspaces/{ws}"

    try:
        with TestClient(app) as client:
            rid = _seed_resource(
                client,
                prefix,
                auth,
                "Handbuch",
                [_heading("h-kontakt", "Kontakt"), _para("p1", "Per E-Mail erreichbar.")],
            )
            assert _vector_count(rid) == 0

            from who2be_api.core.chunk_backfill import backfill_vectors
            from who2be_api.core.db import init_connection

            async def _run() -> int:
                conn = await asyncpg.connect(get_settings().database_url)
                try:
                    await init_connection(conn)
                    return await backfill_vectors(conn, _StubEmbedder())
                finally:
                    await conn.close()

            embedded = asyncio.run(_run())
            assert embedded > 0
            assert _vector_count(rid) > 0

            # Und jetzt greift auch die Semantik.
            set_embedding_port(_StubEmbedder())
            found = client.get(
                f"{prefix}/search/content",
                params={"q": "wie wird der Kunde erreicht", "mode": "semantic"},
                headers=auth,
            ).json()
            assert [h["block_id"] for h in found] == ["h-kontakt"]
    finally:
        cleanup_workspaces([owner])


def test_stub_geometry_is_what_the_tests_assume() -> None:
    """Sichert die Annahme der Stub-Geometrie ab (laeuft ohne DB).

    Wenn diese Beziehungen nicht gelten, messen die Tests oben etwas anderes,
    als sie behaupten.
    """
    stub = _StubEmbedder()
    vectors = asyncio.run(
        stub.embed(
            [
                "Der Kunde wird per E-Mail benachrichtigt.",
                "wie wird der Kunde erreicht",
                "The customer is contacted by email.",
                "Die Lieferung erfolgt immer freitags.",
                "Bilanzierung nach HGB",
            ]
        )
    )

    def cos(a: list[float], b: list[float]) -> float:
        return sum(x * y for x, y in zip(a, b, strict=True)) / (
            math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
        )

    assert cos(vectors[0], vectors[1]) == pytest.approx(1.0)  # Paraphrase
    assert cos(vectors[0], vectors[2]) == pytest.approx(1.0)  # cross-lingual
    assert cos(vectors[0], vectors[3]) == pytest.approx(0.0)  # anderes Thema
    assert cos(vectors[0], vectors[4]) == pytest.approx(0.0)  # voellig fremd


def _set_vector_column(present: bool) -> None:
    """Legt `content_chunk.content_vector` an oder entfernt sie."""

    async def _run() -> None:
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            if present:
                await conn.execute(
                    "ALTER TABLE content_chunk ADD COLUMN IF NOT EXISTS content_vector vector(384)"
                )
            else:
                await conn.execute("ALTER TABLE content_chunk DROP COLUMN IF EXISTS content_vector")
        finally:
            await conn.close()

    asyncio.run(_run())
    reset_vector_support()


@pytest.mark.integration
def test_works_without_the_vector_column(monkeypatch: pytest.MonkeyPatch) -> None:
    """On-Prem auf Standard-Postgres: pgvector fehlt, also fehlt die Spalte.

    Migration 0071 ist fuer genau diesen Fall fail-soft (sie legt die Spalte
    dann nicht an). Der Code muss das aushalten: Aktivierung, Chunk-Aufbau und
    Suche laufen weiter, nur eben rein lexikalisch. Ein Fehler hier waere fuer
    ein additives Feature ein unangemessener Preis.

    Der Test entfernt die Spalte wirklich und legt sie danach wieder an.
    """
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()
    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    # Port ist da und wuerde Vektoren liefern — die Spalte fehlt trotzdem.
    set_embedding_port(_StubEmbedder())

    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = _auth(owner)
    prefix = f"/v1/workspaces/{ws}"

    _set_vector_column(False)
    try:
        with TestClient(app) as client:
            rid = _seed_resource(
                client,
                prefix,
                auth,
                "Handbuch",
                [_heading("h1", "Eskalation"), _para("p1", "Ab Stufe drei die Teamleitung.")],
            )
            assert rid

            for mode in ("auto", "text", "semantic", "hybrid"):
                res = client.get(
                    f"{prefix}/search/content",
                    params={"q": "Teamleitung", "mode": mode},
                    headers=auth,
                )
                assert res.status_code == 200, (mode, res.text)
                assert [h["block_id"] for h in res.json()] == ["h1"], mode

            # Auch der Backfill darf nicht stolpern.
            from who2be_api.core.chunk_backfill import backfill_chunks, backfill_vectors
            from who2be_api.core.db import init_connection

            async def _run() -> int:
                conn = await asyncpg.connect(get_settings().database_url)
                try:
                    await init_connection(conn)
                    await backfill_chunks(conn)
                    return await backfill_vectors(conn, _StubEmbedder())
                finally:
                    await conn.close()

            assert asyncio.run(_run()) == 0
    finally:
        cleanup_workspaces([owner])
        _set_vector_column(True)

"""Bucket-Bootstrap: Idempotenz und Compose-Verdrahtung (#530, ADR-0048).

`scripts/blobstore-bootstrap.py` legt den Blob-Bucket auf SeaweedFS
(Nachfolger von MinIO, #525) idempotent an. Drei Dinge sind hier pruefenswert
und alle DB- und netzfrei:

1. **Idempotenz.** `bucket_exists` + `make_bucket` sind NICHT atomar. Ein
   zweiter Lauf — oder ein paralleler — darf den One-Shot nicht mit
   Exit != 0 beenden, sonst bleibt `api` haengen: es haengt per
   `service_completed_successfully` daran. Jeder ECHTE `S3Error` (nicht nur
   das verlorene Rennen) muss weiter propagieren — der One-Shot ist das Gate
   vor dem API-Start, ein stiller Erfolg waere dort das Schlimmste.
2. **Die Compose-Verdrahtung.** Dass die App den Bucket nie selbst anlegt
   (`api` haengt am Bootstrap, der Bootstrap am gesunden `seaweedfs`) und
   dass kein `minio/*`-Image mehr irgendwo im Stack steckt, ist mit dem
   Wechsel WP1 (#528) leicht zu verlieren.
3. **Das Sicherheits-Gate.** SeaweedFS' eigene Doku: „By default, if no
   credentials are configured, SeaweedFS allows anonymous access to all S3
   operations." Ohne `-s3.config` UND den gemounteten `s3.json` staende der
   Store offen — das darf nie unbemerkt zurueckkommen.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, cast

import pytest
import yaml

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT = _REPO_ROOT / "scripts" / "blobstore-bootstrap.py"
_COMPOSE = _REPO_ROOT / "docker-compose.yml"


def _load_script() -> ModuleType:
    """Laedt das Skript als Modul — der Bindestrich verbietet einen Import."""
    spec = importlib.util.spec_from_file_location("blobstore_bootstrap", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["blobstore_bootstrap"] = module
    spec.loader.exec_module(module)
    return module


class _FakeClient:
    """Minimaler Stand-in fuer `minio.Minio` — zaehlt die Aufrufe."""

    def __init__(self, *, exists: bool, make_error: Exception | None = None) -> None:
        self._exists = exists
        self._make_error = make_error
        self.made: list[str] = []

    def bucket_exists(self, bucket: str) -> bool:
        return self._exists

    def make_bucket(self, bucket: str) -> None:
        if self._make_error is not None:
            raise self._make_error
        self.made.append(bucket)


def _s3_error(code: str) -> Exception:
    """Echter `S3Error` — das Skript faengt genau diesen Typ, kein Surrogat."""
    from minio.error import S3Error

    # `response` ist als `BaseHTTPResponse` typisiert und wird hier nie
    # gelesen; der Konstruktor nimmt den Platzhalter zur Laufzeit an.
    return S3Error(
        code=code,
        message="conflict",
        resource="/who2be-blobs",
        request_id="r",
        host_id="h",
        response=cast("Any", None),
    )


def _run_with(monkeypatch: pytest.MonkeyPatch, client: _FakeClient) -> int:
    module = _load_script()
    monkeypatch.setattr(module, "Minio", lambda *a, **k: client)
    return int(module.main())


def test_creates_bucket_when_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _FakeClient(exists=False)
    assert _run_with(monkeypatch, client) == 0
    assert client.made == ["who2be-blobs"]


def test_second_run_is_a_no_op(monkeypatch: pytest.MonkeyPatch) -> None:
    # Der haeufige Fall: `docker compose up` ein zweites Mal.
    client = _FakeClient(exists=True)
    assert _run_with(monkeypatch, client) == 0
    assert client.made == []


@pytest.mark.parametrize("code", ["BucketAlreadyOwnedByYou", "BucketAlreadyExists"])
def test_lost_race_is_not_a_failure(monkeypatch: pytest.MonkeyPatch, code: str) -> None:
    # `bucket_exists` sagt Nein, zwischen Pruefung und Anlage legt ihn ein
    # anderer an (parallele Compose-Laeufe). Kein Fehler, sondern der
    # dokumentierte Idempotenz-Fall.
    client = _FakeClient(exists=False, make_error=_s3_error(code))
    assert _run_with(monkeypatch, client) == 0


def test_real_s3_error_still_propagates(monkeypatch: pytest.MonkeyPatch) -> None:
    # Ein Betriebsfehler (z. B. falsche Credentials) darf NICHT als Erfolg
    # durchgehen: der One-Shot ist das Gate vor dem API-Start.
    from minio.error import S3Error

    client = _FakeClient(exists=False, make_error=_s3_error("AccessDenied"))
    with pytest.raises(S3Error):
        _run_with(monkeypatch, client)


# --- Compose-Verdrahtung ------------------------------------------------------


def _compose() -> dict[str, Any]:
    return dict(yaml.safe_load(_COMPOSE.read_text(encoding="utf-8")))


def _assert_no_minio_image_anywhere(compose: dict[str, Any]) -> None:
    """MinIO darf nirgendwo im Stack mehr auftauchen — auch nicht als Server."""
    offenders = {
        name: svc["image"]
        for name, svc in compose["services"].items()
        if "image" in svc and str(svc["image"]).startswith("minio/")
    }
    assert not offenders, f"MinIO-Image(s) im Compose-Stack gefunden: {offenders}"


def _assert_api_waits_for_bootstrap(compose: dict[str, Any]) -> None:
    """`docker compose up --wait` darf `api` nie vor einem fertigen Bucket starten."""
    condition = compose["services"]["api"]["depends_on"]["blobstore-bootstrap"]["condition"]
    assert condition == "service_completed_successfully", condition


def _assert_bootstrap_waits_for_healthy_seaweedfs(compose: dict[str, Any]) -> None:
    """Der Bootstrap darf nicht gegen einen S3-Endpunkt laufen, der noch startet."""
    condition = compose["services"]["blobstore-bootstrap"]["depends_on"]["seaweedfs"]["condition"]
    assert condition == "service_healthy", condition


def _assert_s3_credentials_are_configured(compose: dict[str, Any]) -> None:
    """Security-Gate (WP1): ohne `-s3.config` erlaubt SeaweedFS anonymen Vollzugriff.

    Zwei unabhaengige Belege noetig: das Flag im `command` UND die gemountete
    Datei — eines ohne das andere waere kein Schutz (Flag ohne Datei crasht
    den Container, Datei ohne Flag wird nie gelesen).
    """
    seaweedfs = compose["services"]["seaweedfs"]
    command = str(seaweedfs.get("command", ""))
    assert "-s3.config=" in command, (
        "seaweedfs faehrt ohne -s3.config — SeaweedFS' eigene Doku: 'if no "
        f"credentials are configured, SeaweedFS allows anonymous access to "
        f"all S3 operations'. command={command!r}"
    )
    volumes = [str(v) for v in seaweedfs.get("volumes", [])]
    mounted = any("seaweedfs-s3.json" in v and "/etc/seaweedfs/s3.json" in v for v in volumes)
    assert mounted, f"s3.json ist nicht auf /etc/seaweedfs/s3.json gemountet. volumes={volumes}"


def test_no_minio_image_anywhere() -> None:
    _assert_no_minio_image_anywhere(_compose())


def test_api_waits_for_bootstrap_to_complete() -> None:
    _assert_api_waits_for_bootstrap(_compose())


def test_bootstrap_waits_for_seaweedfs_healthy() -> None:
    _assert_bootstrap_waits_for_healthy_seaweedfs(_compose())


def test_seaweedfs_s3_credentials_are_configured() -> None:
    _assert_s3_credentials_are_configured(_compose())

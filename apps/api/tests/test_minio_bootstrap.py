"""Bucket-Bootstrap: Idempotenz und Compose-Verdrahtung (#525, ADR-0048).

`scripts/minio-bootstrap.py` ersetzt den frueheren `minio/mc`-Container. Zwei
Dinge sind hier pruefenswert und beide DB- und netzfrei:

1. **Idempotenz.** `mc mb --ignore-existing` war in einem Flag erledigt; mit
   dem SDK sind es zwei Schritte (`bucket_exists`, dann `make_bucket`), und
   die sind NICHT atomar. Ein zweiter Lauf — oder ein paralleler — darf den
   One-Shot nicht mit Exit != 0 beenden, sonst bleibt `api` haengen: es
   haengt per `service_completed_successfully` daran.
2. **Die Compose-Verdrahtung.** Dass die App den Bucket nie selbst anlegt,
   ist eine ADR-0048-Entscheidung, die man beim Umbau leicht verliert.
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
_SCRIPT = _REPO_ROOT / "scripts" / "minio-bootstrap.py"
_COMPOSE = _REPO_ROOT / "docker-compose.yml"


def _load_script() -> ModuleType:
    """Laedt das Skript als Modul — der Bindestrich verbietet einen Import."""
    spec = importlib.util.spec_from_file_location("minio_bootstrap", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["minio_bootstrap"] = module
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
    # anderer an. Das ist kein Fehler — genau das leistete `--ignore-existing`.
    client = _FakeClient(exists=False, make_error=_s3_error(code))
    assert _run_with(monkeypatch, client) == 0


def test_real_s3_error_still_propagates(monkeypatch: pytest.MonkeyPatch) -> None:
    # Ein Betriebsfehler darf NICHT als Erfolg durchgehen: der One-Shot ist
    # das Gate vor dem API-Start.
    from minio.error import S3Error

    client = _FakeClient(exists=False, make_error=_s3_error("AccessDenied"))
    with pytest.raises(S3Error):
        _run_with(monkeypatch, client)


# --- Compose-Verdrahtung ------------------------------------------------------


def _compose() -> dict[str, Any]:
    return dict(yaml.safe_load(_COMPOSE.read_text(encoding="utf-8")))


def test_bootstrap_pulls_no_separate_image() -> None:
    """Der Grund des Umbaus: kein eigenes CLI-Image mehr in der Lieferkette."""
    compose = _compose()
    bootstrap = compose["services"]["minio-bootstrap"]
    assert "image" not in bootstrap, "Der One-Shot soll das API-Image bauen, keines ziehen."
    assert bootstrap["build"] == compose["services"]["api"]["build"]
    # Ueber die geparste YAML, nicht ueber den Rohtext: `minio/mc` steht als
    # Begruendung im Kommentar daneben und soll dort auch stehen bleiben.
    images = {svc["image"] for svc in compose["services"].values() if "image" in svc}
    assert not [img for img in images if img.startswith("minio/mc")]


def test_api_still_waits_for_the_bucket() -> None:
    """ADR-0048: der Bucket steht VOR dem API-Start — nie durch die App selbst."""
    api = _compose()["services"]["api"]
    assert api["depends_on"]["minio-bootstrap"]["condition"] == "service_completed_successfully"

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
import os
import subprocess
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


# --- Erster Kontakt: S3 hoert noch nicht zu (Folge #932) ----------------------
#
# Nach SeaweedFS 4.48 war der Master gesund, das S3-Gateway auf 8333 aber noch
# nicht offen: der Bootstrap brach mit `Connection refused` ab, `api` startete
# nie. Der Bootstrap wartet jetzt mit Backoff (~60 s) und bricht danach klar ab.


def _refused() -> Exception:
    """Genau der Fehler, den das SDK bei geschlossenem Port wirft (urllib3)."""
    from urllib3.exceptions import MaxRetryError, NewConnectionError

    cause = NewConnectionError(cast("Any", None), "[Errno 111] Connection refused")
    return MaxRetryError(cast("Any", None), "/who2be-blobs?location=", reason=cause)


class _LateClient(_FakeClient):
    """S3 antwortet erst nach `refusals` abgewiesenen Verbindungen."""

    def __init__(self, *, refusals: int, exists: bool = False) -> None:
        super().__init__(exists=exists)
        self.refusals = refusals
        self.calls = 0

    def bucket_exists(self, bucket: str) -> bool:
        self.calls += 1
        if self.calls <= self.refusals:
            raise _refused()
        return super().bucket_exists(bucket)

    def make_bucket(self, bucket: str) -> None:
        # Auch das Anlegen darf erst nach dem ersten erfolgreichen Kontakt kommen.
        assert self.calls > self.refusals, "make_bucket vor erreichbarem S3"
        super().make_bucket(bucket)


class _Clock:
    """Virtuelle Uhr: `sleep` schiebt `now` vor, der Test wartet nie echt."""

    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


def _run_late(monkeypatch: pytest.MonkeyPatch, client: _FakeClient) -> tuple[int, _Clock]:
    module = _load_script()
    clock = _Clock()
    monkeypatch.setattr(module, "Minio", lambda *a, **k: client)
    # Die Defaults von `_first_contact` sind beim Laden gebunden — deshalb
    # die Funktion mit der virtuellen Uhr neu verdrahten.
    original = module._first_contact
    monkeypatch.setattr(
        module,
        "_first_contact",
        lambda c, b: original(c, b, sleep=clock.sleep, clock=clock),
    )
    return int(module.main()), clock


def test_bootstrap_survives_briefly_delayed_s3(monkeypatch: pytest.MonkeyPatch) -> None:
    # Der Vorfall: drei Verbindungen abgewiesen, dann ist S3 da.
    client = _LateClient(refusals=3)
    code, clock = _run_late(monkeypatch, client)
    assert code == 0
    assert client.made == ["who2be-blobs"]
    # Exponentieller Backoff, keine Dauerschleife im Takt der CPU.
    assert clock.sleeps == [1.0, 2.0, 4.0]


def test_backoff_is_capped(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _LateClient(refusals=6, exists=True)
    code, clock = _run_late(monkeypatch, client)
    assert code == 0
    assert clock.sleeps == [1.0, 2.0, 4.0, 8.0, 8.0, 8.0]


def test_bootstrap_gives_up_clearly_after_budget(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # S3 kommt nie: kein Endlos-Warten, sondern Exit 1 mit lesbarer Ursache.
    client = _LateClient(refusals=10_000)
    code, clock = _run_late(monkeypatch, client)
    assert code == 1
    assert client.made == []
    assert clock.now == pytest.approx(60.0)
    err = capsys.readouterr().err
    assert "nicht erreichbar" in err and "Abbruch" in err


def test_s3_error_is_not_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    # Ein 403 ist eine Antwort, kein „noch nicht da": sofort scheitern.
    from minio.error import S3Error

    class _Denied(_FakeClient):
        calls = 0

        def bucket_exists(self, bucket: str) -> bool:
            _Denied.calls += 1
            raise _s3_error("AccessDenied")

    with pytest.raises(S3Error):
        _run_late(monkeypatch, _Denied(exists=False))
    assert _Denied.calls == 1


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


# --- Healthcheck: S3-Port muss antworten (Folge #932) --------------------------
#
# Der Healthcheck-Befehl wird hier AUSGEFUEHRT, nicht nur gelesen: ein falsches
# `wget` im PATH spielt die Lagen des Vorfalls nach (Master gruen, S3 refused /
# S3 antwortet 403 / Master rot). busybox-wget endet bei 403 und bei refused
# gleichermassen mit Exit 1 und schreibt mit `-S` die Statuszeile auf stderr —
# genau das bildet das Double nach (gemessen am Image 4.48).

_ALL_COMPOSES = (
    _COMPOSE,
    _REPO_ROOT / "deploy" / "dokploy" / "docker-compose.yml",
    _REPO_ROOT / "deploy" / "hetzner" / "who2be" / "docker-compose.yml",
)

_FAKE_WGET = """#!/bin/sh
for a in "$@"; do url="$a"; done
case "$url" in
  *:9333/*) state="$MASTER" ;;
  *:8333/*) state="$S3" ;;
  *) state=refused ;;
esac
case "$state" in
  ok) echo '  HTTP/1.1 200 OK' >&2; exit 0 ;;
  403) echo '  HTTP/1.1 403 Forbidden' >&2
       echo 'wget: server returned error: HTTP/1.1 403 Forbidden' >&2; exit 1 ;;
  404) echo '  HTTP/1.1 404 Not Found' >&2; exit 1 ;;
  *) echo "wget: can't connect to remote host (127.0.0.1): Connection refused" >&2; exit 1 ;;
esac
"""


def _healthcheck_shell(path: Path) -> str:
    compose = yaml.safe_load(path.read_text(encoding="utf-8"))
    test = compose["services"]["seaweedfs"]["healthcheck"]["test"]
    assert test[0] == "CMD-SHELL", f"{path}: Healthcheck braucht eine Shell (Pipe): {test!r}"
    return str(test[1])


def _run_healthcheck(tmp_path: Path, command: str, *, master: str, s3: str) -> int:
    fake = tmp_path / "wget"
    fake.write_text(_FAKE_WGET, encoding="utf-8")
    fake.chmod(0o755)
    env = {**os.environ, "PATH": f"{tmp_path}:{os.environ['PATH']}", "MASTER": master, "S3": s3}
    return subprocess.run(["sh", "-c", command], env=env, check=False).returncode


@pytest.mark.parametrize("path", _ALL_COMPOSES, ids=lambda p: str(p.relative_to(_REPO_ROOT)))
@pytest.mark.parametrize(
    ("master", "s3", "healthy"),
    [
        ("ok", "refused", False),  # der Vorfall nach 4.48
        ("ok", "403", True),  # anonym gegen S3 mit Credentials: Antwort = bereit
        ("ok", "ok", True),
        ("refused", "403", False),
    ],
)
def test_seaweedfs_healthcheck_requires_s3_answer(
    tmp_path: Path, path: Path, master: str, s3: str, healthy: bool
) -> None:
    code = _run_healthcheck(tmp_path, _healthcheck_shell(path), master=master, s3=s3)
    assert (code == 0) is healthy, f"{path}: master={master} s3={s3} -> exit {code}"


@pytest.mark.parametrize("path", _ALL_COMPOSES, ids=lambda p: str(p.relative_to(_REPO_ROOT)))
def test_seaweedfs_healthcheck_avoids_healthz_and_has_start_period(path: Path) -> None:
    # effect-exempt: seaweedfs#8243 (`/healthz` = Bucket-Name -> 404) und die
    # Anlaufzeit sind Konfigurationswerte ohne ausfuehrbares Subjekt.
    health = yaml.safe_load(path.read_text(encoding="utf-8"))["services"]["seaweedfs"][
        "healthcheck"
    ]
    assert "healthz" not in str(health["test"]), path
    seconds = int(str(health["start_period"]).removesuffix("s"))
    assert seconds >= 30, f"{path}: start_period {health['start_period']} zu knapp"

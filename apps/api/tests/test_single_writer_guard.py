"""Der Tabellen-Store vertraegt genau EINEN Schreib-Prozess (ADR-0049-Nachtrag).

Hintergrund: `tablestore/engine.py` serialisiert Writes ueber einen
`asyncio.Lock` pro Area — der wirkt nur INNERHALB eines Prozesses. Mit
mehreren Workern oder Containern gaebe es zwei Locks auf derselben
SQLite-Datei; uebrig bliebe `busy_timeout`, und auf einem Netz-Dateisystem
ist SQLite-Locking laut SQLite-Doku unzuverlaessig. Die Folge waere stille
Korruption, kein Fehler.

Zwei Schutzschichten, beide hier geprueft:

1. **Start-Guard** — bricht den Boot bei `WEB_CONCURRENCY`/`--workers` ab.
2. **Compose-Drift** — die Deploy-Dateien duerfen den `api`-Dienst weder
   replizieren noch mit `--workers` starten.

Der Drift-Test ist bewusst dabei: der Volume-Fehler vom selben Tag entstand
genau so — eine Compose-Aenderung, die fuer sich plausibel aussah und deren
Folge erst im Betrieb sichtbar wurde. Ein Kommentar in der YAML allein haelt
niemanden auf.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from who2be_api.main import (
    MultiWorkerNotSupportedError,
    _configured_worker_count,
    _guard_single_writer_process,
)

_REPO_ROOT = Path(__file__).resolve().parents[3]
_COMPOSE_FILES = [
    _REPO_ROOT / "deploy" / "dokploy" / "docker-compose.yml",
    _REPO_ROOT / "deploy" / "hetzner" / "who2be" / "docker-compose.yml",
]


# --- Start-Guard -------------------------------------------------------------


@pytest.mark.parametrize("value", ["2", "4", "16"])
def test_web_concurrency_bricht_den_start_ab(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    """Mehrere Worker per Env ⇒ Abbruch, nicht Warnung."""
    monkeypatch.setenv("WEB_CONCURRENCY", value)
    with pytest.raises(MultiWorkerNotSupportedError) as excinfo:
        _guard_single_writer_process()
    message = str(excinfo.value)
    # Die Meldung muss zum ADR fuehren UND die eigene Grenze nennen — sonst
    # haelt ein Betreiber das Schweigen des Guards faelschlich fuer Beleg,
    # dass die Betriebsgrenze eingehalten ist.
    assert "ADR-0049" in message
    assert "CONTAINER" in message, message


def test_workers_argument_bricht_den_start_ab(monkeypatch: pytest.MonkeyPatch) -> None:
    """Dasselbe ueber die Kommandozeile — der uebliche Performance-Reflex."""
    monkeypatch.delenv("WEB_CONCURRENCY", raising=False)
    monkeypatch.setattr(
        "who2be_api.main.sys.argv",
        ["uvicorn", "who2be_api.main:app", "--workers", "4", "--port", "8000"],
    )
    with pytest.raises(MultiWorkerNotSupportedError):
        _guard_single_writer_process()


@pytest.mark.parametrize("value", ["", "1"])
def test_ein_worker_startet_normal(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    """Der Regelfall — und der leere Wert darf nicht als 'viele' zaehlen."""
    monkeypatch.setenv("WEB_CONCURRENCY", value)
    monkeypatch.setattr("who2be_api.main.sys.argv", ["uvicorn", "who2be_api.main:app"])
    _guard_single_writer_process()


def test_unparsbarer_wert_blockiert_den_start_nicht(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ein Tippfehler in der Env darf keine Instanz lahmlegen.

    Bewusste Richtung: der Guard schuetzt vor einer BEWUSSTEN Fehlkonfiguration
    (`--workers 4`), nicht vor Muell. Bei Muell ist der wahrscheinlichere
    Zustand ein einzelner Worker — abbrechen waere hier der teurere Fehler.
    """
    monkeypatch.setenv("WEB_CONCURRENCY", "viele")
    assert _configured_worker_count() is None
    _guard_single_writer_process()


def test_env_hat_vorrang_vor_argv(monkeypatch: pytest.MonkeyPatch) -> None:
    """`WEB_CONCURRENCY=1` neben `--workers 4`: die Env gewinnt.

    Haelt die Praezedenz fest, damit sie nicht unbemerkt kippt — beide Quellen
    zu mischen waere die Sorte Mehrdeutigkeit, die spaeter niemand mehr
    nachvollzieht.
    """
    monkeypatch.setenv("WEB_CONCURRENCY", "1")
    monkeypatch.setattr(
        "who2be_api.main.sys.argv", ["uvicorn", "who2be_api.main:app", "--workers", "4"]
    )
    assert _configured_worker_count() == 1
    _guard_single_writer_process()


# --- Compose-Drift -----------------------------------------------------------


@pytest.mark.parametrize("compose", _COMPOSE_FILES, ids=lambda p: p.parent.name)
def test_compose_repliziert_die_api_nicht(compose: Path) -> None:
    """Kein `replicas` und kein `--workers` in den Deploy-Composes.

    Grob ueber den Dateiinhalt statt ueber ein YAML-Modell: `replicas` gehoert
    nirgendwo in diese Dateien, egal unter welchem Dienst — und ein Test, der
    erst die Service-Struktur aufloest, wuerde beim naechsten Compose-Umbau
    kaputtgehen statt zu schuetzen.
    """
    text = compose.read_text(encoding="utf-8")
    lines = [
        line
        for line in text.splitlines()
        if not line.lstrip().startswith("#")
        and (re.search(r"\breplicas\s*:", line) or "--workers" in line)
    ]
    assert lines == [], (
        f"{compose.relative_to(_REPO_ROOT)} skaliert die API horizontal — der "
        "Tabellen-Store vertraegt genau einen Schreib-Prozess je Area "
        "(ADR-0049-Nachtrag 2026-08-16). Gefunden: " + "; ".join(lines)
    )


@pytest.mark.parametrize("compose", _COMPOSE_FILES, ids=lambda p: p.parent.name)
def test_compose_erklaert_die_betriebsgrenze(compose: Path) -> None:
    """Der Grund steht dort, wo jemand skalieren wuerde.

    Ohne diesen Test verschwindet der Kommentar beim naechsten Aufraeumen, und
    die Grenze ist wieder unsichtbar — genau der Zustand, der diesen Nachtrag
    noetig gemacht hat.
    """
    text = compose.read_text(encoding="utf-8")
    assert "NICHT REPLIZIEREN" in text, compose
    assert "ADR-0049" in text, compose


def test_dockerfile_startet_ohne_worker_flag() -> None:
    """Das Image-`CMD` selbst darf keine Worker mitbringen."""
    dockerfile = (_REPO_ROOT / "apps" / "api" / "Dockerfile").read_text(encoding="utf-8")
    assert "--workers" not in dockerfile, dockerfile

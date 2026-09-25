"""Der Tabellen-Store vertraegt genau EINEN Schreib-Prozess (ADR-0049-Nachtrag).

Hintergrund: `tablestore/engine.py` serialisiert Writes ueber einen
`asyncio.Lock` pro Area — der wirkt nur INNERHALB eines Prozesses. Mit
mehreren Workern oder Containern gaebe es zwei Locks auf derselben
SQLite-Datei; uebrig bliebe `busy_timeout`, und auf einem Netz-Dateisystem
ist SQLite-Locking laut SQLite-Doku unzuverlaessig. Die Folge waere stille
Korruption, kein Fehler.

Drei Schutzschichten, alle hier geprueft:

1. **Start-Guard** — bricht den Boot bei `WEB_CONCURRENCY`/`--workers` ab.
2. **Compose-Drift** — keine Compose-Datei mit `api`-Dienst darf ihn
   replizieren, mit `--workers` starten oder per `update_config.order:
   start-first` ueberlappend austauschen lassen.
3. **Deploy-Assertion** — `deploy.sh` misst nach dem `up`, dass genau EIN
   `api`-Container laeuft, statt sich auf das Recreate-Verhalten einer
   bestimmten Compose-Version zu verlassen.

Zu (3): der Recreate-Pfad von Compose erzeugt den neuen Container, stoppt DANN
den alten und startet erst danach (`recreateContainer` in
`pkg/compose/convergence.go`, identisch in v2.20 bis v2.39) — ein Overlap
braeuchte `update_config.order: start-first`, und der Default ist `stop-first`.
Ein `up -d --wait` ohne `--scale` erzeugt damit belegt kein Fenster mit zwei
laufenden Containern. Was Annahme bleibt, ist die auf der Box installierte
Compose-Version; deshalb misst das Skript das Ergebnis.

Die Drift-Tests sind bewusst dabei: der Volume-Fehler vom selben Tag entstand
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
_DEPLOY_SCRIPT = _REPO_ROOT / "deploy" / "hetzner" / "scripts" / "deploy.sh"

# Die beiden Dateien, die die Betriebsgrenze auch ERKLAEREN muessen: die
# Deploy-Composes, an denen ein Betreiber skalieren wuerde.
_DOCUMENTED_COMPOSE_FILES = [
    _REPO_ROOT / "deploy" / "dokploy" / "docker-compose.yml",
    _REPO_ROOT / "deploy" / "hetzner" / "who2be" / "docker-compose.yml",
]


def _compose_files_with_api() -> list[Path]:
    """Jede Compose-Datei im Repo, die einen `api`-Dienst definiert.

    Abgeleitet statt aufgezaehlt: eine Liste von Hand veraltet beim naechsten
    Overlay, und genau das Overlay ist die Stelle, an der ein `replicas: 2`
    unbemerkt landet — das Hetzner-Cloud-Overlay ueberschreibt den
    `api`-Dienst und wurde von der frueheren Zwei-Datei-Liste nicht erfasst.
    """
    candidates = sorted(
        {
            *_REPO_ROOT.glob("docker-compose*.yml"),
            *(_REPO_ROOT / "deploy").rglob("docker-compose*.yml"),
        }
    )
    return [path for path in candidates if re.search(r"^\s{2}api:", path.read_text("utf-8"), re.M)]


_COMPOSE_FILES = _compose_files_with_api()


def _compose_id(path: Path) -> str:
    return str(path.relative_to(_REPO_ROOT))


def _uncommented_matches(text: str, pattern: str) -> list[str]:
    """Zeilen, die `pattern` treffen — Kommentarzeilen ausgenommen.

    Die Begruendungs-Kommentare in den Compose-Dateien nennen die verbotenen
    Formen ausdruecklich (`NICHT REPLIZIEREN`, `--workers`); ein Test, der sie
    mitzaehlte, waere garantiert rot.
    """
    return [
        line
        for line in text.splitlines()
        if not line.lstrip().startswith("#") and re.search(pattern, line)
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


@pytest.mark.parametrize("compose", _COMPOSE_FILES, ids=_compose_id)
def test_compose_repliziert_die_api_nicht(compose: Path) -> None:
    """Kein `replicas` und kein `--workers` in einer Compose-Datei mit `api`.

    Grob ueber den Dateiinhalt statt ueber ein YAML-Modell: `replicas` gehoert
    nirgendwo in diese Dateien, egal unter welchem Dienst — und ein Test, der
    erst die Service-Struktur aufloest, wuerde beim naechsten Compose-Umbau
    kaputtgehen statt zu schuetzen.
    """
    lines = _uncommented_matches(
        compose.read_text(encoding="utf-8"), r"\breplicas\s*:|\bscale\s*:|--workers"
    )
    assert lines == [], (
        f"{_compose_id(compose)} skaliert die API horizontal — der "
        "Tabellen-Store vertraegt genau einen Schreib-Prozess je Area "
        "(ADR-0049-Nachtrag 2026-08-16). Gefunden: " + "; ".join(lines)
    )


@pytest.mark.parametrize("compose", _COMPOSE_FILES, ids=_compose_id)
def test_compose_tauscht_die_api_nicht_ueberlappend_aus(compose: Path) -> None:
    """Kein `update_config` — insbesondere kein `order: start-first`.

    Das ist die eine Compose-Option, die aus dem harmlosen `up -d` ein
    Korruptionsfenster machen wuerde: `start-first` startet den neuen Task
    zuerst, "and the running tasks briefly overlap" (Compose Deploy
    Specification). Fuer die Dauer dieser Ueberlappung schreiben ZWEI
    API-Prozesse auf dieselben SQLite-Dateien.

    Verboten wird `update_config` als Ganzes, nicht nur der `start-first`-Wert:
    ein Block, der heute `stop-first` traegt, ist die Einladung, den Wert
    morgen umzustellen. Der Default ist ohnehin `stop-first` — es gibt also
    keinen Grund, ihn hinzuschreiben.
    """
    lines = _uncommented_matches(
        compose.read_text(encoding="utf-8"), r"\bupdate_config\s*:|\bstart-first\b"
    )
    assert lines == [], (
        f"{_compose_id(compose)} konfiguriert den API-Austausch — `start-first` "
        "liesse zwei API-Container ueberlappen und damit zwei Schreiber auf "
        "derselben SQLite-Datei (ADR-0049). Gefunden: " + "; ".join(lines)
    )


@pytest.mark.parametrize("compose", _DOCUMENTED_COMPOSE_FILES, ids=_compose_id)
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


# --- Deploy-Assertion --------------------------------------------------------


def _deploy_script_code() -> str:
    """`deploy.sh` ohne Kommentarzeilen — die Kommentare nennen die Formen."""
    return "\n".join(
        line
        for line in _DEPLOY_SCRIPT.read_text(encoding="utf-8").splitlines()
        if not line.lstrip().startswith("#")
    )


def test_deploy_skript_prueft_die_container_anzahl() -> None:
    """`deploy.sh` misst nach dem `up`, dass genau EIN api-Container laeuft.

    Die Messung prueft den Endzustand, nicht das Recreate-Fenster: sie laeuft
    nach `--wait`, eine transiente Ueberlappung waere zum Messzeitpunkt vorbei.
    Was sie faengt, sind DAUERHAFTE Zweitinstanzen — ein verwaister Container
    aus einem frueheren Bringup, eine von Hand gestartete zweite Instanz, ein
    gar nicht gestarteter api-Container. Gegen ein Recreate-Fenster schuetzt der
    Drift-Test auf `update_config`/`start-first` (s. o.); die Abwaegung gegen
    einen Vorab-`stop` ist in `deploy.sh` begruendet. Diese Pruefung faellt
    still weg, wenn jemand sie beim Aufraeumen entfernt. Deshalb dieser Test.
    """
    code = _deploy_script_code()
    assert "ps --status running --quiet api" in code, (
        "deploy.sh prueft nach dem `up` nicht mehr, wie viele api-Container "
        "laufen — damit ist die Betriebsgrenze (ADR-0049) unbeobachtet."
    )
    assert "exit 3" in code, "Die Pruefung muss den Deploy abbrechen, nicht nur warnen."


def test_deploy_skript_skaliert_nicht() -> None:
    """Kein `--scale` im Deploy-Pfad — sonst waere die Messung sinnlos."""
    code = _deploy_script_code()
    assert "--scale" not in code, code

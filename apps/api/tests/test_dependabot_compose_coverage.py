"""Dependabot-Abdeckung der Compose-Dateien (W8/S5).

Warum dieser Test existiert
---------------------------
Vier Dependabot-Oekosysteme waren konfiguriert, ein hartes CVE-Gate laeuft in
der CI — und die Images, die den Betrieb tragen, bekamen trotzdem keine
Meldung: ``docker`` erfasst ausschliesslich Dockerfiles, waehrend Caddy,
Postgres, GoTrue, nginx, Redis und SeaweedFS als ``image:``-Pin in
Compose-Dateien stehen. Der Befund war nicht, dass etwas falsch konfiguriert
war, sondern dass eine ganze Dateiklasse durch kein Verfahren lief.

Das ``docker-compose``-Ecosystem schliesst die Luecke. Dieser Test sichert die
Eigenschaft, die dabei wirklich zaehlt: **Vollstaendigkeit**. Eine
Teilabdeckung ist schlechter als keine, weil die nicht erfassten Dateien dann
als geprueft gelten — niemand sucht zweimal nach einer Luecke, die geschlossen
gemeldet wurde.

Der Test zaehlt deshalb ab, statt Stichproben zu ziehen: er findet jede
Compose-Datei im Repo und prueft, ob ihr Verzeichnis in ``dependabot.yml``
steht. Legt jemand spaeter einen neuen Stack an, faellt die fehlende Zeile
hier auf und nicht erst, wenn ein CVE unbemerkt vorbeigeht.

Reiner Datei-Test: kein Docker, keine DB, kein Netz.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEPENDABOT = _REPO_ROOT / ".github" / "dependabot.yml"

#: Verzeichnisse, die beim Suchen nach Compose-Dateien uebersprungen werden.
_SKIP_DIRS = frozenset({".git", "node_modules", ".venv", "venv", "dist", "build", ".worktrees"})

#: Dateinamen-Praefixe, an denen Docker Compose seine Dateien erkennt. Bewusst
#: breiter als das, was aktuell im Repo liegt: der Test soll auch eine erst
#: spaeter angelegte ``compose.yaml`` finden.
_COMPOSE_PREFIXES = ("docker-compose", "compose")


def _is_compose_file(path: Path) -> bool:
    if path.suffix not in {".yml", ".yaml"}:
        return False
    stem = path.name.split(".", 1)[0]
    return stem in _COMPOSE_PREFIXES


def _compose_files() -> list[Path]:
    found: list[Path] = []
    for path in _REPO_ROOT.rglob("*"):
        if not path.is_file():
            continue
        if _SKIP_DIRS & set(path.relative_to(_REPO_ROOT).parts):
            continue
        if _is_compose_file(path):
            found.append(path)
    return sorted(found)


def _dependabot_updates() -> list[dict[str, Any]]:
    data = yaml.safe_load(_DEPENDABOT.read_text(encoding="utf-8"))
    updates = data["updates"]
    assert isinstance(updates, list) and updates
    return updates


def _compose_entry() -> dict[str, Any]:
    entries = [u for u in _dependabot_updates() if u.get("package-ecosystem") == "docker-compose"]
    assert len(entries) == 1, (
        "Genau ein docker-compose-Eintrag erwartet — mehrere Eintraege teilen die "
        f"Abdeckung auf und machen sie schwer nachzuzaehlen (gefunden: {len(entries)})"
    )
    return entries[0]


def _covered_dirs() -> set[str]:
    entry = _compose_entry()
    dirs = entry.get("directories") or ([entry["directory"]] if "directory" in entry else [])
    assert dirs, "docker-compose-Eintrag nennt kein Verzeichnis"
    return {d.rstrip("/") or "/" for d in dirs}


def _repo_dir_of(path: Path) -> str:
    rel = path.relative_to(_REPO_ROOT).parent
    return "/" if rel == Path(".") else "/" + rel.as_posix()


_COMPOSE_FILES = _compose_files()


def test_repo_still_has_compose_files() -> None:
    """Selbsttest: findet der Sucher ueberhaupt etwas?

    Ohne diese Zusicherung wuerde der Test unten gruen bleiben, wenn die Suche
    ins Leere laeuft — die teuerste Art, einen Waechter zu verlieren, weil sie
    wie Erfolg aussieht.
    """
    assert len(_COMPOSE_FILES) >= 8, (
        f"Nur {len(_COMPOSE_FILES)} Compose-Dateien gefunden — Suche greift nicht mehr"
    )


def test_docker_compose_ecosystem_is_configured() -> None:
    """Das Ecosystem existiert ueberhaupt — das war der eigentliche Befund."""
    entry = _compose_entry()
    assert entry["schedule"]["interval"] == "weekly"


@pytest.mark.parametrize(
    "compose_file",
    _COMPOSE_FILES,
    ids=[str(p.relative_to(_REPO_ROOT)) for p in _COMPOSE_FILES],
)
def test_every_compose_file_lies_in_a_covered_directory(compose_file: Path) -> None:
    """Jede Compose-Datei liegt in einem von Dependabot erfassten Verzeichnis.

    Kein Freibrief fuer einzelne Dateien: wer eine Datei bewusst aussen lassen
    will, muss das hier sichtbar machen — nicht durch Weglassen.
    """
    directory = _repo_dir_of(compose_file)
    assert directory in _covered_dirs(), (
        f"{compose_file.relative_to(_REPO_ROOT)} liegt in {directory!r}, das in "
        ".github/dependabot.yml nicht unter docker-compose steht — die Images "
        "dieser Datei bekommen keine CVE-Meldung. Verzeichnis dort ergaenzen."
    )


def test_covered_directories_all_contain_a_compose_file() -> None:
    """Kein erfasstes Verzeichnis ohne Compose-Datei.

    Die andere Richtung derselben Frage: ein Pfad, der ins Leere zeigt (Tippfehler,
    verschobener Stack), sieht in der Konfiguration wie Abdeckung aus und ist
    keine. Dependabot meldet einen solchen Pfad nur im eigenen Job-Log.
    """
    with_file = {_repo_dir_of(p) for p in _COMPOSE_FILES}
    leer = _covered_dirs() - with_file
    assert not leer, (
        f"Verzeichnisse ohne Compose-Datei in dependabot.yml: {sorted(leer)} — "
        "Abdeckung ohne Gegenstand"
    )


def test_data_holding_majors_stay_out_of_auto_prs() -> None:
    """Postgres- und GoTrue-Majors kommen nicht als Auto-PR.

    Ein Postgres-Major verlangt ``pg_upgrade`` bzw. Dump/Restore, ein
    GoTrue-Major faehrt Auth-Migrationen im Startvorgang (RUNBOOK
    §GoTrue-Version anheben). Als gruppierter Auto-PR waeren sie ein Pfad, auf
    dem Daten verloren gehen, ohne dass jemand die Entscheidung getroffen hat.
    """
    ignored = {rule["dependency-name"] for rule in _compose_entry().get("ignore", [])}
    for name in ("postgres", "pgvector/pgvector", "supabase/postgres", "supabase/gotrue"):
        assert name in ignored, f"{name}-Major ist nicht von Auto-PRs ausgenommen"

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

import re
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


# --- Valkey statt Redis (ADR-0033-Addendum 2026-10-11, Owner D2a) ----------

#: Die drei Cloud-Overlays, die den Rate-Limit-Speicher als Dienst `redis`
#: fuehren. Der Dienstname bleibt bewusst, damit `redis://redis:6379` in allen
#: Umgebungen unveraendert gilt.
_CLOUD_OVERLAYS = (
    _REPO_ROOT / "docker-compose.cloud.yml",
    _REPO_ROOT / "deploy" / "dokploy" / "docker-compose.cloud.yml",
    _REPO_ROOT / "deploy" / "hetzner" / "who2be" / "docker-compose.cloud.yml",
)

#: `valkey/valkey:8[-.…]-alpine@sha256:<64 hex>` — Major 8, Alpine, Digest-Pin.
_VALKEY_PIN = re.compile(r"^valkey/valkey:8(?:\.\d+)*-alpine@sha256:[0-9a-f]{64}$")


class _ComposeLoader(yaml.SafeLoader):
    """SafeLoader, der Compose-Tags (``!override``, ``!reset``) durchlaesst."""


def _plain(loader: yaml.SafeLoader, _suffix: str, node: yaml.Node) -> Any:
    if isinstance(node, yaml.MappingNode):
        return loader.construct_mapping(node)
    if isinstance(node, yaml.SequenceNode):
        return loader.construct_sequence(node)
    return loader.construct_scalar(node)  # type: ignore[arg-type]


_ComposeLoader.add_multi_constructor("!", _plain)

#: Redis-Image in jeder Schreibweise (`redis:…`, `library/redis@…`, `docker.io/…`).
_REDIS_IMAGE = re.compile(r"^(?:docker\.io/)?(?:library/)?redis[:@]")


def _images(path: Path) -> list[str]:
    data = yaml.load(path.read_text(encoding="utf-8"), Loader=_ComposeLoader) or {}  # noqa: S506
    services = data.get("services") or {}
    return [str(s["image"]) for s in services.values() if isinstance(s, dict) and "image" in s]


@pytest.mark.parametrize(
    "compose_file",
    _COMPOSE_FILES,
    ids=[str(p.relative_to(_REPO_ROOT)) for p in _COMPOSE_FILES],
)
def test_no_compose_file_pins_a_redis_image(compose_file: Path) -> None:
    """Kein Redis-Image mehr, in keiner Compose-Datei.

    Redis 7.4 steht unter RSALv2/SSPLv1, Redis 8 unter RSALv2/SSPLv1/AGPLv3 —
    genau die Lizenzfrage, die der Wechsel auf Valkey abraeumt. Ein Rueckfall
    (etwa ein uebernommener Dependabot-PR auf `redis:8-alpine`) faellt hier auf.
    """
    redis = [i for i in _images(compose_file) if _REDIS_IMAGE.match(i)]
    assert not redis, (
        f"{compose_file.relative_to(_REPO_ROOT)} pinnt {redis} — der Rate-Limit-"
        "Speicher laeuft als Valkey (BSD-3), ADR-0033-Addendum 2026-10-11"
    )


@pytest.mark.parametrize(
    "overlay",
    _CLOUD_OVERLAYS,
    ids=[str(p.relative_to(_REPO_ROOT)) for p in _CLOUD_OVERLAYS],
)
def test_cloud_overlay_runs_digest_pinned_valkey(overlay: Path) -> None:
    """Der Dienst `redis` ist ein per Digest gepinntes Valkey 8 ohne Persistenz.

    Der Digest-Pin folgt dem Muster der anderen gepinnten Images: der Tag
    `8-alpine` wandert, der Digest nicht, und Dependabot hebt beide zusammen an.
    Befehl und Healthcheck muessen die Valkey-Binaries nennen; ``--save ""`` und
    ``--appendonly no`` halten den Speicher fluechtig wie bisher.
    """
    service = yaml.safe_load(overlay.read_text(encoding="utf-8"))["services"]["redis"]
    assert _VALKEY_PIN.match(service["image"]), (
        f"{overlay.relative_to(_REPO_ROOT)}: redis.image={service['image']!r} ist "
        "kein digest-gepinntes valkey/valkey:8-alpine"
    )
    assert service["command"] == ["valkey-server", "--save", "", "--appendonly", "no"]
    assert service["healthcheck"]["test"] == ["CMD", "valkey-cli", "ping"]

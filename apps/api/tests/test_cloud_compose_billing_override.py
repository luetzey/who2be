"""Compose-Verdrahtung der Betreiber-Allowlist (ADR-0028, Testblocker T1).

`WHO2BE_BILLING_OVERRIDE_OPERATORS` ist die Allowlist des Override-Endpoints
(`who2be_billing/router.py#_override_operator_ids`). Das Gate ist fail-closed:
eine leere oder fehlende Variable bedeutet nicht „offen", sondern „niemand darf
schreiben" — jeder Aufruf endet in 403.

Genau daraus folgt die Pruefbarkeit hier. Stand der Variable **in der `.env`**
belegt gar nichts; entscheidend ist, dass Compose sie in die `api`-Umgebung
durchreicht. Fehlt die eine Zeile, laeuft der Stack fehlerfrei hoch und der als
Default beworbene Weg „Pro ohne Mollie setzen" ist trotzdem tot — ein Fehler,
der sich nur am 403 zeigt, nicht am Start. Das ist die teure Variante, und
deshalb steht sie in einem Test.

Bewusst DB- und daemonfrei: geprueft wird die geparste Compose-Datei, nicht ein
laufender Container. `docker compose config` braeuchte einen Daemon und liefe in
CI nicht — die YAML-Ebene traegt die Aussage vollstaendig, weil `environment`
genau die Liste ist, die Compose an den Container weitergibt.

Beide Cloud-Overlays gelten, nicht nur das gemeldete: der Root-Stack (lokale
Cloud-Paritaet) hatte dieselbe Luecke (Befund S6).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

_REPO_ROOT = Path(__file__).resolve().parents[3]
_OPERATORS_ENV = "WHO2BE_BILLING_OVERRIDE_OPERATORS"

# Beide Cloud-Overlays: Hetzner-Prod-Split-Stack und lokale Cloud-Paritaet.
_CLOUD_OVERLAYS = (
    _REPO_ROOT / "deploy" / "hetzner" / "who2be" / "docker-compose.cloud.yml",
    _REPO_ROOT / "docker-compose.cloud.yml",
)


def _api_environment(path: Path) -> dict[str, Any]:
    """Liest `services.api.environment` als Mapping aus einer Compose-Datei."""
    content: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8"))
    api: dict[str, Any] = content["services"]["api"]
    environment = api.get("environment", {})
    if isinstance(environment, list):
        # Listenform `- KEY=value` — beide Schreibweisen sind gueltiges Compose.
        return dict(item.split("=", 1) for item in environment)
    return dict(environment)


@pytest.mark.parametrize(
    "compose_path", _CLOUD_OVERLAYS, ids=lambda p: str(p.relative_to(_REPO_ROOT))
)
def test_cloud_overlay_passes_override_allowlist_to_api(compose_path: Path) -> None:
    """Die Allowlist steht in der `api`-Umgebung — sonst ist der Override tot."""
    environment = _api_environment(compose_path)
    assert _OPERATORS_ENV in environment, (
        f"{compose_path.relative_to(_REPO_ROOT)}: `api.environment` reicht "
        f"{_OPERATORS_ENV} nicht durch — der Override-Endpoint antwortet dann "
        "fail-closed mit 403, obwohl die Variable in der .env steht."
    )


@pytest.mark.parametrize(
    "compose_path", _CLOUD_OVERLAYS, ids=lambda p: str(p.relative_to(_REPO_ROOT))
)
def test_override_allowlist_defaults_to_empty(compose_path: Path) -> None:
    """Der Wert kommt aus dem Env mit leerem Default — fail-closed bleibt erhalten.

    `${VAR:-}` statt eines hart gesetzten Wertes: ohne Eintrag in der `.env`
    startet der Container mit leerer Allowlist und niemand darf schreiben. Ein
    fest verdrahteter Wert waere hier ein Sicherheitsfehler.
    """
    value = str(_api_environment(compose_path)[_OPERATORS_ENV])
    assert value == f"${{{_OPERATORS_ENV}:-}}", (
        f"{compose_path.relative_to(_REPO_ROOT)}: erwartet "
        f"`${{{_OPERATORS_ENV}:-}}` (Env-Durchreichung mit leerem Default), "
        f"gefunden {value!r}."
    )


def test_hetzner_env_example_documents_the_allowlist() -> None:
    """Die Betreiber-Vorlage nennt die Variable — sonst findet sie niemand.

    Die Compose-Zeile allein reicht nicht: der Operator setzt Werte in
    `deploy/hetzner/.env`, und die Vorlage dafuer ist diese Datei.
    """
    example = (_REPO_ROOT / "deploy" / "hetzner" / ".env.example").read_text(encoding="utf-8")
    assert f"{_OPERATORS_ENV}=" in example, (
        "deploy/hetzner/.env.example nennt die Operator-Allowlist nicht — "
        "der Operator kann den Override-Pfad dann nicht scharf schalten."
    )

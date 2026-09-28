"""Compose haelt, was `deploy/hetzner/.env.example` verspricht.

Die Hetzner-Stacks nutzen **kein** `env_file`, sondern listen jede Variable
einzeln unter `services.api.environment`. Eine nicht gelistete Variable erreicht
den Container nicht — auch dann nicht, wenn sie in `deploy/hetzner/.env` steht
und `deploy/hetzner/.env.example` sie ausdruecklich anbietet. Der Stack startet
fehlerfrei, die Einstellung ist trotzdem wirkungslos: ein Fehler, der sich nur
im Verhalten zeigt, nie am Start.

Genau diese Klasse hat schon einmal zugeschlagen — die Betreiber-Allowlist des
Override-Endpoints (`test_cloud_compose_billing_override.py`). Dort steht der
Einzelfall; hier steht die Regel dahinter, damit die naechste Variable nicht
denselben Weg geht.

Geprueft wird der Schnitt aus zwei Mengen:

1. **versprochen** — in `deploy/hetzner/.env.example` unkommentiert als
   `NAME=` deklariert. Ein auskommentierter Eintrag ist eine Erklaerung, keine
   Zusage, und bleibt draussen.
2. **gelesen** — von `who2be_api.core.config.Settings` als ENV-Name
   ausgewertet. Massgeblich ist `validation_alias`, nicht der Feldname: das
   Feld `docs_public` hoert auf `WHO2BE_DOCS_PUBLIC`.

Was beides ist, muss in der `api`-Umgebung des Hetzner-Stacks stehen (Basis
oder Cloud-Overlay — Compose merged beide). Bewusst DB- und daemonfrei: die
YAML-Ebene traegt die Aussage vollstaendig, `docker compose config` braeuchte
einen Daemon und liefe in CI nicht.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

_REPO_ROOT = Path(__file__).resolve().parents[3]
_ENV_EXAMPLE = _REPO_ROOT / "deploy" / "hetzner" / ".env.example"
_CONFIG_PY = _REPO_ROOT / "apps" / "api" / "src" / "who2be_api" / "core" / "config.py"
_STACK = (
    _REPO_ROOT / "deploy" / "hetzner" / "who2be" / "docker-compose.yml",
    _REPO_ROOT / "deploy" / "hetzner" / "who2be" / "docker-compose.cloud.yml",
)

# Variablen, die der API-Code liest und die `.env.example` anbietet, die aber
# bewusst NICHT an den Container gehen. Jeder Eintrag braucht einen Grund —
# eine leere Ausnahmeliste ist der Normalfall.
_INTENTIONALLY_NOT_PASSED: dict[str, str] = {}


class _ComposeLoader(yaml.SafeLoader):
    """Compose-Dateien tragen Merge-Tags (`!override`), die SafeLoader ablehnt."""


def _untagged(loader: yaml.Loader, suffix: str, node: yaml.Node) -> Any:
    if isinstance(node, yaml.SequenceNode):
        return loader.construct_sequence(node, deep=True)
    if isinstance(node, yaml.MappingNode):
        return loader.construct_mapping(node, deep=True)
    assert isinstance(node, yaml.ScalarNode)
    return loader.construct_scalar(node)


_ComposeLoader.add_multi_constructor("!", _untagged)


def _promised_by_env_example() -> set[str]:
    """Unkommentierte `NAME=`-Zeilen — die Zusagen an den Betreiber."""
    text = _ENV_EXAMPLE.read_text(encoding="utf-8")
    return set(re.findall(r"^([A-Z][A-Z0-9_]*)=", text, flags=re.MULTILINE))


def _env_names_read_by_settings() -> set[str]:
    """ENV-Namen, die `Settings` auswertet — Alias schlaegt Feldnamen.

    Gelesen wird der Quelltext, nicht das importierte Modell: pydantic legt die
    aufgeloesten Alias-Namen nicht in einer Form ab, die sich ohne Kenntnis der
    internen Struktur zuverlaessig auslesen laesst, und ein Textabgleich bleibt
    auch dann richtig, wenn pydantic seine Interna aendert.
    """
    text = _CONFIG_PY.read_text(encoding="utf-8")
    body = text.split("(BaseSettings):", 1)[1].split("\n@", 1)[0]
    names: set[str] = set()
    # Ein Feld reicht bis zum naechsten Feld, `@property` oder `def` — nur so
    # landet ein mehrzeiliges `AliasChoices(...)` im selben Block.
    for block in re.split(r"\n(?=    (?:[a-z][a-z0-9_]*\s*:|@property|def ))", body):
        field = re.match(r"\s*([a-z][a-z0-9_]*)\s*:", block)
        if not field:
            continue
        aliases = re.findall(r"[\"']([A-Z][A-Z0-9_]+)[\"']", block)
        names.update(aliases or [field.group(1).upper()])
    return names


def _api_environment() -> set[str]:
    """Die Variablennamen, die der Hetzner-Stack an `api` weitergibt."""
    names: set[str] = set()
    for path in _STACK:
        data: dict[str, Any] = yaml.load(path.read_text(encoding="utf-8"), Loader=_ComposeLoader)
        environment = ((data.get("services") or {}).get("api") or {}).get("environment") or {}
        if isinstance(environment, list):
            names.update(item.split("=", 1)[0] for item in environment)
        else:
            names.update(environment)
    return names


def test_settings_parsing_finds_the_known_aliases() -> None:
    """Selbsttest des Parsers — sonst prueft ein leerer Namensraum nichts.

    Ohne diese Zusicherung wuerde eine Umstellung in `config.py`, die das
    Muster bricht, den Guard still zu einem Test ueber die leere Menge machen:
    gruen, und trotzdem blind.
    """
    names = _env_names_read_by_settings()
    assert len(names) > 20, f"Nur {len(names)} ENV-Namen aus config.py gelesen — Parser defekt?"
    # Feldname ohne Alias, Feldname mit gleichnamigem Alias, Alias mit
    # abweichendem Praefix (`docs_public` ⇒ `WHO2BE_DOCS_PUBLIC`).
    for expected in ("JWT_SECRET", "WHO2BE_EDITION", "WHO2BE_DOCS_PUBLIC"):
        assert expected in names, f"{expected} nicht erkannt — Alias-Parsing defekt."


def test_hetzner_stack_passes_every_promised_setting_to_api() -> None:
    """Was `.env.example` anbietet und die API liest, muss im Container ankommen."""
    promised_and_read = _promised_by_env_example() & _env_names_read_by_settings()
    missing = sorted(promised_and_read - _api_environment() - set(_INTENTIONALLY_NOT_PASSED))
    assert not missing, (
        "deploy/hetzner/.env.example bietet diese Variablen an und die API liest "
        "sie, aber der Hetzner-Stack reicht sie nicht an `api` weiter — der "
        "Betreiber setzt sie und nichts passiert: "
        + ", ".join(missing)
        + ". Entweder unter `services.api.environment` aufnehmen (Regelfall) "
        "oder mit Begruendung in `_INTENTIONALLY_NOT_PASSED` eintragen."
    )

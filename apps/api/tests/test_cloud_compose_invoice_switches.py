"""Compose-Verdrahtung der Rechnungs-Schalter (ADR-0061 §5, Rechnung R2d).

`WHO2BE_INVOICE_TAX_MODE` und `WHO2BE_INVOICE_PRICE_BASIS` werden an zwei
Stellen gelesen: im `api` (Checkout-Betrag, ohne Steuermodus antwortet der
Checkout 503) und im `worker` (Routine `invoice-retry`, stellt die Rechnung bei
Mollie aus). Der `worker` braucht dafuer zusaetzlich `MOLLIE_API_KEY`; ohne ihn
bricht die Routine ab
(`packages/billing/src/who2be_billing/invoice.py#run_invoice_retry`).

Fehlt eine dieser Zeilen, startet der Stack fehlerfrei. Der Fehler zeigt sich
erst daran, dass keine Rechnung entsteht oder der Checkout nie durchgeht. Deshalb
steht die Verdrahtung in einem Test, analog zur Betreiber-Allowlist
(`test_cloud_compose_billing_override.py`).

Drei Eigenschaften werden gehalten:

- **Kein Default am Steuermodus.** `${WHO2BE_INVOICE_TAX_MODE:-}`: ohne Eintrag
  bleibt er leer und die Rechnungsstellung fail closed. Ein Default waere eine
  Steuerentscheidung im Repo, die nur der Betreiber treffen darf.
- **Preisbasis defaultet auf `net`**, wie `Settings` selbst.
- **`api` und `worker` sehen denselben Wert.** Sonst rechnet der Checkout mit
  einer anderen Basis, als die Rechnung ausweist.

Bewusst DB- und daemonfrei: geprueft wird die geparste Compose-Datei.
`docker compose config` braeuchte einen Daemon und liefe in CI nicht.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
import yaml

from who2be_api.core.config import Settings, get_settings

_REPO_ROOT = Path(__file__).resolve().parents[3]

_TAX_MODE = "WHO2BE_INVOICE_TAX_MODE"
_PRICE_BASIS = "WHO2BE_INVOICE_PRICE_BASIS"
_MOLLIE_KEY = "MOLLIE_API_KEY"

# Erwartete Compose-Ausdruecke je Schalter. Der Steuermodus hat einen LEEREN
# Default — das ist die Aussage, nicht eine Luecke.
_EXPECTED: dict[str, str] = {
    _TAX_MODE: f"${{{_TAX_MODE}:-}}",
    _PRICE_BASIS: f"${{{_PRICE_BASIS}:-net}}",
}

# Dieselben drei Overlays wie in `test_cloud_compose_billing_override.py`:
# jedes, das `WHO2BE_EDITION: cloud` setzt.
_CLOUD_OVERLAYS = (
    _REPO_ROOT / "deploy" / "hetzner" / "who2be" / "docker-compose.cloud.yml",
    _REPO_ROOT / "docker-compose.cloud.yml",
    _REPO_ROOT / "deploy" / "dokploy" / "docker-compose.cloud.yml",
)
_SERVICES = ("api", "worker")

_ENV_EXAMPLE = _REPO_ROOT / "deploy" / "hetzner" / ".env.example"

# `${NAME:-default}` bzw. `${NAME}` — mehr Interpolation nutzen die Overlays
# fuer diese Schalter nicht.
_INTERPOLATION = re.compile(r"^\$\{(?P<name>[A-Z0-9_]+)(?::-(?P<default>[^}]*))?\}$")


def _ids(path: Path) -> str:
    return str(path.relative_to(_REPO_ROOT))


def _environment(path: Path, service: str) -> dict[str, Any]:
    """Liest `services.<service>.environment` als Mapping aus einer Compose-Datei."""
    content: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8"))
    environment = content["services"][service].get("environment", {})
    if isinstance(environment, list):
        return dict(item.split("=", 1) for item in environment)
    return dict(environment)


def _resolve(expression: str, env: dict[str, str]) -> str:
    """Loest einen Compose-Ausdruck so auf, wie Compose es fuer `:-` tut.

    `${VAR:-x}` ergibt `x`, wenn VAR fehlt ODER leer ist.
    """
    match = _INTERPOLATION.match(expression)
    assert match, f"unerwarteter Compose-Ausdruck {expression!r}"
    value = env.get(match["name"], "")
    return value if value else (match["default"] or "")


@pytest.mark.parametrize("service", _SERVICES)
@pytest.mark.parametrize("compose_path", _CLOUD_OVERLAYS, ids=_ids)
@pytest.mark.parametrize("name", list(_EXPECTED))
# effect-exempt: Konfig-Drift-Guard auf Compose-Ebene; das Verhalten prueft der Settings-Test unten
def test_invoice_switch_is_passed_with_expected_default(
    name: str, compose_path: Path, service: str
) -> None:
    """Jeder Schalter steht in `api` und `worker`, mit dem festgelegten Default."""
    environment = _environment(compose_path, service)
    assert name in environment, (
        f"{_ids(compose_path)}: `{service}.environment` reicht {name} nicht durch — "
        "der Wert aus der .env kommt im Container nicht an."
    )
    assert str(environment[name]) == _EXPECTED[name], (
        f"{_ids(compose_path)}: `{service}.{name}` erwartet {_EXPECTED[name]!r}, "
        f"gefunden {environment[name]!r}."
    )


@pytest.mark.parametrize("compose_path", _CLOUD_OVERLAYS, ids=_ids)
# effect-exempt: Konfig-Drift-Guard auf Compose-Ebene; Gleichheit der Ausdruecke ist die Aussage
def test_api_and_worker_see_identical_invoice_switches(compose_path: Path) -> None:
    """Checkout (`api`) und Rechnung (`worker`) rechnen mit denselben Schaltern."""
    api = _environment(compose_path, "api")
    worker = _environment(compose_path, "worker")
    for name in _EXPECTED:
        assert api.get(name) == worker.get(name), (
            f"{_ids(compose_path)}: {name} weicht ab — api {api.get(name)!r}, "
            f"worker {worker.get(name)!r}."
        )


@pytest.mark.parametrize("compose_path", _CLOUD_OVERLAYS, ids=_ids)
# effect-exempt: Konfig-Drift-Guard auf Compose-Ebene; Folge ohne Key steht im Moduldocstring
def test_worker_receives_mollie_api_key(compose_path: Path) -> None:
    """Ohne `MOLLIE_API_KEY` im `worker` entsteht nie eine Rechnung."""
    environment = _environment(compose_path, "worker")
    assert environment.get(_MOLLIE_KEY) == f"${{{_MOLLIE_KEY}:-}}", (
        f"{_ids(compose_path)}: `worker.environment` reicht {_MOLLIE_KEY} nicht "
        f"(als `${{{_MOLLIE_KEY}:-}}`) durch, gefunden {environment.get(_MOLLIE_KEY)!r}."
    )


@pytest.mark.parametrize("service", _SERVICES)
@pytest.mark.parametrize("compose_path", _CLOUD_OVERLAYS, ids=_ids)
def test_compose_default_keeps_settings_fail_closed(
    compose_path: Path, service: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ohne `.env`-Eintrag landet der Container im fail-closed-Zustand.

    Der Compose-Default wird aufgeloest, wie Compose es ohne Eintrag in der
    `.env` tut, und an `Settings` gegeben: Steuermodus `None` (Checkout 503,
    Rechnung zurueckgehalten), Preisbasis `net`. Ein Default am Steuermodus
    faellt hier auf, weil `Settings` ihn dann als gesetzt liest.
    """
    environment = _environment(compose_path, service)
    for name in _EXPECTED:
        monkeypatch.setenv(name, _resolve(str(environment[name]), env={}))
    get_settings.cache_clear()
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    assert settings.invoice_tax_mode is None
    assert settings.invoice_price_basis == "net"


@pytest.mark.parametrize("service", _SERVICES)
@pytest.mark.parametrize("compose_path", _CLOUD_OVERLAYS, ids=_ids)
def test_env_value_reaches_settings(
    compose_path: Path, service: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ein Wert in der `.env` setzt sich gegen den Compose-Default durch."""
    environment = _environment(compose_path, service)
    dotenv = {_TAX_MODE: "small_business", _PRICE_BASIS: "gross"}
    for name in _EXPECTED:
        monkeypatch.setenv(name, _resolve(str(environment[name]), env=dotenv))
    get_settings.cache_clear()
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    assert settings.invoice_tax_mode == "small_business"
    assert settings.invoice_price_basis == "gross"


# effect-exempt: Doku-Drift-Guard der Betreiber-Vorlage, hat kein Subjekt
def test_hetzner_env_example_documents_invoice_switches() -> None:
    """Die Betreiber-Vorlage nennt beide Schalter, den Steuermodus ohne Wert.

    Auskommentiert, weil `test_compose_env_promises.py` unkommentierte Eintraege
    als Zusage an die `api` liest — hier ist es eine Erklaerung. Der Steuermodus
    steht ohne Wert: die Vorlage empfiehlt keine Steuerentscheidung.
    """
    lines = _ENV_EXAMPLE.read_text(encoding="utf-8").splitlines()
    assert f"# {_TAX_MODE}=" in lines, (
        f"deploy/hetzner/.env.example: erwartet die Zeile `# {_TAX_MODE}=` "
        "(auskommentiert, ohne Wert)."
    )
    assert f"# {_PRICE_BASIS}=net" in lines, (
        f"deploy/hetzner/.env.example: erwartet die Zeile `# {_PRICE_BASIS}=net`."
    )
    assigned = [line for line in lines if re.match(rf"^\s*#?\s*{_TAX_MODE}=\S", line)]
    assert not assigned, f"deploy/hetzner/.env.example gibt dem Steuermodus einen Wert: {assigned}"

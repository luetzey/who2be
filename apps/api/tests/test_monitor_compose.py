"""Haertung des Waechter-Stacks (``deploy/monitor/``, ADR-0062 Paket A1).

Der Waechter laeuft auf einem eigenen Server und wird selten angefasst. Genau
deshalb rutscht dort eine fehlende Zeile am leichtesten durch: ein neuer Dienst
startet auch ohne Speicherdeckel, und eine DB mit ``ports:`` faellt niemandem
auf, bis jemand von aussen anklopft. Der Test haelt die Akzeptanzkriterien von
A1 fest, damit sie nicht nur im Review gelten:

1. Jeder Dienst traegt dieselben drei Haertungs-Bloecke wie Prod (``logging``,
   ``no-new-privileges``, ``mem_limit``) — vgl. ``test_compose_hardening.py``.
2. Nur ``caddy`` veroeffentlicht Host-Ports; die GlitchTip-Datenbank haengt
   ausschliesslich an einem ``internal``-Netz.
3. Secrets kommen nur per Env und mit ``:?``-Guard (kein Default, kein Literal).
4. Jedes Image ist per Digest gepinnt.
5. Die Frist fuer Fehler-Events steht im Compose so, wie das VVT sie zusagt.
6. Die Einrichtung im RUNBOOK legt alle Admin-Konten an, bevor Caddy die
   Oberflaechen veroeffentlicht.

Reiner Datei-Test, ohne Docker. ``docker compose config`` laeuft zusaetzlich
von Hand (README des Stacks), weil CI fuer diesen Stack keinen Daemon braucht.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
import yaml

_REPO_ROOT = Path(__file__).resolve().parents[3]
_MONITOR = _REPO_ROOT / "deploy" / "monitor"
_COMPOSE = _MONITOR / "compose.yml"
_ENV_EXAMPLE = _MONITOR / ".env.example"
_VVT = _REPO_ROOT / "docs" / "compliance" / "vvt.md"
_RUNBOOK = _REPO_ROOT / "deploy" / "hetzner" / "RUNBOOK.md"

#: Variablen, die Geheimnisse tragen. Jede muss im Compose als ``${VAR:?…}``
#: stehen und darf in ``.env.example`` nur einen Platzhalter haben.
_SECRET_VARS = ("GLITCHTIP_SECRET_KEY", "GLITCHTIP_DB_PASSWORD", "GLITCHTIP_EMAIL_URL")

#: Obergrenze fuer die Summe der Speicherdeckel. Stufe A soll auf dem
#: kleinsten sinnvollen Typ (2 GB) laufen; 1,5 GB lassen Kernel und
#: Page-Cache Luft (ADR-0062 §5.1, Bericht §3.4).
_MEMORY_BUDGET_BYTES = 1536 * 1024 * 1024


def _compose() -> dict[str, Any]:
    data = yaml.safe_load(_COMPOSE.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def _services() -> dict[str, dict[str, Any]]:
    services = _compose()["services"]
    assert isinstance(services, dict) and services
    return services


_SERVICE_NAMES = sorted(_services())


def _mem_bytes(value: str) -> int:
    match = re.fullmatch(r"(\d+)([kmg])", str(value).lower())
    assert match, f"mem_limit {value!r} nicht im Format <zahl>[k|m|g]"
    factor = {"k": 1024, "m": 1024**2, "g": 1024**3}[match.group(2)]
    return int(match.group(1)) * factor


@pytest.mark.parametrize("name", _SERVICE_NAMES)
def test_service_drops_new_privileges(name: str) -> None:
    spec = _services()[name]
    assert "no-new-privileges:true" in spec.get("security_opt", []), name


@pytest.mark.parametrize("name", _SERVICE_NAMES)
def test_service_caps_container_log(name: str) -> None:
    logging = _services()[name].get("logging") or {}
    options = logging.get("options") or {}
    assert logging.get("driver") == "json-file", name
    assert options.get("max-size") and options.get("max-file"), name


@pytest.mark.parametrize("name", _SERVICE_NAMES)
def test_service_has_memory_ceiling(name: str) -> None:
    assert _mem_bytes(_services()[name]["mem_limit"]) > 0


def test_memory_ceilings_fit_the_small_watchdog_host() -> None:
    total = sum(_mem_bytes(spec["mem_limit"]) for spec in _services().values())
    assert total <= _MEMORY_BUDGET_BYTES, f"Summe der mem_limit {total} B > Budget"


@pytest.mark.parametrize("name", _SERVICE_NAMES)
def test_image_is_pinned_by_digest(name: str) -> None:
    image = _services()[name]["image"]
    assert re.search(r":[\w.-]+@sha256:[0-9a-f]{64}$", image), (
        f"{name}: Image {image!r} nicht per Tag@Digest gepinnt"
    )


def test_only_the_reverse_proxy_publishes_host_ports() -> None:
    published = sorted(name for name, spec in _services().items() if spec.get("ports"))
    assert published == ["caddy"]


def test_database_sits_only_on_an_internal_network() -> None:
    compose = _compose()
    db = compose["services"]["glitchtip-db"]
    assert "ports" not in db and "expose" not in db
    networks = db["networks"]
    assert isinstance(networks, list) and networks
    for net in networks:
        assert compose["networks"][net].get("internal") is True, (
            f"glitchtip-db haengt an {net!r}, das nicht internal ist"
        )


@pytest.mark.parametrize("var", _SECRET_VARS)
def test_secrets_come_only_from_env_with_a_guard(var: str) -> None:
    text = _COMPOSE.read_text(encoding="utf-8")
    uses = re.findall(r"\$\{" + var + r"([^}]*)\}", text)
    assert uses, f"{var} wird im Compose nicht verwendet"
    for suffix in uses:
        assert suffix.startswith(":?"), f"{var} ohne :?-Guard (Default {suffix!r})"


@pytest.mark.parametrize("var", _SECRET_VARS)
def test_env_example_carries_no_real_secret(var: str) -> None:
    lines = _ENV_EXAMPLE.read_text(encoding="utf-8").splitlines()
    values = [line.split("=", 1)[1] for line in lines if line.startswith(f"{var}=")]
    assert len(values) == 1, f"{var} fehlt oder steht doppelt in .env.example"
    assert values[0] in {"CHANGE_ME", "consolemail://"}, f"{var}: Beispielwert {values[0]!r}"


def test_event_retention_matches_the_promise_in_the_vvt() -> None:
    env = _services()["glitchtip"]["environment"]
    days = env["GLITCHTIP_EVENT_RETENTION_DAYS"]
    assert days == env["GLITCHTIP_RETENTION_DAYS"]
    vvt = _VVT.read_text(encoding="utf-8")
    assert re.search(
        rf"Fehler-Events \(GlitchTip[^|]*\|\s*\*\*{days} Tage\*\*",
        vvt,
    ), f"VVT §7 nennt fuer Fehler-Events nicht {days} Tage"


def test_self_signup_is_closed_after_the_first_account() -> None:
    env = _services()["glitchtip"]["environment"]
    assert env["ENABLE_USER_REGISTRATION"] == "false"
    assert env["ENABLE_ORGANIZATION_CREATION"] == "false"


def test_beszel_hub_never_dials_into_prod() -> None:
    assert _services()["beszel"]["environment"]["DISABLE_SSH"] == "true"


def test_beszel_hub_cannot_pull_prod_container_logs() -> None:
    assert _services()["beszel"]["environment"]["CONTAINER_DETAILS"] == "false"


# effect-exempt: Konfig-Drift-Guard; Rolle des Env-Kontos gegen Beszel v0.21.0 von Hand geprobt
def test_beszel_first_account_is_not_created_from_env() -> None:
    # In v0.21.0 wird ein Konto aus USER_EMAIL/USER_PASSWORD nur `user`, nicht
    # `admin`; das Admin-Konto entsteht im RUNBOOK per create-user im Tunnel.
    env = _services()["beszel"]["environment"]
    for key in ("USER_EMAIL", "USER_PASSWORD", "BESZEL_HUB_USER_EMAIL", "BESZEL_HUB_USER_PASSWORD"):
        assert key not in env, key


def _runbook_setup() -> str:
    text = _RUNBOOK.read_text(encoding="utf-8")
    start = text.index("## Waechter-Server (Monitoring, ADR-0062)")
    return text[start : text.index("### Betrieb", start)]


def _step(setup: str, number: int) -> str:
    match = re.search(rf"^{number}\. \*\*.*?(?=^\d+\. \*\*|\Z)", setup, re.M | re.S)
    assert match, f"RUNBOOK §Waechter-Server: Schritt {number} fehlt"
    return match.group(0)


# effect-exempt: Doku-Konformitaet der Owner-Schrittliste; Befehle gegen die Images geprobt
def test_runbook_creates_all_admin_accounts_before_caddy_publishes() -> None:
    # Alle drei Oberflaechen geben das erste Konto an den, der zuerst kommt.
    # Deshalb startet der erste `up` ohne caddy, die Konten entstehen ueber
    # den Tunnel, und erst danach wird veroeffentlicht.
    setup = _runbook_setup()
    first_up, accounts, publish = _step(setup, 4), _step(setup, 5), _step(setup, 6)
    up_lines = re.findall(r"^\s*\$MON up -d.*$", first_up, re.M)
    assert up_lines and all("caddy" not in line for line in up_lines)
    assert all(name in up_lines[0] for name in sorted(set(_SERVICE_NAMES) - {"caddy"}))
    assert "! grep -q CHANGE_ME deploy/monitor/.env" in first_up
    assert "createsuperuser" in accounts
    assert "/api/beszel/create-user" in accounts
    assert "ssh -N -L" in accounts
    assert re.search(r"^\s*\$MON up -d\s*$", publish, re.M)
    probes = (
        '/api/settings/ | grep -o \'"enableUserRegistration"',
        "curl -s https://hosts.$D/api/beszel/first-run",
        "--data '420[\"needSetup\"]'",
    )
    for probe in probes:
        assert probe in publish, f"Aussen-Pruefung ohne {probe!r}"
    # Kein spaeterer Schritt legt noch ein Konto ueber die oeffentliche UI an.
    later = setup[setup.index(publish) + len(publish) :]
    assert "Admin-Konto anlegen" not in later and "Owner-Konto anlegen" not in later

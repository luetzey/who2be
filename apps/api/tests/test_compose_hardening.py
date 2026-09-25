"""Container-Haertung der Hetzner-Prod-Stacks (W8/S1-S3).

Drei Compose-Bloecke sollen an **jedem** Dienst beider Hetzner-Stacks stehen,
und genau diese Vollstaendigkeit ist das, was ein Mensch beim Review zuverlaessig
uebersieht — ein neuer Dienst wird angelegt, die drei Zeilen fehlen, und nichts
faellt auf, weil der Stack ja startet. Was dabei verloren geht:

1. ``logging:`` fehlt an einem Dienst → dessen Container-Log waechst unbegrenzt
   und fuellt irgendwann die Platte. Der Ausfall kommt Monate spaeter und sieht
   nicht nach einer Compose-Zeile aus.
2. ``security_opt: ["no-new-privileges:true"]`` fehlt → in genau diesem
   Container bleibt Privilege-Escalation ueber setuid-Binaries moeglich. Eine
   Luecke, die niemandem auffaellt, weil sie nichts kaputt macht.
3. ``mem_limit`` fehlt → dieser Container ist der einzige ohne Deckel und damit
   der wahrscheinlichste Ausloeser eines Host-OOM, dessen Opfer sich der Kernel
   selbst sucht (BSI SYS.1.6.A15).

Deshalb prueft dieser Test nicht Stichproben, sondern zaehlt ab: jeder Dienst,
den die beiden Dateien definieren — inklusive One-Shots und Profil-Diensten.
Reiner Datei-Test, ohne DB und ohne Docker.

Bewusst NICHT geprueft werden ``docker-compose.yml`` (Repo-Root, lokale
Entwicklung), ``deploy/dokploy/*`` (Staging mit eigener Ressourcenverwaltung)
und die Cloud-Overlays: die ``mem_limit``-Werte sind auf die konkrete
Zielmaschine geeicht (CX32, 8 GB) und waeren anderswo eine willkuerliche
Fremdvorgabe.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
import yaml

_REPO_ROOT = Path(__file__).resolve().parents[3]
_HETZNER = _REPO_ROOT / "deploy" / "hetzner"
_APP_COMPOSE = _HETZNER / "who2be" / "docker-compose.yml"
_SUPABASE_COMPOSE = _HETZNER / "supabase" / "docker-compose.yml"
_CADDYFILE = _HETZNER / "Caddyfile"

_COMPOSE_FILES = (_APP_COMPOSE, _SUPABASE_COMPOSE)


def _services(path: Path) -> dict[str, dict[str, Any]]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    services = data["services"]
    assert isinstance(services, dict) and services
    return services


def _all_services() -> list[tuple[str, str, dict[str, Any]]]:
    out: list[tuple[str, str, dict[str, Any]]] = []
    for path in _COMPOSE_FILES:
        for name, spec in _services(path).items():
            out.append((path.parent.name, name, spec))
    return out


_ALL = _all_services()
_IDS = [f"{stack}/{name}" for stack, name, _ in _ALL]


@pytest.mark.parametrize(("stack", "name", "spec"), _ALL, ids=_IDS)
def test_service_drops_new_privileges(stack: str, name: str, spec: dict[str, Any]) -> None:
    """Jeder Dienst setzt ``no-new-privileges`` — ohne Ausnahme."""
    assert spec.get("security_opt") == ["no-new-privileges:true"], (
        f"{stack}/{name} ohne no-new-privileges — Privilege-Escalation ueber "
        "setuid-Binaries bliebe in genau diesem Container offen."
    )


@pytest.mark.parametrize(("stack", "name", "spec"), _ALL, ids=_IDS)
def test_service_caps_container_log(stack: str, name: str, spec: dict[str, Any]) -> None:
    """Jeder Dienst deckelt sein Container-Log (Docker-eigene Rotation)."""
    logging = spec.get("logging")
    assert isinstance(logging, dict), f"{stack}/{name} ohne logging: — Log waechst unbegrenzt."
    assert logging.get("driver") == "json-file"
    options = logging.get("options") or {}
    assert options.get("max-size"), f"{stack}/{name}: logging ohne max-size ist kein Deckel."
    assert options.get("max-file"), f"{stack}/{name}: logging ohne max-file ist kein Deckel."


@pytest.mark.parametrize(("stack", "name", "spec"), _ALL, ids=_IDS)
def test_service_has_memory_ceiling(stack: str, name: str, spec: dict[str, Any]) -> None:
    """Jeder Dienst hat eine Speicher-Obergrenze (BSI SYS.1.6.A15)."""
    limit = spec.get("mem_limit")
    assert isinstance(limit, str) and limit.endswith(("m", "g")), (
        f"{stack}/{name} ohne mem_limit — dieser Container waere der einzige "
        "ohne Deckel und damit der wahrscheinlichste Ausloeser eines Host-OOM."
    )


def test_memory_budget_of_always_on_services_fits_the_host() -> None:
    """Die Deckel der DAUERHAFT laufenden Dienste passen auf die Zielmaschine.

    Owner-Entscheidung 2026-09-25: Hetzner CX32 mit 8 GB, beide Stacks auf
    derselben Maschine. One-Shots (``restart: "no"``) und Profil-Dienste sind
    ausgenommen — die laufen nicht im Dauerbetrieb.

    Der Test haelt nach oben Abstand (<= 7 GiB, damit Host, Kernel-Page-Cache
    und Docker selbst Luft behalten) und nach unten (>= 4 GiB): ein zu kleines
    Budget hiesse, dass die Deckel im Normalbetrieb greifen, und ein OOM im
    Normalbetrieb waere schlechter als gar kein Deckel.
    """
    total_mib = 0
    counted: list[str] = []
    for stack, name, spec in _ALL:
        if spec.get("restart") == "no" or spec.get("profiles"):
            continue
        limit = str(spec["mem_limit"])
        value, unit = int(limit[:-1]), limit[-1]
        total_mib += value * (1024 if unit == "g" else 1)
        counted.append(f"{stack}/{name}={limit}")

    assert counted, "kein Dauerdienst gefunden — der Filter ist kaputt"
    assert 4096 <= total_mib <= 7168, (
        f"Dauerdienst-Budget {total_mib} MiB passt nicht zu 8 GB RAM: {sorted(counted)}"
    )


def _caddyfile_text() -> str:
    return _CADDYFILE.read_text(encoding="utf-8")


def _caddyfile_directives() -> str:
    """Caddyfile ohne Kommentarzeilen.

    Die Datei ist stark kommentiert, und die Kommentare zitieren Direktiven im
    Klartext. Ein naiver Substring-Test wuerde also den *Kommentar* ueber eine
    Einstellung fuer die Einstellung selbst halten — und bliebe gruen, wenn die
    Direktive geloescht und nur die Begruendung stehen gelassen wird.
    """
    return "\n".join(
        line for line in _caddyfile_text().splitlines() if not line.lstrip().startswith("#")
    )


def _site_blocks() -> list[str]:
    """Namen der Site-Bloecke (Zeilen der Form ``<sub>.{$DOMAIN} {``).

    Bewusst am Zeilenanfang verankert: ``{$DOMAIN} {`` steht auch mitten in der
    CSP-Zeile von ``app.{$DOMAIN}`` (``connect-src … https://api.{$DOMAIN}
    {$VITE_SUPABASE_URL}``). Ein blosses ``count()`` zaehlt die mit und
    verlangt dann einen Import zu viel.
    """
    return re.findall(r"(?m)^([a-z0-9-]+\.\{\$DOMAIN\}) \{$", _caddyfile_directives())


def test_caddy_access_log_is_enabled_for_every_site() -> None:
    """Jeder Site-Block importiert das Access-Log-Snippet.

    Ein Site-Block ohne ``import access_log`` protokolliert schweigend nichts —
    die Subdomain faellt aus der Nachvollziehbarkeit heraus, ohne dass
    irgendetwas kaputtgeht.
    """
    directives = _caddyfile_directives()
    sites = _site_blocks()
    assert len(sites) >= 4, f"Site-Bloecke nicht gefunden ({sites}) — Struktur geaendert?"
    assert directives.count("import access_log") == len(sites)
    assert directives.count("import security_headers") == len(sites)


def test_caddy_access_log_rotates_and_expires() -> None:
    """Rotation UND Aufbewahrungsfrist sind gesetzt, nicht nur eines davon.

    Ohne ``roll_size``/``roll_keep`` fuellt das Log die Platte (selbstgebauter
    Ausfall); ohne ``roll_keep_for`` blieben IP-Adressen unbegrenzt liegen
    (V12 im VVT). Die Frist ist zugleich das Loeschverfahren — es gibt keinen
    zweiten Mechanismus, der sie durchsetzt.
    """
    directives = _caddyfile_directives()
    assert "output file /var/log/caddy/access.log" in directives
    assert "roll_size" in directives
    assert "roll_keep " in directives
    # 336h = 14 Tage. Muss zu docs/compliance/vvt.md §7 und
    # data-retention-and-erasure.md §5 passen — die drei Stellen sind eine
    # Aussage, nicht drei.
    assert "roll_keep_for 336h" in directives


def test_caddy_access_log_redacts_oauth_query_values() -> None:
    """OAuth-Werte aus der URL landen nicht im Klartext auf Platte.

    ``api.<DOMAIN>`` traegt den OAuth-Authorization-Endpunkt (ADR-0036).
    Header-Credentials redigiert Caddy per Default, Query-Werte NICHT.
    """
    directives = _caddyfile_directives()
    assert "request>uri query" in directives
    for parameter in ("code", "token", "access_token", "refresh_token"):
        assert f"replace {parameter} REDACTED" in directives
    # log_credentials wuerde die Default-Redaktion von Cookie/Authorization
    # abschalten — darf als DIREKTIVE nirgends auftauchen (im Kommentar wird
    # sie bewusst erwaehnt und genau deshalb hier gegen die Direktiven geprueft).
    assert "log_credentials" not in directives


def test_caddy_access_log_lives_on_a_volume() -> None:
    """Das Log-Verzeichnis ist gemountet (BSI SYS.1.6.A7).

    Die Basis-Anforderung verlangt woertlich, dass die Speicherung der
    Protokollierungsdaten der Container „ausserhalb des Containers, mindestens
    auf dem Container-Host, erfolgen" MUSS. Ohne den Mount waere das Log nach
    jedem Redeploy weg — also genau dann, wenn man es braucht.
    """
    data = yaml.safe_load(_APP_COMPOSE.read_text(encoding="utf-8"))
    caddy = data["services"]["caddy"]
    mounts = [str(v) for v in caddy["volumes"]]
    assert any(m.startswith("caddy-logs:/var/log/caddy") for m in mounts), mounts
    assert "caddy-logs" in data["volumes"]

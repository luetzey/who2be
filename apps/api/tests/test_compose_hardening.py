"""Container-Haertung der Hetzner-Prod-Stacks (W8/S1-S3).

Drei Compose-Bloecke sollen an **jedem** Dienst beider Hetzner-Stacks stehen,
und genau diese Vollstaendigkeit ist das, was ein Mensch beim Review zuverlaessig
uebersieht — ein neuer Dienst wird angelegt, die drei Zeilen fehlen, und nichts
faellt auf, weil der Stack ja startet:

1. ``logging:`` deckelt das Container-Log; ohne den Deckel waechst es
   unbegrenzt, und der daraus folgende Ausfall kommt Monate spaeter und sieht
   nicht nach einer Compose-Zeile aus.
2. ``security_opt: ["no-new-privileges:true"]`` sperrt den Rechtezuwachs im
   Container (BSI SYS.1.6.A17). Ein Dienst ohne die Zeile faellt niemandem
   auf, weil die fehlende Einstellung nichts kaputt macht.
3. ``mem_limit`` begrenzt den Speicher je Container (BSI SYS.1.6.A15). Ein
   Dienst ohne Deckel bestimmt im Zweifel, welchen Prozess der Kernel
   beendet — und das soll nicht dem Zufall ueberlassen bleiben.

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
        f"{stack}/{name} ohne no-new-privileges — die Haertung muss an jedem "
        "Dienst stehen, nicht an den meisten."
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
        f"{stack}/{name} ohne mem_limit — der Deckel muss an jedem Dienst "
        "stehen, damit die Speicherobergrenzen als Ganzes wirken."
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


def test_caddy_access_log_rotates_by_size() -> None:
    """Groessenbegrenzung ist gesetzt — sonst fuellt das Log die Platte.

    Das ist ausdruecklich NUR die Groessengrenze. Die 14-Tage-Frist haengt
    nicht daran; sie wird vom Host-Cron getragen, den
    ``test_access_log_retention_is_enforced_by_a_documented_cron`` prueft.
    """
    directives = _caddyfile_directives()
    assert "output file /var/log/caddy/access.log" in directives
    assert "roll_size" in directives
    assert "roll_keep " in directives


def test_caddy_access_log_keeps_the_secondary_time_bound() -> None:
    """``roll_keep_for`` bleibt als zweite, unabhaengige Grenze gesetzt.

    Sie traegt die Frist NICHT allein: sie wirkt nur auf bereits rotierte
    Generationen und laeuft erst, wenn eine neue Datei entsteht — die aktive
    ``access.log`` erfasst sie nie. Sie ist der Rueckfall, falls der Cron
    ausfaellt, und muss deshalb zur dokumentierten Frist passen.
    """
    directives = _caddyfile_directives()
    assert "roll_keep_for 336h" in directives


def test_caddy_does_not_use_directives_this_version_ignores() -> None:
    """Keine Zeitrotations-Direktive, die Caddy 2.8 still verwirft.

    ``roll_at``/``roll_interval`` kennt der file-Writer dieser Version nicht
    und laesst sie beim Adaptieren kommentarlos weg — gegen das Binary
    geprueft. Eine solche Zeile saehe nach durchgesetzter Frist aus und waere
    wirkungslos; genau davor schuetzt dieser Test.
    """
    directives = _caddyfile_directives()
    for ignored in ("roll_at", "roll_interval", "mode "):
        assert ignored not in directives, (
            f"{ignored!r} wird von Caddy 2.8 still verworfen — "
            "wirkungsloser Platzhalter statt durchgesetzter Einstellung"
        )


def test_access_log_retention_is_enforced_by_a_documented_cron() -> None:
    """Die 14-Tage-Frist hat einen Mechanismus, nicht nur eine Zusage.

    Die Caddy-Direktiven deckeln die Groesse, nicht die Zeit. Ohne einen
    zeitlichen Ausloeser kann die aktive Logdatei bei geringem Aufkommen
    laenger als die zugesagte Frist bestehen — personenbezogene Daten (IP,
    User-Agent) blieben dann ueber die Frist hinaus liegen, ohne dass etwas
    ausfaellt. Deshalb muss das RUNBOOK ein Verfahren nennen, das die Frist
    tatsaechlich durchsetzt, und die Frist darin muss zur Konfiguration und
    zu den beiden Compliance-Dokumenten passen.
    """
    runbook = (_HETZNER / "RUNBOOK.md").read_text(encoding="utf-8")
    assert "/var/log/caddy/access.log" in runbook

    # Der Mechanismus, der fehlte: eine Zeile, die zeitbasiert LOESCHT. Der
    # Quartals-Check listet dieselbe `-mtime`-Bedingung nur auf, ohne zu
    # loeschen — deshalb muessen beide Teile in EINER Zeile stehen, sonst
    # wuerde der Test von der blossen Pruefanleitung gruen gehalten.
    delete_lines = [
        line for line in runbook.splitlines() if "-mtime +14" in line and "-delete" in line
    ]
    assert delete_lines, (
        "RUNBOOK nennt kein zeitbasiertes Loeschverfahren fuer die Access-Logs "
        "(eine Zeile, die aeltere Generationen tatsaechlich entfernt)"
    )
    # ... und rotiert die aktive Datei, die roll_keep_for nie erfasst.
    assert "mv /var/log/caddy/access.log" in runbook

    # Die Frist ist EINE Aussage an vier Stellen.
    for doc in (
        _REPO_ROOT / "docs" / "compliance" / "vvt.md",
        _REPO_ROOT / "docs" / "compliance" / "data-retention-and-erasure.md",
    ):
        text = doc.read_text(encoding="utf-8")
        assert "14 Tage" in text
        assert "RUNBOOK" in text, f"{doc.name} verweist nicht auf das Verfahren"


def test_retention_docs_do_not_claim_a_failure_proof_mechanism() -> None:
    """Kein Dokument behauptet, die Frist koenne nicht ausfallen.

    Ein Host-Cron kann still ausfallen. Die Dokumente benennen dieses
    Restrisiko; ein Satz, der das Gegenteil verspricht, wuerde einen spaeteren
    Leser eine echte Pruefung ueberspringen lassen.
    """
    for path in (
        _CADDYFILE,
        _HETZNER / "RUNBOOK.md",
        _REPO_ROOT / "docs" / "compliance" / "vvt.md",
        _REPO_ROOT / "docs" / "compliance" / "data-retention-and-erasure.md",
    ):
        text = path.read_text(encoding="utf-8")
        assert "keinen, der ausfallen kann" not in text, (
            f"{path.name}: Zusage der Ausfallsicherheit, die das Verfahren nicht traegt"
        )


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

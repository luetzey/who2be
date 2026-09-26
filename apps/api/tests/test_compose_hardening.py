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


def test_caddy_access_log_keeps_its_own_size_bound() -> None:
    """``roll_keep_for`` bleibt gesetzt — aber nur fuer seine eigene Klasse.

    Es ist **kein** unabhaengiger Rueckfall fuer die Frist: es erfasst
    ausschliesslich die von Caddy selbst erzeugten Generationen
    (``access-<ts>.log.gz``), laeuft nur bei einem Rotationsereignis und
    beruehrt die aktive Datei nie. Die Generationen des Rotations-Skripts
    (``access.log.<ts>.gz``) fallen nicht darunter — die raeumt allein das
    Skript weg. Gesetzt bleibt es, weil es innerhalb seiner Klasse wirkt und
    zur dokumentierten Frist passen muss.
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


def test_access_log_retention_is_enforced_by_a_documented_script() -> None:
    """Die 14-Tage-Frist hat einen Mechanismus, und er ist ausfuehrbar.

    Die Caddy-Direktiven deckeln die Groesse, nicht die Zeit. Den zeitlichen
    Teil traegt ``deploy/hetzner/scripts/rotate-access-log.sh``, per Host-Cron
    taeglich gestartet. Dieser Test haelt nur die Verdrahtung nach — dass
    RUNBOOK und Compliance-Dokumente auf dasselbe Skript zeigen und die Frist
    eine einzige Aussage ist.

    Die **Wirkung** des Skripts prueft
    ``deploy/hetzner/tests/test_access_log_rotation.sh``: es fuehrt die Rotation
    gegen echte Verzeichnisse im echten Caddy-Image aus. Ein Test, der nur
    Zeichenketten in Markdown sucht, ist hier ausdruecklich kein Nachweis — die
    Vorgaenger-Pruefungen dieser Karte waren gruen, waehrend die Frist nicht
    griff.
    """
    script = _HETZNER / "scripts" / "rotate-access-log.sh"
    assert script.is_file(), "Rotations-Skript fehlt — die Frist haette keinen Mechanismus"
    script_text = script.read_text(encoding="utf-8")

    # Die Frist steht im Skript als Default, nicht nur in der Doku.
    assert "ACCESS_LOG_RETENTION_DAYS:-14" in script_text

    runbook = (_HETZNER / "RUNBOOK.md").read_text(encoding="utf-8")
    assert "scripts/rotate-access-log.sh" in runbook, (
        "RUNBOOK nennt das Rotations-Skript nicht — dann richtet es niemand ein"
    )
    # Der Cron-Eintrag ruft das Skript, nicht eine handgeschriebene Kette. Genau
    # diese Kette war der Fehler: der Loeschteil hing am Rotationsteil.
    cron_lines = [
        line
        for line in runbook.splitlines()
        if "rotate-access-log.sh" in line and line.lstrip().startswith(("30 4", "0 4", "15 4"))
    ]
    assert cron_lines, "RUNBOOK enthaelt keine Crontab-Zeile, die das Skript startet"

    # Die Frist ist EINE Aussage an mehreren Stellen.
    for doc in (
        _REPO_ROOT / "docs" / "compliance" / "vvt.md",
        _REPO_ROOT / "docs" / "compliance" / "data-retention-and-erasure.md",
    ):
        text = doc.read_text(encoding="utf-8")
        assert "14 Tage" in text
        assert "RUNBOOK" in text, f"{doc.name} verweist nicht auf das Verfahren"


def test_retention_threshold_stays_below_the_promised_period() -> None:
    """Die Loeschschwelle liegt unter der Frist — sonst ist die Frist ueberschritten.

    Rechnung, die das Skript im Kommentar fuehrt und die hier nachgerechnet
    wird: eine Generation wird bis zu 24 h nach dem letzten Eintrag darin
    erzeugt, und ``find -mtime +N`` greift erst ab einem Alter von mehr als N
    vollen Tagen. Mit der Frist selbst als Schwelle waere der aelteste Eintrag
    beim Loeschen bis zu zwei Tage ueber der Zusage. Deshalb Frist minus 2.
    """
    script_text = (_HETZNER / "scripts" / "rotate-access-log.sh").read_text(encoding="utf-8")
    match = re.search(r"DELETE_THRESHOLD_DAYS=\$\(\(RETENTION_DAYS\s*-\s*(\d+)\)\)", script_text)
    assert match, "Loeschschwelle wird nicht aus der Frist abgeleitet"
    subtracted = int(match.group(1))
    assert subtracted >= 2, (
        f"Schwelle ist nur {subtracted} Tag(e) unter der Frist. Rotationsfenster (bis 24 h) "
        "und die -mtime-Semantik (+N greift ab N+1 Tagen) addieren sich auf zwei Tage — "
        "mit weniger Abstand wird die zugesagte Frist im schlechtesten Fall ueberschritten."
    )


def test_retention_docs_do_not_claim_a_second_independent_limit() -> None:
    """Kein Dokument behauptet einen Rueckfall, den es nicht gibt.

    Zwei Zusagen sind hier verboten, weil beide nachweislich nicht zutrafen:

    1. Die Frist koenne nicht ausfallen. Ein Host-Cron kann still ausfallen;
       die Dokumente benennen dieses Restrisiko.
    2. ``roll_keep_for`` sei eine *zweite, unabhaengige* Grenze fuer die Frist.
       Es erfasst nur Caddys eigene Generationen (``access-<ts>.log.gz``), nicht
       die des Rotations-Skripts (``access.log.<ts>.gz``) — die beiden
       Namensklassen sind disjunkt. Fuer die Generationen des Skripts gibt es
       genau einen Loeschpfad: das Skript selbst.

    Geprueft wird auf die Aussage, nicht auf eine einzelne Formulierung: jede
    Kombination aus „zweite/unabhaengige Grenze" und einer Ausfall-Zusage faellt
    auf. Ein blosses Verbot der wortgleichen Vorgaenger-Zeile liesse denselben
    Satz mit anderen Worten durch — genau das ist in Runde 2 passiert.
    """
    forbidden = (
        "keinen, der ausfallen kann",
        "zweite, unabhaengige Grenze",
        "zweite, unabhängige Grenze",
        "zweiter, unabhaengiger Mechanismus",
        "als zweite Grenze",
    )
    for path in (
        _CADDYFILE,
        _HETZNER / "RUNBOOK.md",
        _REPO_ROOT / "docs" / "compliance" / "vvt.md",
        _REPO_ROOT / "docs" / "compliance" / "data-retention-and-erasure.md",
        *sorted((_REPO_ROOT / "changelog.d").glob("*access-logs*")),
    ):
        text = path.read_text(encoding="utf-8")
        for claim in forbidden:
            assert claim not in text, (
                f"{path.name}: behauptet einen Rueckfall fuer die Frist "
                f"({claim!r}), den das Verfahren nicht traegt"
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


def _site_block_body(site: str) -> str:
    """Rumpf eines Site-Blocks (ohne Kommentare), bis zur schliessenden Klammer.

    Die CSP steht je Site einzeln und unterscheidet sich zwischen ihnen — ein
    Test gegen die ganze Datei koennte den Wert der einen Site fuer den der
    anderen halten.
    """
    directives = _caddyfile_directives().splitlines()
    start = directives.index(f"{site} {{") + 1
    body: list[str] = []
    for line in directives[start:]:
        if line == "}":
            return "\n".join(body)
        body.append(line)
    raise AssertionError(f"Site-Block {site} hat keine schliessende Klammer")


def test_caddy_security_header_values_are_the_promised_ones() -> None:
    """Die Header-WERTE stehen exakt so da, wie sie zugesagt sind.

    ``test_caddy_access_log_is_enabled_for_every_site`` prueft nur, dass jeder
    Site-Block das Snippet importiert — nicht, was darin steht. Eine geaenderte
    Zahl (``max-age``), ein aufgeweichtes ``SAMEORIGIN`` statt ``DENY`` oder ein
    entfernter Eintrag faellt dort nicht auf.

    Der laufende Gegenpart ist ``deploy/hetzner/tests/test_headers_ci.sh``: er
    misst die Antwort auf der Leitung. Dieser Test hier greift auch dann, wenn
    der Container gar nicht erst startet — dann faellt der andere aus, statt zu
    greifen.
    """
    directives = _caddyfile_directives()
    expected = {
        "Strict-Transport-Security": '"max-age=31536000; includeSubDomains"',
        "X-Content-Type-Options": '"nosniff"',
        "X-Frame-Options": '"DENY"',
        "Referrer-Policy": '"no-referrer"',
        "Cross-Origin-Opener-Policy": '"same-origin"',
    }
    for name, value in expected.items():
        assert f"{name} {value}" in directives, (
            f"{name} fehlt oder hat einen anderen Wert als zugesagt ({value})"
        )
    # Permissions-Policy: die vier Sensoren einzeln, damit ein herausgeloeschter
    # Eintrag nicht durchrutscht.
    for feature in ("accelerometer=()", "camera=()", "geolocation=()", "microphone=()"):
        assert feature in directives, f"Permissions-Policy deckt {feature} nicht mehr ab"
    # `-Server` versteckt das Caddy-Banner (Versions-Fingerprint).
    assert "-Server" in directives


def test_caddy_csp_of_every_site_closes_the_known_gaps() -> None:
    """Jede Site hat eine CSP, und jede schliesst die drei bekannten Luecken.

    ``form-action`` faellt **nicht** auf ``default-src`` zurueck — fehlt es, ist
    Form-Hijacking offen, obwohl die CSP streng aussieht. ``object-src`` und
    ``base-uri`` fallen zwar zurueck, werden aber explizit gefuehrt, damit eine
    spaeter aufgeweichte ``default-src`` sie nicht mitreisst.
    """
    sites = _site_blocks()
    assert len(sites) >= 4, f"Site-Bloecke nicht gefunden ({sites}) — Struktur geaendert?"
    for site in sites:
        body = _site_block_body(site)
        assert "header Content-Security-Policy" in body, f"{site}: keine eigene CSP"
        for gap in ("object-src 'none'", "frame-ancestors 'none'", "form-action", "base-uri"):
            assert gap in body, f"{site}: CSP fuehrt {gap!r} nicht mehr"


def test_caddy_blocks_internal_paths_before_the_app() -> None:
    """``/v1/internal/*`` wird im Proxy abgewiesen, nicht erst in der App.

    ADR-0010: der Pfad traegt u. a. ``/metrics``. Wird der Block entfernt, geht
    die Anfrage in den Container — ein versehentlich offener Endpunkt waere von
    aussen erreichbar.
    """
    body = _site_block_body("api.{$DOMAIN}")
    assert "@internal path /v1/internal/*" in body
    assert "respond @internal" in body and "403" in body


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

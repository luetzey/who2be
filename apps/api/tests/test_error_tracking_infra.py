"""Infra-Paket Fehler-Tracking (ADR-0062 Stufe A, W7): Env und CSP.

Zwei Zusagen, beide fuer den Fall „nichts gesetzt":

1. **CSP byte-identisch.** Die CSP der Web-App (`app.{$DOMAIN}` im Caddyfile)
   bekommt die Tracker-Origin ueber `{$CSP_CONNECT_SRC_EXTRA}`. Die
   Compose-Datei fuellt das nur, wenn `ERROR_TRACKER_ORIGIN` gesetzt ist, und
   dann MIT fuehrendem Leerzeichen. Ohne Wert ersetzt Caddy den Platzhalter
   durch den leeren String, und der Header ist Zeichen fuer Zeichen der von
   vorher. Ein Leerzeichen an der falschen Stelle wuerde den Header still
   aendern, ohne dass irgendetwas bricht — deshalb der Vergleich gegen die
   festgeschriebene Fassung.
2. **DSN leer = aus.** Jeder Dienst mit Sentry-SDK (api, mcp, mcp-http, web)
   bekommt seinen DSN mit leerem Default in allen drei Stacks (Hetzner,
   Dokploy, Repo-Root). Tracing wird nirgends durchgereicht.

Reine Datei-Tests. Ist `caddy` bzw. `docker-compose` installiert, laufen
zusaetzlich die echten Werkzeuge; in CI fehlen sie meist, dann skip.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml

_REPO_ROOT = Path(__file__).resolve().parents[3]
_CADDYFILE = _REPO_ROOT / "deploy" / "hetzner" / "Caddyfile"
_HETZNER_APP = _REPO_ROOT / "deploy" / "hetzner" / "who2be" / "docker-compose.yml"
_DOKPLOY = _REPO_ROOT / "deploy" / "dokploy" / "docker-compose.yml"
_ROOT = _REPO_ROOT / "docker-compose.yml"
_RUNBOOK = _REPO_ROOT / "deploy" / "hetzner" / "RUNBOOK.md"

# Die CSP der Web-App vor dem Infra-Paket, woertlich aus dem Caddyfile.
_CSP_BEFORE = (
    "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data:; font-src 'self' data:; "
    "connect-src 'self' https://api.{$DOMAIN} {$VITE_SUPABASE_URL}; "
    "object-src 'none'; frame-ancestors 'none'; form-action 'self'; base-uri 'self'"
)
_PLACEHOLDER = "{$CSP_CONNECT_SRC_EXTRA}"
_CADDY_ENV_VALUE = "${ERROR_TRACKER_ORIGIN:+ ${ERROR_TRACKER_ORIGIN}}"


def _app_csp() -> str:
    text = _CADDYFILE.read_text(encoding="utf-8")
    block = text.split("\napp.{$DOMAIN} {", 1)[1].split("\n}", 1)[0]
    match = re.search(r'header Content-Security-Policy "([^"]*)"', block)
    assert match, "CSP der Web-App im Caddyfile nicht gefunden — Struktur geaendert?"
    return match.group(1)


def _services(path: Path) -> dict[str, dict[str, Any]]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    services: dict[str, dict[str, Any]] = data["services"]
    return services


def _env(path: Path, service: str) -> dict[str, str]:
    environment = _services(path)[service].get("environment") or {}
    assert isinstance(environment, dict), f"{path.name}/{service}: environment als Liste"
    return {str(k): str(v) for k, v in environment.items()}


# --- 1. CSP -----------------------------------------------------------------


def test_app_csp_without_tracker_is_byte_identical() -> None:
    """Leerer Platzhalter ⇒ exakt die CSP von vorher."""
    csp = _app_csp()
    assert _PLACEHOLDER in csp, "Platzhalter fuer die Tracker-Origin fehlt in der CSP"
    assert csp.replace(_PLACEHOLDER, "") == _CSP_BEFORE


def test_placeholder_sits_directly_behind_the_last_connect_src_entry() -> None:
    """Kein Leerzeichen VOR dem Platzhalter — das Leerzeichen bringt der Wert mit.

    Stuende es im Caddyfile, bekaeme die CSP ohne Tracker ein doppeltes
    Leerzeichen vor dem Semikolon und waere nicht mehr byte-identisch.
    """
    csp = _app_csp()
    assert "{$VITE_SUPABASE_URL}" + _PLACEHOLDER + ";" in csp


def test_only_the_app_site_gets_the_tracker_origin() -> None:
    """api./mcp./supabase. senden keine Browser-Events; ihre CSP bleibt `default-src 'none'`."""
    text = _CADDYFILE.read_text(encoding="utf-8")
    headers = [line for line in text.splitlines() if "header Content-Security-Policy" in line]
    assert sum(_PLACEHOLDER in line for line in headers) == 1


def test_caddy_receives_the_origin_only_when_set() -> None:
    """Compose setzt den Platzhalter leer oder als ' <origin>'."""
    env = _env(_HETZNER_APP, "caddy")
    assert env.get("CSP_CONNECT_SRC_EXTRA") == _CADDY_ENV_VALUE


def test_runbook_traefik_csp_matches_caddy() -> None:
    """Der Dokploy-Pfad (Traefik-Datei im RUNBOOK) traegt dieselbe Web-CSP."""
    text = _RUNBOOK.read_text(encoding="utf-8")
    match = re.search(r'who2be-csp-web:.*?contentSecurityPolicy: "([^"]*)"', text, re.S)
    assert match, "who2be-csp-web im RUNBOOK nicht gefunden"
    expected = (
        _app_csp()
        .replace(_PLACEHOLDER, "")
        .replace("{$DOMAIN}", "<DOMAIN>")
        .replace("{$VITE_SUPABASE_URL}", "https://supabase.<DOMAIN>")
    )
    assert match.group(1) == expected


@pytest.mark.skipif(shutil.which("caddy") is None, reason="caddy nicht installiert")
def test_caddy_adapt_renders_identical_csp_without_tracker(tmp_path: Path) -> None:
    """Gegenprobe mit dem echten Caddy: leer, ungesetzt und gesetzt."""
    base = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": str(tmp_path),
        "DOMAIN": "example.com",
        "ACME_EMAIL": "ops@example.com",
        "VITE_SUPABASE_URL": "https://supabase.example.com",
    }

    def connect_src(extra: dict[str, str]) -> str:
        out = subprocess.run(
            ["caddy", "adapt", "--config", str(_CADDYFILE), "--adapter", "caddyfile"],
            env={**base, **extra},
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        json.loads(out)
        found: list[str] = re.findall(r"connect-src [^;]*;", out)
        assert len(found) == 1
        return found[0]

    before = "connect-src 'self' https://api.example.com https://supabase.example.com;"
    assert connect_src({}) == before
    assert connect_src({"CSP_CONNECT_SRC_EXTRA": ""}) == before
    assert connect_src({"CSP_CONNECT_SRC_EXTRA": " https://errors.example.org"}) == (
        "connect-src 'self' https://api.example.com https://supabase.example.com "
        "https://errors.example.org;"
    )


@pytest.mark.skipif(shutil.which("docker-compose") is None, reason="docker-compose fehlt")
def test_compose_renders_empty_or_prefixed_origin(tmp_path: Path) -> None:
    """Compose-Interpolation `${X:+ ${X}}` liefert '' bzw. ' <origin>'."""
    probe = tmp_path / "compose.yml"
    probe.write_text(
        "services:\n  caddy:\n    image: scratch\n    environment:\n"
        f'      CSP_CONNECT_SRC_EXTRA: "{_CADDY_ENV_VALUE}"\n',
        encoding="utf-8",
    )

    def render(extra: dict[str, str]) -> str:
        env = {"PATH": os.environ.get("PATH", ""), "HOME": str(tmp_path), **extra}
        out = subprocess.run(
            ["docker-compose", "-f", str(probe), "config", "--format", "json"],
            env=env,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        return str(json.loads(out)["services"]["caddy"]["environment"]["CSP_CONNECT_SRC_EXTRA"])

    assert render({}) == ""
    assert render({"ERROR_TRACKER_ORIGIN": ""}) == ""
    assert render({"ERROR_TRACKER_ORIGIN": "https://errors.example.org"}) == (
        " https://errors.example.org"
    )


# --- 2. DSN-Env -------------------------------------------------------------

_SENTRY_SERVICES: list[tuple[Path, str, str, str]] = [
    # (Datei, Dienst, Variable im Container, erwarteter Compose-Wert)
    (_HETZNER_APP, "api", "SENTRY_DSN", "${SENTRY_DSN_API:-}"),
    (_HETZNER_APP, "mcp", "SENTRY_DSN", "${SENTRY_DSN_MCP:-}"),
    (_HETZNER_APP, "mcp-http", "SENTRY_DSN", "${SENTRY_DSN_MCP:-}"),
    (_HETZNER_APP, "web", "WHO2BE_SENTRY_DSN", "${SENTRY_DSN_WEB:-}"),
    (_DOKPLOY, "api", "SENTRY_DSN", "${SENTRY_DSN_API:-}"),
    (_DOKPLOY, "mcp-http", "SENTRY_DSN", "${SENTRY_DSN_MCP:-}"),
    (_DOKPLOY, "web", "WHO2BE_SENTRY_DSN", "${SENTRY_DSN_WEB:-}"),
    (_ROOT, "api", "SENTRY_DSN", "${SENTRY_DSN_API:-}"),
    (_ROOT, "mcp", "SENTRY_DSN", "${SENTRY_DSN_MCP:-}"),
    (_ROOT, "web", "WHO2BE_SENTRY_DSN", "${SENTRY_DSN_WEB:-}"),
]


@pytest.mark.parametrize(
    ("path", "service", "name", "value"),
    _SENTRY_SERVICES,
    ids=[f"{p.parent.name}/{s}" for p, s, _, _ in _SENTRY_SERVICES],
)
def test_dsn_is_passed_with_empty_default(path: Path, service: str, name: str, value: str) -> None:
    assert _env(path, service).get(name) == value


@pytest.mark.parametrize("path", [_HETZNER_APP, _DOKPLOY, _ROOT], ids=lambda p: p.parent.name)
def test_tracing_is_never_passed(path: Path) -> None:
    """Tracing ist eine eigene Owner-Entscheidung (Default 0 im SDK bleibt)."""
    for service, spec in _services(path).items():
        environment = spec.get("environment") or {}
        assert "SENTRY_TRACES_SAMPLE_RATE" not in environment, f"{service} reicht Tracing durch"

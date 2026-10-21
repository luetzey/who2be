"""Fehler-Tracking fuer API und MCP-Server (Sentry-SDK, Ziel z. B. GlitchTip).

Eine Quelle fuer beide Prozesse. MCP darf `who2be_api` nicht importieren
(ADR-0005), deshalb liegt das Modul im geteilten Paket `who2be_models`.

Grundsatz: Ist `SENTRY_DSN` leer oder nicht gesetzt, wird das SDK gar nicht
initialisiert. Dann gibt es keinen Client, keinen Transport und keinen
Netzwerk-Aufruf. On-Prem-Installationen ohne Tracker merken nichts davon.

Mit DSN gilt der PII-Filter in vier Stufen:

1. PII aus: `send_default_pii` bleibt ungesetzt, das SDK wertet das als False
   (keine IP, keine Cookies, kein Nutzer). Die MCP-Integration erfasst
   Werkzeug-Argumente und -Ergebnisse nur bei PII an.
2. `include_local_variables=False` und `max_request_body_size="never"`:
   In Stack-Locals und Request-Bodies liegen Element-Inhalte und Tokens.
3. `EventScrubber` mit eigener Denylist, rekursiv ueber das ganze Event.
4. `before_send` (auch fuer Transaktionen) und `before_breadcrumb` als letzte
   Schranke: Sie entfernen Request-Daten, Cookies, Query-Strings, Header und
   die Werkzeug-Argumente/-Ergebnisse der MCP-Integration vollstaendig und
   maskieren `w2b_`-Tokens, JWTs, Bearer-Werte, E-Mail-Adressen und
   Query-Strings in jedem Text.

Umgebungsvariablen (alle optional):

- `SENTRY_DSN`: Ziel-DSN, leer bedeutet aus.
- `SENTRY_ENVIRONMENT`: Umgebungs-Tag, Default `production`.
- `SENTRY_RELEASE`: Release-Tag, Default `<dienst>@<version>`.
- `SENTRY_TRACES_SAMPLE_RATE`: Anteil fuer Tracing, Default `0` (aus).
"""

from __future__ import annotations

import os
import re
from collections.abc import Mapping, Sequence
from typing import Any

import sentry_sdk
from sentry_sdk.integrations import Integration
from sentry_sdk.scrubber import DEFAULT_DENYLIST, DEFAULT_PII_DENYLIST, EventScrubber
from sentry_sdk.transport import Transport

# Schluesselnamen, deren Wert nie ein Event verlaesst (Vergleich in Kleinschrift).
# Ergaenzt die SDK-Listen um die Who2Be-spezifischen Felder aus dem
# Stabilitaets-Bericht §2.2: Tokens, E-Mail und Element-Inhalte.
WHO2BE_DENYLIST: tuple[str, ...] = (
    "authorization",
    "proxy-authorization",
    "cookie",
    "set-cookie",
    "x-api-key",
    "api_key",
    "api_token",
    "token",
    "access_token",
    "refresh_token",
    "id_token",
    "jwt",
    "jwt_secret",
    "bearer",
    "secret",
    "client_secret",
    "code",
    "email",
    "e-mail",
    "mail",
    "content",
    "markdown",
    "body",
    "text",
    "data",
    "query",
    "query_string",
    "password",
)

_MASK = "[Filtered]"

# Textmuster, die in Fehlermeldungen, Log-Zeilen und Breadcrumbs maskiert werden.
_TEXT_PATTERNS: tuple[re.Pattern[str], ...] = (
    # Who2Be-API-Tokens.
    re.compile(r"w2b_[A-Za-z0-9_\-]+"),
    # JWTs (drei Base64url-Teile, Header beginnt mit eyJ).
    re.compile(r"eyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]*"),
    # Bearer-Werte in Header-Echos.
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._~+/\-]+=*"),
    # E-Mail-Adressen.
    re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}"),
    # Query-Strings in URLs aus Log-Zeilen (OAuth-`code`, `token` u. a.).
    re.compile(r"\?[^\s\"'#]*=[^\s\"'#]*"),
)

# Request-Felder, die nie mitgeschickt werden. Uebrig bleiben Methode und URL
# ohne Query-String.
_REQUEST_DROP: tuple[str, ...] = ("data", "cookies", "headers", "query_string", "env")

# Span-/Trace-Daten der MCPIntegration, die Nutzerinhalte tragen. Die
# Integration setzt `mcp.request.argument.<name>` OHNE PII-Pruefung
# (sentry-sdk 2.72, integrations/mcp.py), deshalb entfernt `before_send` diese
# Schluessel ueberall im Event, auch in Trace-Kontext und Spans.
_CONTENT_KEY_PREFIXES: tuple[str, ...] = (
    "mcp.request.argument.",
    "mcp.tool.result.content",
    "mcp.prompt.result.message_content",
    "mcp.resource.uri",
    "gen_ai.",
)


def scrub_text(value: str) -> str:
    """Maskiert Tokens, JWTs, Bearer-Werte und E-Mail-Adressen in einem Text."""
    for pattern in _TEXT_PATTERNS:
        value = pattern.sub(_MASK, value)
    return value


def _scrub_strings(node: Any) -> Any:
    """Wendet `scrub_text` rekursiv auf alle Strings in Dicts und Listen an."""
    if isinstance(node, str):
        return scrub_text(node)
    if isinstance(node, dict):
        for key, value in node.items():
            node[key] = _scrub_strings(value)
        return node
    if isinstance(node, list):
        for index, value in enumerate(node):
            node[index] = _scrub_strings(value)
        return node
    return node


def _drop_content_keys(node: Any) -> None:
    """Entfernt rekursiv alle Schluessel mit Inhalts-Praefix (MCP-Argumente u. a.)."""
    if isinstance(node, dict):
        for key in [k for k in node if isinstance(k, str) and k.startswith(_CONTENT_KEY_PREFIXES)]:
            del node[key]
        for value in node.values():
            _drop_content_keys(value)
    elif isinstance(node, list):
        for value in node:
            _drop_content_keys(value)


def _strip_request(event: dict[str, Any]) -> None:
    request = event.get("request")
    if not isinstance(request, dict):
        return
    for key in _REQUEST_DROP:
        request.pop(key, None)
    url = request.get("url")
    if isinstance(url, str):
        request["url"] = url.split("?", 1)[0].split("#", 1)[0]


def before_send(event: dict[str, Any], _hint: Mapping[str, Any]) -> dict[str, Any]:
    """Letzte Schranke vor dem Versand eines Events (Fehler und Transaktionen)."""
    _strip_request(event)
    event.pop("user", None)
    _drop_content_keys(event)
    _scrub_strings(event)
    return event


def before_breadcrumb(crumb: dict[str, Any], _hint: Mapping[str, Any]) -> dict[str, Any]:
    """Breadcrumbs tragen Log-Zeilen und HTTP-Ziele, deshalb dieselbe Maskierung."""
    data = crumb.get("data")
    if isinstance(data, dict):
        url = data.get("url")
        if isinstance(url, str):
            data["url"] = url.split("?", 1)[0]
        data.pop("http.query", None)
        data.pop("http.fragment", None)
    _scrub_strings(crumb)
    return crumb


def build_scrubber() -> EventScrubber:
    """`EventScrubber` mit SDK-Denylist plus Who2Be-Denylist, rekursiv."""
    denylist = list(dict.fromkeys([*DEFAULT_DENYLIST, *WHO2BE_DENYLIST]))
    return EventScrubber(
        denylist=denylist,
        pii_denylist=list(DEFAULT_PII_DENYLIST),
        recursive=True,
        send_default_pii=False,
    )


def _sample_rate(raw: str | None) -> float:
    try:
        rate = float(raw) if raw else 0.0
    except ValueError:
        return 0.0
    return min(max(rate, 0.0), 1.0)


def init_error_tracking(
    service: str,
    version: str,
    *,
    integrations: Sequence[Integration] = (),
    environ: Mapping[str, str] | None = None,
    transport: type[Transport] | None = None,
) -> bool:
    """Initialisiert das Sentry-SDK, wenn `SENTRY_DSN` gesetzt ist.

    Gibt `True` zurueck, wenn das SDK aktiv ist. Ohne DSN passiert nichts:
    `sentry_sdk.init` wird nicht aufgerufen, also auch kein Transport angelegt.

    `transport` ist nur fuer Tests gedacht, damit Events ohne Netzwerk
    abgefangen werden koennen.
    """
    env = os.environ if environ is None else environ
    dsn = env.get("SENTRY_DSN", "").strip()
    if not dsn:
        return False

    options: dict[str, Any] = {
        "dsn": dsn,
        "environment": env.get("SENTRY_ENVIRONMENT", "").strip() or "production",
        "release": env.get("SENTRY_RELEASE", "").strip() or f"{service}@{version}",
        "server_name": service,
        # Bewusst NICHT `send_default_pii=False` setzen: Die Option ist ab
        # sentry-sdk 2.6x deprecated. Ungesetzt behandelt das SDK sie als False
        # (keine IP, keine Cookies, kein Nutzer, keine MCP-Argumente). Ein
        # `data_collection`-Block wuerde dagegen den EventScrubber abschalten.
        "include_local_variables": False,
        "max_request_body_size": "never",
        "event_scrubber": build_scrubber(),
        "before_send": before_send,
        "before_send_transaction": before_send,
        "before_breadcrumb": before_breadcrumb,
        "traces_sample_rate": _sample_rate(env.get("SENTRY_TRACES_SAMPLE_RATE")),
        "integrations": list(integrations),
    }
    if transport is not None:
        options["transport"] = transport
    sentry_sdk.init(**options)
    return True

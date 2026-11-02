"""Per-Request-Policy-Filterung der MCP-Tool-Liste (ADR-0042, ADR-0059).

FastMCP-Middleware, die `tools/list` pro Request auf die Tools filtert, die
die `AgentToolPolicy` des aufrufenden Bearer-Tokens gewaehrt UND das
Werkzeug-Profil seines Agenten durchlaesst (`whoami.tool_profile`), und
direkte Aufrufe ausgeblendeter Tools mit einer klaren Meldung ablehnt. SSoT
fuer die Rechte ist `who2be_models.tool_requirements`, fuer Gruppen, Kern und
Profil-Formel `who2be_models.tool_profiles` — dieselben Funktionen nutzt der
`tools-overview`-Prompt-Resolver der API (kein Drift).

Das Profil blendet nur aus, es erweitert nie (ADR-0059 §3.1): Was die Rechte
verbergen, bleibt verborgen; die Kern-Werkzeuge `ping`, `whoami` und
`report_problem` blendet kein Profil aus. Ohne `tool_profile` (Menschen,
ungebundene Tokens, Agenten auf „Alle", aeltere API) filtert die Middleware
wie vorher nur nach Rechten. Bei `tools/call` unterscheidet sie zwei
Meldungen: Rechte fehlen, oder nur das Profil verbirgt das Werkzeug — dann
nennt die Meldung den Meldeweg `report_problem` mit `tool_request` (§8).

Das ist bewusst KEINE Security-Grenze: Die autoritative Durchsetzung bleibt
serverseitig bei der API (ADR-0039). Daher gilt durchgehend **fail-open**:
- Kein Token / Aufloesung fehlgeschlagen (401, Netz, kaputter Header) →
  ungefilterte Liste + Warn-Log; ein leeres `tools/list` reproduzierte sonst
  das bekannte "verbunden, aber keine Tools"-Symptom. Insbesondere bleibt der
  auth-freie `ping`-Pfad ohne (gueltigen) Token sichtbar und aufrufbar.
- Unbekannter Tool-Name (fehlt in `MCP_TOOL_REQUIREMENTS`) → sichtbar lassen
  + einmaliges Warn-Log; der Paritaetstest in `tests/test_policy_filter.py`
  faengt das im CI.

Die Identitaet (`whoami`) wird pro Token-SHA-256 gecacht (LRU + TTL, Muster
`_workspace_cache` in `server.py`). Rechte- und Profil-Aenderungen wirken nach
hoechstens 60 Sekunden (W59-5, ADR-0059 §6.2); ein Neuverbinden verkuerzt das
nicht, weil der Cache am Token haengt. Das `ttlMs` von `tools/list` setzt
FastMCP (heute `0`, `cacheScope: private`); es liegt unter dieser TTL und
bleibt deshalb unveraendert — `tests/test_policy_filter.py` haelt die Grenze.
"""

from __future__ import annotations

import hashlib
import logging
import time
from collections import OrderedDict
from collections.abc import Sequence

import mcp.types as mt
from fastmcp.exceptions import ToolError
from fastmcp.server.middleware import CallNext, Middleware, MiddlewareContext
from fastmcp.tools.base import Tool, ToolResult

from who2be_mcp.config import get_settings
from who2be_models import (
    WhoAmIRead,
    is_tool_in_profile,
    is_tool_visible_for,
    is_tool_visible_for_with_profile,
)

logger = logging.getLogger(__name__)

# whoami-Identitaet wird PRO TOKEN gecacht (Streamable-HTTP ist multi-tenant:
# jeder Request traegt seinen eigenen Bearer, ADR-0034). Key ist der
# SHA-256-Hash des Tokens (defense-in-depth: kein Klartext-Token als
# Dict-Key), Wert ist (WhoAmIRead, Ablauf-Monotonic). LRU-Schranke + TTL wie
# beim `_workspace_cache` in `server.py`. TTL 60 s nach W59-5 (Owner
# 2026-10-21, ADR-0059 §6.2): eine Freigabe im Web wirkt binnen einer Minute.
_WHOAMI_CACHE_MAX = 512
_WHOAMI_CACHE_TTL_SECONDS = 60.0
_whoami_cache: OrderedDict[str, tuple[WhoAmIRead, float]] = OrderedDict()

# Bereits gewarnte unbekannte Tool-Namen — das Warn-Log soll pro Prozess nur
# einmal pro Tool erscheinen, nicht bei jedem tools/list.
_warned_unknown_tools: set[str] = set()


def _token_key(token: str) -> str:
    # Lokale Kopie von `server._token_key`: server.py importiert dieses Modul
    # (Middleware-Registrierung), ein Import in Gegenrichtung waere ein Zyklus.
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _whoami_cache_get(token: str) -> WhoAmIRead | None:
    key = _token_key(token)
    entry = _whoami_cache.get(key)
    if entry is None:
        return None
    identity, expires_at = entry
    if time.monotonic() >= expires_at:
        _whoami_cache.pop(key, None)
        return None
    _whoami_cache.move_to_end(key)
    return identity


def _whoami_cache_put(token: str, identity: WhoAmIRead) -> None:
    key = _token_key(token)
    _whoami_cache[key] = (identity, time.monotonic() + _WHOAMI_CACHE_TTL_SECONDS)
    _whoami_cache.move_to_end(key)
    while len(_whoami_cache) > _WHOAMI_CACHE_MAX:
        _whoami_cache.popitem(last=False)


def _rights_hidden_message(name: str) -> str:
    return (
        f"Tool '{name}' ist fuer diesen Agenten nicht freigeschaltet — "
        "pruefe deine Berechtigungen via whoami."
    )


def _profile_hidden_message(name: str, profile_name: str) -> str:
    # Wortlaut ADR-0059 §8: nennt keine Rechte und verspricht keine Freigabe.
    return (
        f"Werkzeug `{name}` liegt nicht in deinem Werkzeug-Profil „{profile_name}“. "
        'Brauchst du es, melde es mit `report_problem` (`category="tool_request"`, '
        "in `note` das Werkzeug und wofuer). Ein Mensch passt dein Profil an."
    )


class PolicyFilterMiddleware(Middleware):
    """Filtert `tools/list` und sperrt `tools/call` nach Token-Policy und Profil.

    Nutzt `is_tool_visible_for_with_profile` aus `who2be_models.tool_profiles`
    gegen die per `whoami` aufgeloeste Identitaet des Request-Tokens. Fail-open
    in jede Richtung (siehe Modul-Docstring) — die API bleibt autoritativ.
    """

    async def _resolve_identity(self) -> WhoAmIRead | None:
        """Loest die Identitaet des Request-Tokens auf (`whoami`, gecacht).

        `None` bei JEDEM Fehler (kein/leerer Token, 401, Netz, fehlender
        HTTP-Kontext) — der Caller behandelt das fail-open. Der Token selbst
        wird nie geloggt.
        """
        # Deferred Import: server.py importiert dieses Modul fuer die
        # Middleware-Registrierung — ein Top-Level-Import waere ein Zyklus.
        # Attribut-Zugriff zur Laufzeit haelt zudem Test-Monkeypatches auf
        # `server.build_client`/`server.get_http_headers` wirksam.
        from who2be_mcp import server

        try:
            settings = get_settings()
            token = server._request_token(settings)
            if not token:
                return None
            cached = _whoami_cache_get(token)
            if cached is not None:
                return cached
            # `build_client` buendelt Token- + Workspace-Aufloesung (inkl.
            # `/v1/me`-Cache) — derselbe Pfad wie bei jedem Tool-Call.
            client = await server.build_client()
            identity = await client.whoami()
        except Exception as exc:  # fail-open by design (ADR-0042)
            logger.warning(
                "Policy-Aufloesung fuer tools/list|call fehlgeschlagen (%s) — fail-open.",
                type(exc).__name__,
            )
            return None
        _whoami_cache_put(token, identity)
        return identity

    @staticmethod
    def _is_visible(identity: WhoAmIRead, name: str) -> bool | None:
        """Rechte UND Profil (ADR-0059 §3.1); `None` fuer unbekannte Namen."""
        return is_tool_visible_for_with_profile(
            name,
            unrestricted=identity.unrestricted,
            role=identity.role,
            capabilities=identity.capabilities,
            read_scopes=identity.read_scopes,
            memory_mode=identity.memory_mode,
            tool_profile=identity.tool_profile,
        )

    @staticmethod
    def _hidden_message(identity: WhoAmIRead, name: str) -> str | None:
        """Sperr-Meldung fuer `tools/call`, `None` wenn der Aufruf durchgeht.

        Die Rechte gehen vor: Verbergen sie das Werkzeug, kommt die
        Rechte-Meldung, auch wenn das Profil es ebenfalls ausblendet. Nur wenn
        allein das Profil es verbirgt, kommt die Profil-Meldung (§8).
        Unbekannte Namen gehen durch (fail-open, die API setzt durch).
        """
        by_rights = is_tool_visible_for(
            name,
            unrestricted=identity.unrestricted,
            role=identity.role,
            capabilities=identity.capabilities,
            read_scopes=identity.read_scopes,
            memory_mode=identity.memory_mode,
        )
        if by_rights is False:
            return _rights_hidden_message(name)
        grant = identity.tool_profile
        if by_rights is None or identity.unrestricted or grant is None:
            return None
        if is_tool_in_profile(name, grant):
            return None
        return _profile_hidden_message(name, grant.name)

    async def on_list_tools(
        self,
        context: MiddlewareContext[mt.ListToolsRequest],
        call_next: CallNext[mt.ListToolsRequest, Sequence[Tool]],
    ) -> Sequence[Tool]:
        tools = await call_next(context)
        identity = await self._resolve_identity()
        if identity is None:
            return tools
        visible: list[Tool] = []
        for tool in tools:
            allowed = self._is_visible(identity, tool.name)
            if allowed is None:
                # Unbekanntes Tool: fail-open sichtbar lassen. Der
                # Drift-Guard-Test (test_policy_filter.py) macht das CI-rot.
                if tool.name not in _warned_unknown_tools:
                    _warned_unknown_tools.add(tool.name)
                    logger.warning(
                        "MCP-Tool '%s' fehlt in MCP_TOOL_REQUIREMENTS — "
                        "fail-open sichtbar; Mapping ergaenzen (ADR-0042).",
                        tool.name,
                    )
                visible.append(tool)
            elif allowed:
                visible.append(tool)
        return visible

    async def on_call_tool(
        self,
        context: MiddlewareContext[mt.CallToolRequestParams],
        call_next: CallNext[mt.CallToolRequestParams, ToolResult],
    ) -> ToolResult:
        identity = await self._resolve_identity()
        # Nur bei ERFOLGREICH aufgeloester Identitaet und explizit unsichtbarem
        # Tool sperren; Aufloesungsfehler oder unbekannter Name werden
        # durchgelassen — die API setzt autoritativ durch (ADR-0039).
        if identity is not None:
            message = self._hidden_message(identity, context.message.name)
            if message is not None:
                raise ToolError(message)
        return await call_next(context)

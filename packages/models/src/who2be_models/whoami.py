"""Pydantic-Modell fuer `GET /v1/workspaces/{ws_id}/whoami` (#253).

Identitaets- und Capability-Introspektion fuer den aufrufenden Principal:
Mensch (JWT), ungebundener API-Token oder agent-gebundener API-Token. Liefert
genug, damit ein Agent (oder die Web-UI) ohne Raten weiss, *was er ist* und
*was er darf* — Rolle, Agent-Bindung, gewaehrte Write-Capabilities, Read-Scopes
und die org-weiten Entitlement-Features.
"""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel

from who2be_models.locale import DEFAULT_LOCALE, ContentLocale
from who2be_models.tool_policy import (
    AgentCapability,
    MemoryDirective,
    MemoryMode,
    ReadScope,
    TransitionGrant,
)
from who2be_models.workarea import WorkAreaAssignment
from who2be_models.workspace_member import WorkspaceRole


class WhoAmIRead(BaseModel):
    """Antwort von `GET /v1/workspaces/{ws_id}/whoami`.

    `unrestricted` ist die KRITISCHE Unterscheidung: Mensch/JWT und ungebundene
    API-Tokens tragen KEINE Pro-Agent-Tool-Policy. Das heisst **"keine
    Pro-Agent-Restriktion"**, NICHT "nichts erlaubt" — fuer sie gilt allein das
    Rollen-Gate (`require_role`). In diesem Fall ist `unrestricted=True`,
    `capabilities` ist `None` (NICHT die leere Liste — die hiesse "explizit
    nichts gewaehrt") und `read_scopes` ist `None`. Nur ein agent-gebundener
    Token traegt eine konkrete Policy: dann ist `unrestricted=False`,
    `capabilities` listet die tatsaechlich gewaehrten Write-Capabilities und
    `read_scopes` die effektiven Lese-Scopes je Domain. So kann `whoami` nicht
    luegen — ein Mensch sieht nicht faelschlich "0 Capabilities".

    `features` traegt die org-weiten Entitlement-Features (org-scoped, ueber den
    `EntitlementPort` aufgeloest) — orthogonal zur Pro-Agent-Policy.
    """

    user_id: UUID
    workspace_id: UUID
    role: WorkspaceRole
    is_api_token: bool
    agent_id: UUID | None
    # True = keine Pro-Agent-Tool-Policy (Mensch/JWT oder ungebundener Token).
    # Dann ist `capabilities`/`read_scopes` None — es greift nur das Rollen-Gate.
    unrestricted: bool
    # Gewaehrte Write-Capabilities des gebundenen Agenten; `None` wenn
    # `unrestricted` (kein Pro-Agent-Limit), `[]` = explizit keine gewaehrt.
    capabilities: list[AgentCapability] | None
    # Effektive Read-Scopes je Domain (persona/playbook/resource/agent/
    # external_tool, WP-3); `None` wenn `unrestricted`.
    read_scopes: dict[str, ReadScope] | None
    # Feinkoernige Write-Verfeinerungen (ADR-0039); `None` wenn `unrestricted`,
    # leere Dicts = keine Verfeinerung (ungeteiltes promote_retire / alle Tags).
    transition_grants: dict[str, TransitionGrant] | None = None
    write_tags: dict[str, list[str]] | None = None
    # Schreib-Rate-Limit (Mutationen/Minute); None = unbegrenzt oder unrestricted.
    write_rate_limit: int | None = None
    # Agent-Memory (ADR-0044): Gedaechtnis-Modus + Abfrage-Verbindlichkeit des
    # gebundenen Agenten; `None` wenn `unrestricted` (Mensch/ungebundener Token
    # hat kein Agent-Gedaechtnis). Der MCP-Adapter filtert die Memory-Tools
    # anhand von `memory_mode` (ADR-0042, `is_tool_visible_for`).
    memory_mode: MemoryMode | None = None
    memory_directive: MemoryDirective | None = None
    # Org-weite Entitlement-Features (z. B. "core", "agents", "composite_playbooks").
    features: list[str]
    # Content-Sprache DIESES Workspaces (`workspace.content_locale`, ADR-0045):
    # der Default fuer neue Elemente, wenn ein `create_*`-Aufruf `locale`
    # weglaesst. Default `'de'` hier deckt Bestandsdaten/Alt-Clients (spiegelt
    # `WorkspaceRead.content_locale`) — jeder aktuelle `whoami`-Pfad befuellt
    # das Feld explizit aus dem Workspace-Datensatz.
    content_locale: ContentLocale = DEFAULT_LOCALE
    # WorkArea-Zuordnungen des gebundenen Agenten (ADR-0047): id/name/scope/
    # level je Grant, inkl. der beim whoami-Aufruf auto-angelegten privaten
    # Area. `None` fuer Menschen/ungebundene Tokens — die haben keine
    # Grant-Menge (editor+ liest ohnehin alles, viewer die shared Areas).
    work_areas: list[WorkAreaAssignment] | None = None

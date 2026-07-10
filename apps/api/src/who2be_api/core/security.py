"""Authentifizierung: Supabase-JWT und API-Token (ADR-0006).

Zwei Wege, ein `owner_id`-Kontext. Die Dependency `get_current_user` erkennt
den Weg am Token-Praefix `w2b_` und liefert in beiden Faellen die `owner_id`.

Phase 2.1a-2: zusaetzlich `get_current_workspace`, das aus Path-Parameter
`workspace_id` plus `get_current_user` einen `WorkspaceContext` (User, WS,
Rolle) baut. Mitgliedschaftspruefung ueber `workspace_member`; API-Token
tragen einen `workspace_id`-Snapshot, der gegen das Path-Segment matchen
muss (Defense gegen Cross-Workspace-Token-Reuse).
"""

import hashlib
import logging
import secrets
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

import asyncpg
import jwt
import structlog
from fastapi import Depends, HTTPException, Path, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from who2be_api.core.config import get_settings
from who2be_api.core.db import get_pool
from who2be_api.core.errors import ApiGateError
from who2be_api.core.tenancy import tenant_scope
from who2be_api.licensing.edition import is_onprem
from who2be_api.repositories.token_repository import PgTokenRepository, TokenRepository
from who2be_models import AgentCapability, AgentToolPolicy, WorkspaceRole

logger = logging.getLogger(__name__)

TOKEN_PREFIX = "w2b_"
_JWT_ALGORITHM = "HS256"
# Supabase GoTrue setzt fuer signed-in-Endnutzer `aud=authenticated`. Service-Tokens
# (`role=service_role`) sollen die API NICHT als Owner durchlassen, auch wenn sie
# zufaellig mit demselben Secret signiert sind.
_JWT_AUDIENCE = "authenticated"
_JWT_ALLOWED_ROLES = frozenset({"authenticated"})

_bearer_scheme = HTTPBearer(auto_error=False)


def _jwt_issuer(supabase_url: str) -> str | None:
    """Erwarteter `iss`-Claim eines Supabase-JWT (`<supabase_url>/auth/v1`).

    Gibt `None` zurueck, wenn `SUPABASE_URL` nicht konfiguriert ist — dann wird
    die Pruefung uebersprungen (Dev-/Test-Mode ohne issuer-Bindung).
    """
    base = supabase_url.rstrip("/")
    return f"{base}/auth/v1" if base else None


def new_token() -> str:
    """Erzeugt einen neuen Klartext-API-Token (`w2b_`-praefixiert)."""
    return f"{TOKEN_PREFIX}{secrets.token_urlsafe(32)}"


def hash_token(token: str) -> str:
    """SHA-256-Hexdigest eines Tokens — nur der Hash wird persistiert."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _credentials_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Ungueltige oder fehlende Anmeldedaten.",
        headers={"WWW-Authenticate": "Bearer"},
    )


@dataclass(frozen=True)
class CurrentPrincipal:
    """Authentifizierter Aufrufer.

    `token_workspace_id` ist nur fuer den API-Token-Pfad gesetzt — Tokens sind
    pro Workspace gepinnt. JWT-Aufrufer haben `None` und werden in
    `get_current_workspace` allein per Membership autorisiert.

    `token_role` traegt im Token-Pfad die gepinnte Snapshot-Rolle aus
    `api_token.role` (ADR-0023); im JWT-Pfad `None` (Rolle kommt dann aus
    `workspace_member`).

    `email` ist nur im JWT-Pfad gesetzt — Supabase liefert die User-Email als
    Claim mit. Wird vom Invitation-Accept genutzt, um Einladungen an die
    falsche Email-Adresse abzuweisen (Phase 3-D). API-Tokens tragen keinen
    Email-Claim.

    `aal` ist nur im JWT-Pfad gesetzt — GoTrue liefert den Authenticator-
    Assurance-Level ("aal1" nach Ein-Faktor-Login, "aal2" nach verifizierter
    MFA-Challenge) als Claim. Das Admin-MFA-Gate (`require_aal2`) liest ihn.
    API-Tokens tragen keinen aal-Claim (`None`).
    """

    user_id: UUID
    token_workspace_id: UUID | None
    token_role: WorkspaceRole | None = None
    email: str | None = None
    aal: str | None = None
    # Nur im API-Token-Pfad und nur, wenn der Token an einen Agenten gebunden
    # ist: dann erbt jeder Aufruf die MCP-Tool-Policy dieses Agenten. `None` =
    # ungebundener Token (oder JWT) → keine Pro-Agent-Restriktion.
    token_agent_id: UUID | None = None


@dataclass(frozen=True)
class WorkspaceContext:
    """Workspace + User + Rolle des Aufrufers — Standard-Service-Argument.

    `is_api_token` ist True, wenn der Aufruf ueber einen `w2b_`-API-Token kam
    (MCP-Server). Services nutzen das Flag, um nur Active-Versionen
    zurueckzuliefern (Plan §2.1.D — Active-Filter im Repo).

    `role` ist die effektive Rolle (Membership-Rolle im JWT-Pfad,
    Snapshot-Rolle im Token-Pfad) und Basis fuer `require_role` (ADR-0023).

    `aal` traegt im JWT-Pfad den Authenticator-Assurance-Level-Claim
    ("aal1"/"aal2") aus dem GoTrue-Token; das Admin-MFA-Gate (`require_aal2`,
    WP-F/S1) wertet ihn aus. Im API-Token-Pfad `None` — Tokens sind ein
    Maschinen-Pfad ohne MFA-Konzept und vom Gate ausgenommen.
    """

    workspace_id: UUID
    user_id: UUID
    role: WorkspaceRole
    is_api_token: bool = False
    aal: str | None = None
    # An welchen Agenten der aufrufende Token gebunden ist (None = ungebunden
    # oder JWT). Gesetzt im Token-Pfad von `get_current_workspace`.
    agent_id: UUID | None = None
    # Die MCP-Tool-Policy des gebundenen Agenten. `None` heisst „keine
    # Pro-Agent-Restriktion" (Mensch/JWT oder ungebundener Token) — dann greift
    # allein das Rollen-Gate. Ist sie gesetzt, prueft `require_capability` die
    # Writes und die Read-Services scopen ueber `tool_policy`.
    tool_policy: AgentToolPolicy | None = None

    def sees_drafts(self, capability: AgentCapability) -> bool:
        """True, wenn dieser Aufrufer die Current-Version (inkl. Draft/Review)
        lesen darf, statt nur die `active`-Version.

        „Wer pflegen darf, darf auch Drafts sehen" — die Draft-Sichtbarkeit eines
        Read-Pfads folgt der zugehoerigen Write-Capability der Entitaet. Drei
        Faelle:

        - **Mensch/JWT** (`is_api_token=False`): immer — der Web-Editor arbeitet
          grundsaetzlich auf der Current-Version.
        - **Agent-gebundener Token**: nur, wenn die Policy `capability` gewaehrt
          (z. B. ein Editor-/Meta-Agent wie der Builder mit `playbook_write`).
          Reine Konsum-Agenten (Write aus) bleiben auf `active` — kein Leck
          unfertiger Inhalte.
        - **Ungebundener API-Token** (`tool_policy is None`, aber `is_api_token`):
          bleibt auf `active` (bestehendes MCP-Konsum-Verhalten, Phase 2.1b).

        Aufrufer leiten daraus `active_only = not ctx.sees_drafts(cap)` ab.
        """
        if not self.is_api_token:
            return True
        if self.tool_policy is None:
            return False
        return self.tool_policy.allows(capability)


# Rollen-Hierarchie admin > editor > viewer (ADR-0023). Numerischer Rang fuer
# `require_role`-Vergleiche — Single-Source der Ordnung im Backend.
_ROLE_ORDER: dict[WorkspaceRole, int] = {
    WorkspaceRole.viewer: 0,
    WorkspaceRole.editor: 1,
    WorkspaceRole.admin: 2,
}


def role_satisfies(actual: WorkspaceRole, minimum: WorkspaceRole) -> bool:
    """True, wenn `actual` mindestens `minimum` in der Hierarchie erreicht."""
    return _ROLE_ORDER[actual] >= _ROLE_ORDER[minimum]


# Authenticator Assurance Level (GoTrue/Supabase): "aal1" = ein Faktor
# (Passwort/Magic-Link), "aal2" = zusaetzlich eine verifizierte MFA-Challenge
# (TOTP). Administrative Aktionen verlangen aal2 (WP-F, Befund S1).
_AAL2 = "aal2"


def require_aal2(ctx: WorkspaceContext) -> None:
    """Wirft 403, wenn ein interaktiver Aufrufer keine MFA-(AAL2-)Session hat.

    Zentrales Gate fuer administrative Aktionen (WP-F, S1) — wird von
    `require_role` automatisch fuer `minimum == admin` aufgerufen, kann aber
    auch direkt verwendet werden. Zwei bewusste Ausnahmen, damit das Gate
    keine legitimen Bestands-/Maschinenpfade bricht:

    - **API-Token** (`is_api_token`): Maschinen-Pfad ohne MFA-Konzept (analog
      GitHub-PATs) — separat ausstellbar/revozierbar, daher exempt.
    - **Fehlender `aal`-Claim** (`aal is None`): aeltere/handsignierte
      (Magic-Link-/Test-)JWTs tragen ihn nicht — aber nur **On-Prem/Dev** wird
      das fail-open durchgelassen. In der **Cloud** setzt GoTrue `aal` immer mit;
      ein dort fehlender Claim ist verdaechtig und wird fail-**closed** behandelt
      (Zero-Trust). Ein *expliziter* Nicht-aal2-Wert (typisch "aal1") wird in
      beiden Editionen geblockt.

    Der On-Prem-fail-open-Zweig ist nicht mehr unsichtbar (SEC-1,
    Standards-Review 2026-07-08): jeder Durchlass emittiert das strukturierte
    Warn-Event `aal_missing_onprem` (ADR-0007), und der Config-Schalter
    `WHO2BE_REQUIRE_MFA_ONPREM=true` schliesst ihn hart (fail-closed wie Cloud).
    """
    if ctx.is_api_token:
        return
    if ctx.aal == _AAL2:
        return
    # Fehlender Claim: fail-open nur On-Prem/Dev (Bestands-/Test-JWTs ohne aal)
    # und nur, solange der Betreiber es nicht per WHO2BE_REQUIRE_MFA_ONPREM
    # hart abdreht. In der Cloud faellt der Pfad durch zum Raise (fail-closed)
    # — folgt dem `is_cloud()`-Editions-Muster, ohne den On-Prem-Default zu
    # brechen. Der Durchlass ist sichtbar: strukturiertes Warn-Event.
    if ctx.aal is None and is_onprem() and not get_settings().require_mfa_onprem:
        structlog.get_logger(__name__).warning(
            "aal_missing_onprem",
            user_id=str(ctx.user_id),
            workspace_id=str(ctx.workspace_id),
            detail=(
                "Admin-Aktion ohne aal-Claim On-Prem durchgelassen (fail-open). "
                "WHO2BE_REQUIRE_MFA_ONPREM=true erzwingt MFA auch On-Prem."
            ),
        )
        return
    raise ApiGateError(
        status=status.HTTP_403_FORBIDDEN,
        reason="mfa_required",
        actionable_by="human",
        detail=(
            "Diese Admin-Aktion erfordert Zwei-Faktor-Authentifizierung (MFA). "
            "Richte in den Kontoeinstellungen einen TOTP-Faktor ein und melde "
            "dich anschliessend erneut an."
        ),
    )


def require_role(ctx: WorkspaceContext, minimum: WorkspaceRole) -> None:
    """Wirft 403, wenn die Kontext-Rolle `minimum` nicht erreicht (ADR-0023).

    Administrative Aktionen (`minimum == admin`) verlangen zusaetzlich eine
    MFA-(AAL2-)Session (WP-F, S1) — das Gate haengt zentral hier, sodass jeder
    bestehende `require_role(ctx, WorkspaceRole.admin)`-Aufruf es erbt, ohne
    dass die einzelnen Call-Sites es duplizieren.
    """
    if not role_satisfies(ctx.role, minimum):
        raise ApiGateError(
            status=status.HTTP_403_FORBIDDEN,
            reason="insufficient_role",
            actionable_by="human",
            detail=f"Diese Aktion erfordert mindestens die Rolle '{minimum.value}'.",
        )
    if minimum == WorkspaceRole.admin:
        require_aal2(ctx)


# Klartext-Erklaerung pro Capability fuer die 403-Antwort an den Agenten.
_CAPABILITY_LABELS: dict[AgentCapability, str] = {
    AgentCapability.persona_write: "Personas zu erstellen oder zu aendern",
    AgentCapability.playbook_write: "Playbooks zu erstellen, zu aendern oder zu verknuepfen",
    AgentCapability.resource_write: "Resources zu erstellen, zu aendern oder zu verknuepfen",
    AgentCapability.agent_write: "Agenten zu erstellen oder zu aendern",
    AgentCapability.system_prompt_write: "System-Prompt-Templates zu verfassen oder zu aendern",
    AgentCapability.feedback_write: "Nutzung/Feedback zu melden",
    AgentCapability.feedback_resolve: (
        "Feedback-Signale zu schliessen (addressed/in_progress/dismissed)"
    ),
    AgentCapability.promote_retire: "Versionen zu aktivieren oder zu deaktivieren",
}


def require_capability(ctx: WorkspaceContext, capability: AgentCapability) -> None:
    """Wirft 403, wenn ein agent-gebundener Token die Capability nicht hat.

    Ist `ctx.tool_policy is None` (Mensch/JWT oder ungebundener API-Token), ist
    dies ein No-Op — dann gilt allein das Rollen-Gate (`require_role`). Nur wenn
    der Token an einen Agenten gebunden ist, schraenkt die Pro-Agent-Policy die
    Mutation zusaetzlich ein. So bleibt der bestehende Pfad (Web-UI,
    Admin-Tokens) unveraendert, waehrend ein Agent nur das darf, was sein
    Besitzer ihm zugestanden hat.
    """
    policy = ctx.tool_policy
    if policy is None:
        return
    if not policy.allows(capability):
        what = _CAPABILITY_LABELS.get(capability, capability.value)
        raise ApiGateError(
            status=status.HTTP_403_FORBIDDEN,
            reason="missing_capability",
            actionable_by="human",
            detail=(
                f"Dieser Agent ist nicht berechtigt, {what}. "
                "Der Workspace-Besitzer kann das in der Agent-Konfiguration freischalten."
            ),
        )


def require_unmanaged(is_managed: bool) -> None:
    """Wirft 403, wenn das Aggregat vom System verwaltet ist (Builder-Lock).

    Managed-Aggregate (geseedeter Builder: Persona/Template/Playbooks/Agent)
    duerfen von Usern NICHT bearbeitet, transitioniert oder geloescht werden —
    sie werden zentral gepflegt und per Start-Sync aktualisiert. Der Weg fuer
    eigene Anpassungen ist das Duplizieren des Agenten (erzeugt unverwaltete
    Kopien). Gilt fuer alle Aufrufer (Mensch wie Agent).
    """
    if not is_managed:
        return
    raise ApiGateError(
        status=status.HTTP_403_FORBIDDEN,
        reason="managed_aggregate",
        actionable_by="human",
        detail=(
            "Dieser Eintrag wird vom System verwaltet und kann nicht geaendert "
            "oder geloescht werden. Dupliziere den Agenten, um eine eigene, "
            "anpassbare Kopie zu erhalten."
        ),
    )


def require_write_tags(ctx: WorkspaceContext, domain: str, target_tags: list[str]) -> None:
    """Wirft 403, wenn ein agent-gebundener Token in `domain` Inhalte mit diesen
    Tags nicht schreiben darf (Tag-Praedikat-Write-Scoping, ADR-0039).

    No-Op fuer ungebundene Tokens (Mensch/Web-UI) und fuer Agenten ohne
    `write_tags`-Einschraenkung in dieser Domain. Greift bei create UND update:
    der Agent darf nur Inhalte schreiben, deren Tags die erlaubte Menge schneiden
    — sowohl der NEUE Inhalt als auch (beim Update) der BESTEHENDE muessen passen.
    """
    policy = ctx.tool_policy
    if policy is None:
        return
    if not policy.tags_permitted(domain, target_tags):
        allowed = policy.write_tags_for(domain) or []
        raise ApiGateError(
            status=status.HTTP_403_FORBIDDEN,
            reason="missing_capability",
            actionable_by="human",
            detail=(
                f"Dieser Agent darf nur {domain}-Inhalte mit den Tags {sorted(allowed)} "
                "schreiben. Der Workspace-Besitzer kann den Tag-Scope in der "
                "Agent-Konfiguration anpassen."
            ),
        )


def require_write_rate(ctx: WorkspaceContext) -> None:
    """Drosselt Schreib-Mutationen eines Agenten auf `write_rate_limit`/min (ADR-0039).

    No-Op fuer ungebundene Tokens (Mensch/Web-UI) und ohne gesetztes Limit.
    Sliding-Window keyed auf `agent_id`; ueberschritten ⇒ 429. Der globale
    slowapi-`write_limit` bleibt orthogonal die grobe Obergrenze.
    """
    from fastapi import HTTPException

    from who2be_api.core.rate_limit import token_rate_limiter

    policy = ctx.tool_policy
    if policy is None or policy.write_rate_limit is None or policy.write_rate_limit <= 0:
        return
    if ctx.agent_id is None:
        return
    if not token_rate_limiter.allow(f"write:{ctx.agent_id}", policy.write_rate_limit):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Schreib-Rate-Limit dieses Agenten erreicht — bitte spaeter erneut versuchen.",
        )


def verify_supabase_jwt(token: str) -> tuple[UUID, str | None, str | None]:
    """Verifiziert ein Supabase-JWT lokal (HS256) und liest `sub` + optional `email`/`aal`.

    Rueckgabe: `(owner_id, email_or_none, aal_or_none)`. Email- und aal-Claim
    sind optional — aelteren/handsignierten Test-JWTs fehlen sie; produktive
    Supabase-JWTs tragen beide mit. Email nutzt die Email-Mismatch-Pruefung
    beim Invitation-Accept (Phase 3-D); `aal` das Admin-MFA-Gate (WP-F/S1).
    """
    settings = get_settings()
    secret = settings.jwt_secret
    if not secret:
        raise _credentials_error()
    issuer = _jwt_issuer(settings.supabase_url)
    try:
        payload = jwt.decode(
            token,
            secret,
            algorithms=[_JWT_ALGORITHM],
            audience=_JWT_AUDIENCE,
            issuer=issuer,
            options={"require": ["exp", "sub", "aud"]},
        )
    except jwt.PyJWTError as exc:
        raise _credentials_error() from exc
    # `role` ist von Supabase per Konvention gesetzt; ohne Whitelist wuerden
    # `service_role`-Tokens (Admin) hier ebenfalls als Owner durchlaufen.
    role = payload.get("role")
    if role is not None and role not in _JWT_ALLOWED_ROLES:
        raise _credentials_error()
    sub = payload.get("sub")
    if not isinstance(sub, str):
        raise _credentials_error()
    try:
        owner_id = UUID(sub)
    except ValueError as exc:
        raise _credentials_error() from exc
    email_claim = payload.get("email")
    email = email_claim if isinstance(email_claim, str) and email_claim else None
    # `aal` (Authenticator Assurance Level): "aal1" nach Ein-Faktor-Login,
    # "aal2" nach verifizierter MFA-Challenge. Fehlt bei Test-JWTs (→ None).
    aal_claim = payload.get("aal")
    aal = aal_claim if isinstance(aal_claim, str) and aal_claim else None
    structlog.contextvars.bind_contextvars(owner_id=str(owner_id))
    return owner_id, email, aal


async def resolve_principal(token: str, token_repo: TokenRepository) -> CurrentPrincipal:
    """Bildet einen Bearer-Token auf einen `CurrentPrincipal` ab.

    JWT-Pfad: `token_workspace_id=None`, Membership entscheidet spaeter.
    API-Token-Pfad: Workspace-Snapshot aus `api_token.workspace_id`.
    """
    if token.startswith(TOKEN_PREFIX):
        token_hash = hash_token(token)
        auth = await token_repo.fetch_auth_by_hash(token_hash)
        if auth is None:
            raise _credentials_error()
        try:
            await token_repo.touch_last_used(token_hash)
        except (asyncpg.PostgresError, OSError):
            logger.warning("last_used_at konnte nicht aktualisiert werden.")
        structlog.contextvars.bind_contextvars(owner_id=str(auth.owner_id))
        return CurrentPrincipal(
            user_id=auth.owner_id,
            token_workspace_id=auth.workspace_id,
            token_role=auth.role,
            token_agent_id=auth.agent_id,
        )
    user_id, email, aal = verify_supabase_jwt(token)
    return CurrentPrincipal(user_id=user_id, token_workspace_id=None, email=email, aal=aal)


async def get_current_principal(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)],
) -> CurrentPrincipal:
    """FastAPI-Dependency: `CurrentPrincipal` des authentifizierten Aufrufers.

    Fehlende Anmeldedaten und der JWT-Pfad kommen ohne Datenbank aus; nur die
    API-Token-Verifikation braucht den Pool. Der Pool wird daher erst hier —
    nach der Credential-Pruefung — geholt, sonst lieferte ein nicht
    initialisierter Pool ein 500 statt eines 401/503.
    """
    if credentials is None:
        raise _credentials_error()
    token = credentials.credentials
    if not token.startswith(TOKEN_PREFIX):
        user_id, email, aal = verify_supabase_jwt(token)
        return CurrentPrincipal(user_id=user_id, token_workspace_id=None, email=email, aal=aal)
    try:
        pool = get_pool()
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Datenbank nicht verfuegbar.",
        ) from exc
    return await resolve_principal(token, PgTokenRepository(pool))


async def get_current_user(
    principal: Annotated[CurrentPrincipal, Depends(get_current_principal)],
) -> UUID:
    """FastAPI-Dependency: owner_id des authentifizierten Aufrufers.

    Wird fuer Workspace-uebergreifende Endpunkte (`/v1/me`, `/v1/organizations`)
    verwendet. Fuer Workspace-scoped Endpunkte stattdessen
    `get_current_workspace`.
    """
    return principal.user_id


async def _load_agent_tool_policy(
    pool: asyncpg.Pool, workspace_id: UUID, agent_id: UUID | None
) -> AgentToolPolicy | None:
    """Laedt die Tool-Policy des an den Token gebundenen Agenten.

    `None`, wenn der Token ungebunden ist (`agent_id is None`) — dann gilt keine
    Pro-Agent-Restriktion. Der Agent ist ueber `(id, workspace_id)`
    workspace-gepinnt; verschwindet er (Race mit Delete), faellt der Token
    defensiv auf „keine Policy" zurueck statt zu brechen.
    """
    if agent_id is None:
        return None
    policy_json = await pool.fetchval(
        "SELECT tool_policy FROM agent WHERE id = $1 AND workspace_id = $2",
        agent_id,
        workspace_id,
    )
    if policy_json is None:
        return None
    return AgentToolPolicy.model_validate(policy_json)


async def get_current_workspace(
    workspace_id: Annotated[UUID, Path(...)],
    principal: Annotated[CurrentPrincipal, Depends(get_current_principal)],
) -> AsyncIterator["WorkspaceContext"]:
    """FastAPI-Dependency: `WorkspaceContext` fuer Workspace-scoped Endpunkte.

    Zwei getrennte Pfade (ADR-0023):
    - **API-Token:** Token-`workspace_id` muss exakt zum Path-Segment passen
      (Defense gegen Cross-Workspace-Token-Reuse); die Rolle ist die gepinnte
      Snapshot-Rolle aus `api_token.role`. Bewusst **kein**
      `workspace_member`-Lookup — ein gepinnter Token bleibt gueltig, bis er
      revoked wird, auch wenn der Ersteller spaeter herabgestuft/entfernt wird.
    - **JWT:** `workspace_member`-Lookup; nicht-Mitglied → 403. Rolle = die
      aktuelle Membership-Rolle.

    RLS-Choke-Point (Plan R1): nach der Autorisierung betritt diese Dependency
    `tenant_scope(workspace_id, org_id)` und reicht den `WorkspaceContext` per
    `yield` weiter. Solange der Endpunkt laeuft, traegt jede vom App-Pool
    gezogene Connection `app.current_tenant`/`app.current_org` — RLS isoliert
    den Mandanten als zweite Verteidigungslinie hinter den App-`WHERE`-Filtern.
    Der `org_id`-Lookup laeuft VOR dem Scope (workspace ist control-plane, ohne
    RLS lesbar).
    """
    try:
        pool = get_pool()
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Datenbank nicht verfuegbar.",
        ) from exc

    if principal.token_workspace_id is not None:
        if principal.token_workspace_id != workspace_id:
            # Cross-Workspace-Token-Reuse: der Token darf in diesem Workspace
            # ueberhaupt nicht agieren — fuer den Aufrufer endgueltig (`none`).
            raise ApiGateError(
                status=status.HTTP_403_FORBIDDEN,
                reason="forbidden_transition",
                actionable_by="none",
                detail="Token gehoert nicht zu diesem Workspace.",
            )
        if principal.token_role is None:
            # Defensiv: der Token-Pfad setzt `token_role` immer mit. Fehlt sie,
            # ist der Principal inkonsistent — kein stiller Voll-Zugriff.
            raise _credentials_error()
        # An einen Agenten gebundener Token: dessen Tool-Policy laden, damit
        # `require_capability` (Writes) und die Read-Services (Scoping) sie
        # durchsetzen. Der Agent ist workspace-gepinnt — kein Cross-WS-Leck.
        tool_policy = await _load_agent_tool_policy(pool, workspace_id, principal.token_agent_id)
        ctx = WorkspaceContext(
            workspace_id=workspace_id,
            user_id=principal.user_id,
            role=principal.token_role,
            is_api_token=True,
            agent_id=principal.token_agent_id,
            tool_policy=tool_policy,
        )
    else:
        role = await pool.fetchval(
            "SELECT role FROM workspace_member WHERE workspace_id = $1 AND user_id = $2",
            workspace_id,
            principal.user_id,
        )
        if role is None:
            # Kein Membership-Eintrag: der Aufrufer braucht eine Einladung/Rolle
            # in diesem Workspace — ein Mensch (Admin) muss ihn aufnehmen.
            raise ApiGateError(
                status=status.HTTP_403_FORBIDDEN,
                reason="insufficient_role",
                actionable_by="human",
                detail="Kein Zugriff auf diesen Workspace.",
            )
        ctx = WorkspaceContext(
            workspace_id=workspace_id,
            user_id=principal.user_id,
            role=WorkspaceRole(role),
            is_api_token=False,
            aal=principal.aal,
        )

    # Org des Workspace fuer `app.current_org` (org-scoped RLS auf
    # org_entitlement/mcp_usage). `workspace`/`organization` tragen keine RLS,
    # sind also auch ausserhalb des Scopes lesbar; None ⇒ org-GUC bleibt ungesetzt.
    # Zugleich der Soft-Delete-Gate (Track O): eine zur Loeschung vorgemerkte
    # Org (deleted_at gesetzt) sperrt den Zugriff auf alle ihre Workspaces.
    org_row = await pool.fetchrow(
        "SELECT o.id AS org_id, o.deleted_at "
        "FROM workspace w JOIN organization o ON o.id = w.org_id "
        "WHERE w.id = $1",
        workspace_id,
    )
    if org_row is not None and org_row["deleted_at"] is not None:
        raise ApiGateError(
            status=status.HTTP_403_FORBIDDEN,
            reason="domain_disabled",
            actionable_by="human",
            detail="Diese Organisation wurde zur Loeschung vorgemerkt.",
        )
    org_id: UUID | None = org_row["org_id"] if org_row is not None else None
    structlog.contextvars.bind_contextvars(workspace_id=str(workspace_id))
    async with tenant_scope(workspace_id, org_id):
        yield ctx

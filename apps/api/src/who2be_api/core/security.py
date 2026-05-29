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
from dataclasses import dataclass
from typing import Annotated, Literal
from uuid import UUID

import asyncpg
import jwt
import structlog
from fastapi import Depends, HTTPException, Path, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from who2be_api.core.config import get_settings
from who2be_api.core.db import get_pool
from who2be_api.repositories.token_repository import PgTokenRepository, TokenRepository

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
class TokenAuth:
    """Resolution-Ergebnis eines API-Tokens: Owner + Workspace-Snapshot."""

    owner_id: UUID
    workspace_id: UUID


@dataclass(frozen=True)
class CurrentPrincipal:
    """Authentifizierter Aufrufer.

    `token_workspace_id` ist nur fuer den API-Token-Pfad gesetzt — Tokens sind
    pro Workspace gepinnt. JWT-Aufrufer haben `None` und werden in
    `get_current_workspace` allein per Membership autorisiert.
    """

    user_id: UUID
    token_workspace_id: UUID | None


@dataclass(frozen=True)
class WorkspaceContext:
    """Workspace + User + Rolle des Aufrufers — Standard-Service-Argument.

    `is_api_token` ist True, wenn der Aufruf ueber einen `w2b_`-API-Token kam
    (MCP-Server). Services nutzen das Flag, um nur Active-Versionen
    zurueckzuliefern (Plan §2.1.D — Active-Filter im Repo).
    """

    workspace_id: UUID
    user_id: UUID
    role: Literal["admin", "editor", "viewer"]
    is_api_token: bool = False


# Rollen-Hierarchie admin>editor>viewer (ADR-0023). `require_role` ist der
# Stub fuer das RBAC-Gate aus Plan §2.3.B — er erzwingt bereits ein
# Mindest-Level (admin-only fuer Member-/Invitation-Verwaltung), und Prompt A
# baut darauf die volle Permission-Matrix auf.
_ROLE_RANK: dict[str, int] = {"viewer": 0, "editor": 1, "admin": 2}


def require_role(ctx: "WorkspaceContext", minimum: Literal["admin", "editor", "viewer"]) -> None:
    """Wirft 403, wenn die Rolle im `ctx` unter `minimum` liegt."""
    if _ROLE_RANK[ctx.role] < _ROLE_RANK[minimum]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Rolle '{minimum}' erforderlich.",
        )


def verify_supabase_jwt(token: str) -> UUID:
    """Verifiziert ein Supabase-JWT lokal (HS256) und liest `sub` als owner_id."""
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
    structlog.contextvars.bind_contextvars(owner_id=str(owner_id))
    return owner_id


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
        return CurrentPrincipal(user_id=auth.owner_id, token_workspace_id=auth.workspace_id)
    return CurrentPrincipal(user_id=verify_supabase_jwt(token), token_workspace_id=None)


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
        return CurrentPrincipal(user_id=verify_supabase_jwt(token), token_workspace_id=None)
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


async def get_current_workspace(
    workspace_id: Annotated[UUID, Path(...)],
    principal: Annotated[CurrentPrincipal, Depends(get_current_principal)],
) -> "WorkspaceContext":
    """FastAPI-Dependency: `WorkspaceContext` fuer Workspace-scoped Endpunkte.

    Pruefung in zwei Stufen:
    1. API-Token-Snapshot: Token-`workspace_id` muss exakt zum Path-Segment
       passen — Defense gegen Cross-Workspace-Token-Reuse.
    2. Membership: `workspace_member`-Lookup; nicht-Mitglied → 403.
    """
    if principal.token_workspace_id is not None and principal.token_workspace_id != workspace_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Token gehoert nicht zu diesem Workspace.",
        )
    try:
        pool = get_pool()
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Datenbank nicht verfuegbar.",
        ) from exc
    role = await pool.fetchval(
        "SELECT role FROM workspace_member WHERE workspace_id = $1 AND user_id = $2",
        workspace_id,
        principal.user_id,
    )
    if role is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Kein Zugriff auf diesen Workspace.",
        )
    structlog.contextvars.bind_contextvars(workspace_id=str(workspace_id))
    return WorkspaceContext(
        workspace_id=workspace_id,
        user_id=principal.user_id,
        role=role,
        is_api_token=principal.token_workspace_id is not None,
    )

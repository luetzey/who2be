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
from who2be_api.core.tenancy import tenant_scope
from who2be_api.repositories.token_repository import PgTokenRepository, TokenRepository
from who2be_models import WorkspaceRole

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
    """

    user_id: UUID
    token_workspace_id: UUID | None
    token_role: WorkspaceRole | None = None
    email: str | None = None


@dataclass(frozen=True)
class WorkspaceContext:
    """Workspace + User + Rolle des Aufrufers — Standard-Service-Argument.

    `is_api_token` ist True, wenn der Aufruf ueber einen `w2b_`-API-Token kam
    (MCP-Server). Services nutzen das Flag, um nur Active-Versionen
    zurueckzuliefern (Plan §2.1.D — Active-Filter im Repo).

    `role` ist die effektive Rolle (Membership-Rolle im JWT-Pfad,
    Snapshot-Rolle im Token-Pfad) und Basis fuer `require_role` (ADR-0023).
    """

    workspace_id: UUID
    user_id: UUID
    role: WorkspaceRole
    is_api_token: bool = False


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


def require_role(ctx: WorkspaceContext, minimum: WorkspaceRole) -> None:
    """Wirft 403, wenn die Kontext-Rolle `minimum` nicht erreicht (ADR-0023)."""
    if not role_satisfies(ctx.role, minimum):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Diese Aktion erfordert mindestens die Rolle '{minimum.value}'.",
        )


def verify_supabase_jwt(token: str) -> tuple[UUID, str | None]:
    """Verifiziert ein Supabase-JWT lokal (HS256) und liest `sub` + optional `email`.

    Rueckgabe: `(owner_id, email_or_none)`. Der Email-Claim ist optional —
    aelteren Test-JWTs fehlt er; produktive Supabase-JWTs tragen ihn aber
    immer mit. Wir verwenden ihn fuer die Email-Mismatch-Pruefung beim
    Invitation-Accept (Phase 3-D).
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
    structlog.contextvars.bind_contextvars(owner_id=str(owner_id))
    return owner_id, email


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
        )
    user_id, email = verify_supabase_jwt(token)
    return CurrentPrincipal(user_id=user_id, token_workspace_id=None, email=email)


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
        user_id, email = verify_supabase_jwt(token)
        return CurrentPrincipal(user_id=user_id, token_workspace_id=None, email=email)
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
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Token gehoert nicht zu diesem Workspace.",
            )
        if principal.token_role is None:
            # Defensiv: der Token-Pfad setzt `token_role` immer mit. Fehlt sie,
            # ist der Principal inkonsistent — kein stiller Voll-Zugriff.
            raise _credentials_error()
        ctx = WorkspaceContext(
            workspace_id=workspace_id,
            user_id=principal.user_id,
            role=principal.token_role,
            is_api_token=True,
        )
    else:
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
        ctx = WorkspaceContext(
            workspace_id=workspace_id,
            user_id=principal.user_id,
            role=WorkspaceRole(role),
            is_api_token=False,
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
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Diese Organisation wurde zur Loeschung vorgemerkt.",
        )
    org_id: UUID | None = org_row["org_id"] if org_row is not None else None
    structlog.contextvars.bind_contextvars(workspace_id=str(workspace_id))
    async with tenant_scope(workspace_id, org_id):
        yield ctx

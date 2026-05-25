"""Authentifizierung: Supabase-JWT und API-Token (ADR-0006).

Zwei Wege, ein `owner_id`-Kontext. Die Dependency `get_current_user` erkennt
den Weg am Token-Praefix `w2b_` und liefert in beiden Faellen die `owner_id`.
"""

import hashlib
import logging
import secrets
from typing import Annotated
from uuid import UUID

import asyncpg
import jwt
import structlog
from fastapi import Depends, HTTPException, status
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


async def resolve_owner(token: str, token_repo: TokenRepository) -> UUID:
    """Bildet einen Bearer-Token auf eine owner_id ab (ADR-0006-Dispatch)."""
    if token.startswith(TOKEN_PREFIX):
        token_hash = hash_token(token)
        owner_id = await token_repo.fetch_owner_by_hash(token_hash)
        if owner_id is None:
            raise _credentials_error()
        try:
            await token_repo.touch_last_used(token_hash)
        except (asyncpg.PostgresError, OSError):
            logger.warning("last_used_at konnte nicht aktualisiert werden.")
        structlog.contextvars.bind_contextvars(owner_id=str(owner_id))
        return owner_id
    return verify_supabase_jwt(token)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)],
) -> UUID:
    """FastAPI-Dependency: owner_id des authentifizierten Aufrufers.

    Fehlende Anmeldedaten und der JWT-Pfad kommen ohne Datenbank aus; nur die
    API-Token-Verifikation braucht den Pool. Der Pool wird daher erst hier —
    nach der Credential-Pruefung — geholt, sonst lieferte ein nicht
    initialisierter Pool ein 500 statt eines 401/503.
    """
    if credentials is None:
        raise _credentials_error()
    token = credentials.credentials
    if not token.startswith(TOKEN_PREFIX):
        return verify_supabase_jwt(token)
    try:
        pool = get_pool()
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Datenbank nicht verfuegbar.",
        ) from exc
    return await resolve_owner(token, PgTokenRepository(pool))

"""OAuth-2.1-Authorization-Server-Endpunkte (Remote-MCP-Connector).

Drei Router:
- `metadata_router` (`/.well-known`): RFC-8414-AS-Metadaten (anonym, statisch).
- `router` (`/oauth`): `register` (DCR), `authorize` (→ Web-Consent),
  `consent` (User-eingeloggt → Auth-Code), `token` (Code-/Refresh-Grant).

Der `authorize`-Endpunkt ist der Open-Redirect-Choke-Point: ungueltiger Client /
nicht registrierte redirect_uri ⇒ 400 OHNE Redirect. `token` ist form-encoded
(OAuth-konform) und liefert `Cache-Control: no-store`.
"""

from typing import Annotated

import asyncpg
from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse, RedirectResponse

from who2be_api.core.config import get_settings
from who2be_api.core.db import get_pool
from who2be_api.core.rate_limit import limiter, write_limit
from who2be_api.core.security import CurrentPrincipal, get_current_principal
from who2be_api.repositories.audit_log_repository import PgAuditLogRepository
from who2be_api.repositories.oauth_repository import PgOAuthRepository
from who2be_api.repositories.token_repository import PgTokenRepository
from who2be_api.services.audit_service import AuditService
from who2be_api.services.oauth_service import OAuthError, OAuthService
from who2be_models import (
    OAuthClientRegistered,
    OAuthClientRegistration,
    OAuthConsentApprove,
    OAuthConsentResult,
    OAuthTokenResponse,
)

router = APIRouter(prefix="/oauth", tags=["oauth"])
metadata_router = APIRouter(tags=["oauth"])

_NO_STORE = {"Cache-Control": "no-store", "Pragma": "no-cache"}


def get_oauth_service(
    pool: Annotated[asyncpg.Pool, Depends(get_pool)],
) -> OAuthService:
    return OAuthService(
        oauth_repo=PgOAuthRepository(pool),
        token_repo=PgTokenRepository(pool),
        pool=pool,
        audit=AuditService(PgAuditLogRepository()),
    )


Service = Annotated[OAuthService, Depends(get_oauth_service)]
Principal = Annotated[CurrentPrincipal, Depends(get_current_principal)]


def _error_response(exc: OAuthError) -> JSONResponse:
    body: dict[str, str] = {"error": exc.error}
    if exc.description:
        body["error_description"] = exc.description
    return JSONResponse(status_code=exc.status_code, content=body, headers=_NO_STORE)


@metadata_router.get("/.well-known/oauth-authorization-server")
async def authorization_server_metadata() -> dict[str, object]:
    """RFC-8414-Metadaten — der LLM-Client entdeckt darueber alle Endpunkte."""
    settings = get_settings()
    issuer = settings.oauth_issuer_url.rstrip("/")
    return {
        "issuer": issuer,
        "authorization_endpoint": f"{issuer}/oauth/authorize",
        "token_endpoint": f"{issuer}/oauth/token",
        "registration_endpoint": f"{issuer}/oauth/register",
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code", "refresh_token"],
        "code_challenge_methods_supported": ["S256"],
        "token_endpoint_auth_methods_supported": ["none"],
    }


@router.post("/register", status_code=status.HTTP_201_CREATED)
@limiter.limit(write_limit)
async def register_client(
    request: Request, data: OAuthClientRegistration, service: Service
) -> OAuthClientRegistered:
    """Dynamic Client Registration (RFC 7591) — public client (PKCE)."""
    try:
        return await service.register_client(data)
    except OAuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.error) from exc


@router.get("/authorize", response_model=None)
@limiter.limit(write_limit)
async def authorize(
    request: Request,
    service: Service,
    response_type: Annotated[str, Query()],
    client_id: Annotated[str, Query()],
    redirect_uri: Annotated[str, Query()],
    code_challenge: Annotated[str, Query()],
    resource: Annotated[str, Query()],
    code_challenge_method: Annotated[str, Query()] = "S256",
    state: Annotated[str | None, Query()] = None,
    scope: Annotated[str | None, Query()] = None,
) -> RedirectResponse | JSONResponse:
    """Validiert den Request und leitet auf die Web-Consent-Seite weiter.

    Bei ungueltigem Client / nicht registrierter redirect_uri: 400 OHNE Redirect.
    """
    try:
        consent_url = await service.authorize_to_consent_url(
            client_id=client_id,
            redirect_uri=redirect_uri,
            response_type=response_type,
            code_challenge=code_challenge,
            code_challenge_method=code_challenge_method,
            state=state,
            resource=resource,
            scope=scope,
        )
    except OAuthError as exc:
        return _error_response(exc)
    return RedirectResponse(consent_url, status_code=status.HTTP_302_FOUND)


@router.post("/consent")
@limiter.limit(write_limit)
async def consent(
    request: Request, data: OAuthConsentApprove, principal: Principal, service: Service
) -> OAuthConsentResult:
    """Consent-Submit der eingeloggten Web-Session → Redirect-URL zum Client."""
    try:
        redirect = await service.consent(
            user_id=principal.user_id,
            request_blob=data.request,
            agent_id=data.agent_id,
            approve=data.approve,
        )
    except OAuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.error) from exc
    return OAuthConsentResult(redirect=redirect)


@router.post("/token", response_model=None)
@limiter.limit(write_limit)
async def token(
    request: Request,
    service: Service,
    grant_type: Annotated[str, Form()],
    client_id: Annotated[str, Form()],
    code: Annotated[str | None, Form()] = None,
    redirect_uri: Annotated[str | None, Form()] = None,
    code_verifier: Annotated[str | None, Form()] = None,
    refresh_token: Annotated[str | None, Form()] = None,
) -> JSONResponse:
    """Token-Endpunkt (form-encoded). Zwei Grants: code + refresh."""
    try:
        if grant_type == "authorization_code":
            if not (code and redirect_uri and code_verifier):
                raise OAuthError("invalid_request", "code/redirect_uri/code_verifier fehlen.")
            result: OAuthTokenResponse = await service.exchange_code(
                code=code,
                redirect_uri=redirect_uri,
                client_id=client_id,
                code_verifier=code_verifier,
            )
        elif grant_type == "refresh_token":
            if not refresh_token:
                raise OAuthError("invalid_request", "refresh_token fehlt.")
            result = await service.exchange_refresh(refresh_token, client_id)
        else:
            raise OAuthError("unsupported_grant_type", f"Grant {grant_type} nicht unterstuetzt.")
    except OAuthError as exc:
        return _error_response(exc)
    return JSONResponse(content=result.model_dump(exclude_none=True), headers=_NO_STORE)

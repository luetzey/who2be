"""Pydantic-Modelle fuer den OAuth-Remote-MCP-Connector (Authorization Server).

Who2Be agiert als OAuth-2.1-Authorization-Server (MCP-Authorization-Spec): ein
LLM-Client registriert sich dynamisch (DCR, RFC 7591), schickt den User durch
den Authorize/Consent-Flow und tauscht den Code gegen einen agent-gebundenen
Access-Token (+ Refresh-Token). Der Access-Token ist ein gewoehnlicher
`w2b_`-API-Token mit gesetztem `expires_at`.
"""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class OAuthClientRegistration(BaseModel):
    """Dynamic-Client-Registration-Request (RFC 7591). Public client (PKCE)."""

    model_config = ConfigDict(extra="forbid")

    redirect_uris: list[str] = Field(min_length=1, max_length=8)
    client_name: str | None = Field(default=None, max_length=200)
    token_endpoint_auth_method: str = "none"


class OAuthClientRegistered(BaseModel):
    """DCR-Response — der ausgegebene `client_id` plus Echo der Metadaten."""

    model_config = ConfigDict(extra="forbid")

    client_id: str
    client_name: str | None = None
    redirect_uris: list[str]
    token_endpoint_auth_method: str
    grant_types: list[str]


class OAuthConsentApprove(BaseModel):
    """Consent-Submit der Web-Seite.

    `request` ist der signierte (HMAC) Authorize-Request-Blob, den
    `GET /oauth/authorize` erzeugt hat — er traegt client_id, redirect_uri,
    code_challenge, state, resource, scope manipulationssicher.
    """

    model_config = ConfigDict(extra="forbid")

    request: str
    agent_id: UUID
    approve: bool


class OAuthConsentResult(BaseModel):
    """Antwort des Consent-Endpunkts: die Redirect-URL zurueck zum Client."""

    model_config = ConfigDict(extra="forbid")

    redirect: str


class OAuthTokenResponse(BaseModel):
    """Token-Endpunkt-Antwort (OAuth 2.1). `expires_in` in Sekunden."""

    model_config = ConfigDict(extra="forbid")

    access_token: str
    token_type: str = "bearer"
    expires_in: int
    refresh_token: str
    scope: str | None = None


class OAuthError(BaseModel):
    """OAuth-Fehlerobjekt (`error`, optional `error_description`)."""

    model_config = ConfigDict(extra="forbid")

    error: str
    error_description: str | None = None

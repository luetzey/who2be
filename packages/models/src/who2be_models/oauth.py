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
    """Dynamic-Client-Registration-Request (RFC 7591). Public client (PKCE).

    `extra="ignore"` (nicht `forbid`): echte DCR-Clients (Claude/ChatGPT) senden
    zusaetzliche Standard-Metadaten (`grant_types`, `response_types`, `scope`,
    `client_uri`, …). RFC 7591 schreibt vor, nicht unterstuetzte Metadaten zu
    IGNORIEREN — `forbid` wuerde die Registrierung mit 422 brechen.
    """

    model_config = ConfigDict(extra="ignore")

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


class OAuthConsentPreviewRequest(BaseModel):
    """Anfrage der Consent-Seite: welcher Agent haengt an diesem Request-Blob?

    Traegt ausschliesslich den signierten Authorize-Request-Blob — bewusst KEIN
    freier `agent_id`-Parameter. Der Trust-Anker ist die HMAC-Signatur; ein
    Endpunkt, der eine beliebige Agent-UUID aufloest, waere ein IDOR-Vektor.
    """

    model_config = ConfigDict(extra="forbid")

    request: str


class OAuthConsentAgent(BaseModel):
    """Lesbare Identitaet des gebundenen Agenten (Name + Workspace-Name)."""

    model_config = ConfigDict(extra="forbid")

    id: UUID
    name: str
    workspace_id: UUID
    workspace_name: str


class OAuthConsentPreview(BaseModel):
    """Reine Anzeige-Vorschau des Consent — trifft KEINE Autorisierungs-Entscheidung.

    `locked` sagt, ob der signierte Blob einen Agent-Hint traegt (Hard-Lock:
    genau dieser Agent wird gebunden, die Auswahl des Users ist irrelevant).
    `agent` ist `null`, wenn der Agent nicht aufloesbar ist — bewusst
    ununterscheidbar fuer „existiert nicht" und „liegt in keinem Workspace des
    Users", damit der Endpunkt kein Existenz-Orakel wird. Das 403 faellt erst
    am `POST /oauth/consent`, wo die Entscheidung getroffen wird.
    """

    model_config = ConfigDict(extra="forbid")

    locked: bool
    agent: OAuthConsentAgent | None = None


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

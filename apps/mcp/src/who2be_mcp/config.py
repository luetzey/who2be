"""Konfiguration des Who2Be-MCP-Servers.

Genau eine Quelle fuer alle Einstellungen: Umgebungsvariablen bzw. `.env`.
Die Variablen tragen den Prefix `WHO2BE_` (z. B. `WHO2BE_API_TOKEN`).
"""

from functools import lru_cache
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="WHO2BE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    api_base_url: str = "http://localhost:8000"
    api_token: str = ""
    # Optional explizit gepinnter Workspace; sonst Bootstrap via `/v1/me`.
    # NUR fuer stdio/Single-Tenant — s. `_reject_workspace_pin_on_http`.
    workspace_id: str = ""
    # `json` fuer Prod-Aggregation, `console` fuer lesbares Dev-Tail (ADR-0007).
    log_format: Literal["json", "console"] = "json"
    # Transport-Switch — Default `stdio` (Claude Desktop / Cursor local).
    # `http` exponiert den FastMCP-Server als ASGI-App (Streamable-HTTP) auf
    # {http_host}:{http_port}{http_path} — fuer Cloud-Connectoren, Remote-Clients
    # und Hetzner-Deployment hinter Caddy. ADR-0034.
    transport: Literal["stdio", "http"] = "stdio"
    http_host: str = "0.0.0.0"
    http_port: int = 8765
    http_path: str = "/mcp"
    # OAuth-Resource-Server (ADR-0034-Folge, nur HTTP-Transport):
    # `oauth_issuer_url` = die Who2Be-API als Authorization-Server (PRM-Pointer);
    # `mcp_public_url` = oeffentliche ORIGIN dieses MCP-Servers (ohne `{http_path}`;
    # FastMCP haengt den Mount-Pfad an → die advertisierte Resource wird
    # `{mcp_public_url}{http_path}` und muss `MCP_RESOURCE_URL` der API gleichen).
    oauth_issuer_url: str = "http://localhost:8000"
    mcp_public_url: str = "http://127.0.0.1:8765"

    @model_validator(mode="after")
    def _reject_workspace_pin_on_http(self) -> "Settings":
        """`WHO2BE_WORKSPACE_ID` ist unter `transport=http` ein Konfig-Fehler.

        Streamable-HTTP ist multi-tenant: ein Prozess bedient alle Bearer
        (ADR-0034). Ein gepinnter Workspace gewinnt aber gegen *jeden* Token —
        fremde Credentials wuerden in einen fremden Workspace geschickt. Der
        Pin ist eine stdio-Bequemlichkeit, keine Server-Einstellung, deshalb
        beim Start abbrechen statt die Tenant-Grenze still zu unterlaufen.
        """
        if self.transport == "http" and self.workspace_id:
            raise ValueError(
                "WHO2BE_WORKSPACE_ID ist mit WHO2BE_TRANSPORT=http nicht erlaubt: "
                "der HTTP-Transport ist multi-tenant, ein gepinnter Workspace wuerde "
                "fuer jeden Bearer gelten. Pin entfernen — der Workspace kommt aus "
                "dem Token."
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()

"""Konfiguration des Who2Be-MCP-Servers.

Genau eine Quelle fuer alle Einstellungen: Umgebungsvariablen bzw. `.env`.
Die Variablen tragen den Prefix `WHO2BE_` (z. B. `WHO2BE_API_TOKEN`).
"""

from functools import lru_cache
from typing import Literal

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


@lru_cache
def get_settings() -> Settings:
    return Settings()

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
    # `json` fuer Prod-Aggregation, `console` fuer lesbares Dev-Tail (ADR-0007).
    log_format: Literal["json", "console"] = "json"


@lru_cache
def get_settings() -> Settings:
    return Settings()

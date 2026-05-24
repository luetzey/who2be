"""Zentrale Konfiguration der Who2Be-API.

Genau eine Quelle fuer alle Einstellungen: Umgebungsvariablen bzw.
`.env`. `cors_origins` ist eine Liste, damit MS-2 (Hetzner) mehrere
Origins (App-Domain + ggf. Preview-Deployments) zulassen kann; pydantic-
settings parst CSV-Strings automatisch (`CORS_ORIGINS=a,b`).
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    database_url: str = "postgresql://postgres:postgres@localhost:5432/who2be"
    jwt_secret: str = ""
    supabase_url: str = ""
    cors_origins: list[str] = ["http://localhost:5173"]


@lru_cache
def get_settings() -> Settings:
    return Settings()

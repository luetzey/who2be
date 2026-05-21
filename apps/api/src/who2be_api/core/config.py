"""Zentrale Konfiguration der Who2Be-API.

Genau eine Quelle fuer alle Einstellungen: Umgebungsvariablen bzw. `.env`.
`jwt_secret`, `supabase_url` und `cors_origin` werden erst in spaeteren Phasen
(Auth, Web) genutzt und sind bewusst schon hier verankert.
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
    cors_origin: str = "http://localhost:5173"


@lru_cache
def get_settings() -> Settings:
    return Settings()

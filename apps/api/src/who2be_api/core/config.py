"""Zentrale Konfiguration der Who2Be-API.

Genau eine Quelle fuer alle Einstellungen: Umgebungsvariablen bzw.
`.env`. `cors_origins` ist eine Liste, damit MS-2 (Hetzner) mehrere
Origins (App-Domain + ggf. Preview-Deployments) zulassen kann;
`CORS_ORIGINS=a,b` (CSV) und `CORS_ORIGINS=["a","b"]` (JSON) werden
beide akzeptiert.
"""

import json
from functools import lru_cache
from typing import Literal

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _split_origins(raw: str) -> list[str]:
    """Akzeptiert CSV (`a,b`) und JSON-Liste (`["a","b"]`)."""
    stripped = raw.strip()
    if not stripped:
        return []
    if stripped.startswith("["):
        decoded = json.loads(stripped)
        if not isinstance(decoded, list):
            raise ValueError("CORS_ORIGINS-JSON muss eine Liste sein.")
        return [str(item) for item in decoded]
    return [part.strip() for part in stripped.split(",") if part.strip()]


class Settings(BaseSettings):
    """Quelle der Wahrheit fuer alle API-Einstellungen.

    `cors_origins` ist im Env eine **Zeichenkette** (CSV oder JSON-Liste),
    weil pydantic-settings komplexe Typen vor den Validatoren JSON-decoded —
    eine direkte `list[str]`-Annotation wuerde CSV nicht akzeptieren. Konsumenten
    rufen `settings.cors_origins` und bekommen die geparste Liste.
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql://postgres:postgres@localhost:5432/who2be"
    jwt_secret: str = ""
    supabase_url: str = ""
    # Service-Role-Key fuer GoTrue-Admin-Calls (Invitation-Mail via
    # `POST /auth/v1/invite`). Leer ⇒ Mail-Versand wird uebersprungen (Token
    # kommt trotzdem im 201-Body zurueck, manuell teilbar).
    supabase_service_key: str = ""
    # Basis-URL der Web-App fuer den Accept-Link in der Einladungs-Mail
    # (`{web_base_url}/invitations/{token}/accept`).
    web_base_url: str = "http://localhost:5173"
    cors_origins_raw: str = Field(
        default="http://localhost:5173",
        validation_alias=AliasChoices("CORS_ORIGINS", "cors_origins"),
    )
    # Pro Token-Hash bzw. IP. Slowapi-Limit-Callable liest dieses Feld zur Laufzeit,
    # damit Tests via Settings-Override auf einen niedrigen Wert druecken koennen.
    rate_limit_write: str = "30/minute"
    # `json` fuer Prod-Aggregation, `console` fuer lesbares Dev-Tail (ADR-0007).
    log_format: Literal["json", "console"] = "json"
    # F-13 / H5: /docs, /redoc, /openapi.json sind in Prod default aus. true nur fuer
    # lokales Debugging — Caddy hat keinen Auth-Layer davor.
    docs_public: bool = Field(
        default=False,
        validation_alias=AliasChoices("WHO2BE_DOCS_PUBLIC", "docs_public"),
    )

    @property
    def cors_origins(self) -> list[str]:
        return _split_origins(self.cors_origins_raw)


@lru_cache
def get_settings() -> Settings:
    return Settings()

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
    # RLS-Cloud-Haertung (Plan R1/R2): die App verbindet im Cloud-Betrieb als
    # nicht-privilegierte Rolle `who2be_app` (NOSUPERUSER, NOBYPASSRLS) ueber
    # diese URL; `DATABASE_URL` bleibt der Owner und faehrt nur die Migrationen
    # (`who2be-migrate`). Leer ⇒ Fallback auf `DATABASE_URL` (On-Prem/Dev: die
    # App laeuft als Owner, der RLS ohnehin umgeht — kein App-SQL-Unterschied).
    app_database_url: str = Field(
        default="",
        validation_alias=AliasChoices("APP_DATABASE_URL", "app_database_url"),
    )
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
    # Track D — Editionen/Entitlements (Notion-Vault: Deployment-/Licensing-Standards).
    # Ein Build, ein Image; der Unterschied Cloud vs. On-Prem liegt allein in dieser
    # Runtime-Config (12-Factor III). Default `onprem` ⇒ OSS-sicher (unbegrenztes
    # `OSS_ENTITLEMENT`, kein Billing). Nur `cloud` aktiviert Limits + Webhook-Adapter.
    edition: Literal["cloud", "onprem"] = Field(
        default="onprem",
        validation_alias=AliasChoices("WHO2BE_EDITION", "edition"),
    )
    # On-Prem-Adapter: signierte Lizenzdatei (Ed25519), offline mit `K_pub` verifiziert.
    # Leer ⇒ reines OSS (unbegrenzt). NIE der Private-Key — nur der Lizenz-Token.
    license_key: str = Field(
        default="",
        validation_alias=AliasChoices("WHO2BE_LICENSE_KEY", "license_key"),
    )
    # Cloud-Adapter: Shared Secret des Zahlungsanbieters (Stripe/Mollie) fuer die
    # Webhook-Signaturpruefung. Leer ⇒ Webhook lehnt jede Lieferung ab (fail closed).
    billing_webhook_secret: str = Field(
        default="",
        validation_alias=AliasChoices("WHO2BE_BILLING_WEBHOOK_SECRET", "billing_webhook_secret"),
    )
    # Mollie-Pull-Adapter (Plan §3.2): API-Key fuer den serverseitigen Fetch nach
    # dem Webhook-Ping (Mollie liefert nur die `id`, kein signierter Body). Leer ⇒
    # Mollie-Checkout/-Webhook sind nicht verfuegbar (503). NIE ein Test-Key in Prod.
    mollie_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("MOLLIE_API_KEY", "mollie_api_key"),
    )
    # Optionales Zusatz-Secret fuer den Mollie-Webhook-Pfad (`?token=…`,
    # konstant-zeitlich verglichen) — Mollie selbst signiert nicht. Leer ⇒ kein
    # Token-Gate (die Pull-Verifikation bleibt die Hauptsicherung).
    mollie_webhook_secret: str = Field(
        default="",
        validation_alias=AliasChoices("MOLLIE_WEBHOOK_SECRET", "mollie_webhook_secret"),
    )
    # Absolute, oeffentlich erreichbare URL des Mollie-Webhooks (Mollie verlangt
    # https und akzeptiert kein localhost). Leer ⇒ Zahlungen/Subscriptions werden
    # ohne `webhookUrl` angelegt (lokales Dev / Tests).
    mollie_webhook_url: str = Field(
        default="",
        validation_alias=AliasChoices("MOLLIE_WEBHOOK_URL", "mollie_webhook_url"),
    )
    # On-Prem-Bootstrap: beim ersten Boot ohne Tenant wird fuer diese Email ein
    # Admin + Personal-Org + Workspace deterministisch geseedet.
    bootstrap_admin_email: str = Field(
        default="",
        validation_alias=AliasChoices("WHO2BE_BOOTSTRAP_ADMIN_EMAIL", "bootstrap_admin_email"),
    )

    @property
    def cors_origins(self) -> list[str]:
        return _split_origins(self.cors_origins_raw)

    @property
    def effective_app_database_url(self) -> str:
        """App-Role-Connection fuer den Laufzeit-Pool.

        Cloud: `APP_DATABASE_URL` (Rolle `who2be_app`). On-Prem/Dev: faellt auf
        `DATABASE_URL` zurueck (App laeuft als Owner, RLS-Bypass — Plan R2).
        """
        return self.app_database_url or self.database_url


@lru_cache
def get_settings() -> Settings:
    return Settings()

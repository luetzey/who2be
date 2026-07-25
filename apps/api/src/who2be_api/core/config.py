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
    # --- OAuth-Remote-MCP-Connector (Authorization Server, ADR-0034-Folge) ---
    # `oauth_issuer_url`: oeffentliche Basis-URL der API (= OAuth-Issuer, z.B.
    # https://api.<domain>). `oauth_consent_url`: die Web-Consent-Seite.
    # `mcp_resource_url`: kanonische MCP-Resource-URL (RFC 8707 audience).
    oauth_issuer_url: str = Field(
        default="http://localhost:8000",
        validation_alias=AliasChoices("OAUTH_ISSUER_URL", "oauth_issuer_url"),
    )
    oauth_consent_url: str = Field(
        default="http://localhost:5173/oauth/consent",
        validation_alias=AliasChoices("OAUTH_CONSENT_URL", "oauth_consent_url"),
    )
    mcp_resource_url: str = Field(
        default="http://127.0.0.1:8765/mcp",
        validation_alias=AliasChoices("MCP_RESOURCE_URL", "mcp_resource_url"),
    )
    cors_origins_raw: str = Field(
        default="http://localhost:5173",
        validation_alias=AliasChoices("CORS_ORIGINS", "cors_origins"),
    )
    # Pro Token-Hash bzw. IP. Slowapi-Limit-Callable liest dieses Feld zur Laufzeit,
    # damit Tests via Settings-Override auf einen niedrigen Wert druecken koennen.
    rate_limit_write: str = "30/minute"
    # Plan CL2 / §3.1 — pluggable Rate-Limit-Storage. Default `memory://` ⇒
    # Single-Process, Verhalten unveraendert. `redis://host:port` aktiviert ein
    # geteiltes Backend (slowapi + Per-Token-Ceiling), damit mehrere API-Replicas
    # dasselbe Fenster sehen. Der Wert wird 1:1 an `storage_from_string` (limits)
    # bzw. an den slowapi-`Limiter` durchgereicht.
    rate_limit_storage_uri: str = Field(
        default="memory://",
        validation_alias=AliasChoices("RATE_LIMIT_STORAGE_URI", "rate_limit_storage_uri"),
    )
    # `json` fuer Prod-Aggregation, `console` fuer lesbares Dev-Tail (ADR-0007).
    log_format: Literal["json", "console"] = "json"
    # F-13 / H5: /docs, /redoc, /openapi.json sind in Prod default aus. true nur fuer
    # lokales Debugging — Caddy hat keinen Auth-Layer davor.
    docs_public: bool = Field(
        default=False,
        validation_alias=AliasChoices("WHO2BE_DOCS_PUBLIC", "docs_public"),
    )
    # Track D — Editionen/Entitlements (interne Deployment-/Licensing-Standards).
    # Ein Codebase, zwei Build-Profile (ADR-0029): die Edition-Weiche liest diese
    # Runtime-Config, aber die Artefakte unterscheiden sich physisch um das
    # Billing-Paket (`who2be-billing` nur im Cloud-Build). Default `onprem` ⇒
    # OSS-sicher (unbegrenztes `OSS_ENTITLEMENT`, kein Billing). Nur `cloud`
    # aktiviert Limits + Webhook-Adapter.
    edition: Literal["cloud", "onprem"] = Field(
        default="onprem",
        validation_alias=AliasChoices("WHO2BE_EDITION", "edition"),
    )
    # Semantische Suche (ADR-0046). Default AUS: Embeddings sind additiv, und
    # eine Installation ohne die optionale Dependency-Gruppe `embeddings` soll
    # nicht bei jedem Start in einen Adapter-Fehler laufen. An ⇒ Vektoren
    # werden best-effort erzeugt; fehlt der Adapter trotzdem, bleibt die Suche
    # im Volltext-Modus (fail-soft, siehe embeddings/service.py).
    embeddings_enabled: bool = Field(
        default=False,
        validation_alias=AliasChoices("WHO2BE_EMBEDDINGS_ENABLED", "embeddings_enabled"),
    )
    # Modell des lokalen Adapters. Muss 384-dimensionale Vektoren liefern
    # (Spaltentyp in Migration 0071) und sollte MULTILINGUAL sein — der
    # Hauptgewinn ist, dass eine deutsche Anfrage englischen Inhalt findet.
    embedding_model: str = Field(
        default="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        validation_alias=AliasChoices("WHO2BE_EMBEDDING_MODEL", "embedding_model"),
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
    # Dunning-Grace bei fehlgeschlagener Folgezahlung (Plan §3.2): so viele Tage
    # bleibt der gebuchte Tier nach einem fehlgeschlagenen Recurring-Payment aktiv
    # (Banner via `grace_until`), bevor das Entitlement abgelaufen ist.
    mollie_grace_days: int = Field(
        default=7,
        ge=0,
        validation_alias=AliasChoices("MOLLIE_GRACE_DAYS", "mollie_grace_days"),
    )
    # On-Prem-Bootstrap: beim ersten Boot ohne Tenant wird fuer diese Email ein
    # Admin + Personal-Org + Workspace deterministisch geseedet.
    bootstrap_admin_email: str = Field(
        default="",
        validation_alias=AliasChoices("WHO2BE_BOOTSTRAP_ADMIN_EMAIL", "bootstrap_admin_email"),
    )
    # MFA-Haertung On-Prem (SEC-1, Standards-Review 2026-07-08): `require_aal2`
    # laesst On-Prem/Dev-JWTs OHNE `aal`-Claim (Legacy-/Magic-Link-/Test-Tokens)
    # per Default durch (fail-open, nur mit Warn-Log `aal_missing_onprem`).
    # true ⇒ auch On-Prem wird ein fehlender Claim hart abgelehnt (fail-closed
    # wie in der Cloud). Default false = bisheriges Verhalten.
    require_mfa_onprem: bool = Field(
        default=False,
        validation_alias=AliasChoices("WHO2BE_REQUIRE_MFA_ONPREM", "require_mfa_onprem"),
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

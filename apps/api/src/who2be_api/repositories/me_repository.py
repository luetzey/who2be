"""Persistenz fuer `GET /v1/me` (TASK-301).

Aggregiert alle Organizations + Workspaces, in denen der User Member ist,
plus die jeweilige Rolle. Default-Workspace = aelteste Membership des Users
(stabile Reihenfolge nach `workspace_member.joined_at` und Tie-Breaker
`workspace_id`).

Lazy-Seed: Frische User (GoTrue-Signup ohne Einladung) haben noch keine
Org/Workspace-Zuordnung. Beim ersten `/v1/me`-Aufruf legt `fetch` transparent
eine Personal-Org + Workspace an (`ensure_personal_workspace`), sodass der
Response immer eine valide `default_workspace_id` traegt und der Frontend-
Endlos-Redirect unterbunden wird.
"""

from typing import Protocol
from uuid import UUID

import asyncpg

from who2be_api.core.tenancy import scope_to_self
from who2be_api.repositories.workspace_repository import ensure_personal_workspace
from who2be_api.services.bootstrap_service import claim_bootstrap_org
from who2be_models import DEFAULT_LOCALE, MeOrganization, MeRead, MeWorkspace
from who2be_models.locale import SUPPORTED_LOCALES, normalize_locale


def _content_locale_from_preferred(value: str | None) -> str:
    """UI-Sprache (`preferred_locale`) → Workspace-Content-Sprache (ADR-0045).

    Leere, formwidrige oder nicht unterstuetzte Werte fallen auf
    `DEFAULT_LOCALE` zurueck — der Lazy-Seed darf an einer kaputten
    User-Metadaten-Zeile nie scheitern.
    """
    if not value:
        return DEFAULT_LOCALE
    try:
        normalized = normalize_locale(value)
    except ValueError:
        return DEFAULT_LOCALE
    if normalized not in SUPPORTED_LOCALES:
        return DEFAULT_LOCALE
    return normalized


class MeRepository(Protocol):
    """Service-seitige Abstraktion fuer den `/v1/me`-Read."""

    async def fetch(self, user_id: UUID) -> MeRead: ...


_MEMBER_QUERY = (
    "SELECT o.id AS org_id, o.name AS org_name, o.slug AS org_slug, "
    "o.kind AS org_kind, o.created_at AS org_created_at, "
    "w.id AS workspace_id, w.name AS workspace_name, w.slug AS workspace_slug, "
    "m.role AS workspace_role, m.joined_at AS workspace_joined_at "
    "FROM workspace_member m "
    "JOIN workspace w ON w.id = m.workspace_id "
    "JOIN organization o ON o.id = w.org_id "
    "WHERE m.user_id = $1 AND o.deleted_at IS NULL "
    "ORDER BY o.created_at ASC, o.id ASC, m.joined_at ASC, w.id ASC"
)

# Erneute Pruefung unter dem Seed-Lock — dieselbe Sicht wie `_MEMBER_QUERY`
# (soft-geloeschte Orgs zaehlen nicht), sonst wichen Lazy-Seed-Entscheidung
# und Response voneinander ab.
_HAS_LIVE_MEMBERSHIP_QUERY = (
    "SELECT 1 FROM workspace_member m "
    "JOIN workspace w ON w.id = m.workspace_id "
    "JOIN organization o ON o.id = w.org_id "
    "WHERE m.user_id = $1 AND o.deleted_at IS NULL LIMIT 1"
)


class PgMeRepository:
    """asyncpg-Implementierung."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def fetch(self, user_id: UUID) -> MeRead:
        rows = await self._pool.fetch(_MEMBER_QUERY, user_id)

        # Lazy-Seed: kein Workspace vorhanden → Personal-Workspace anlegen und
        # sofort erneut abfragen, damit der Response stets eine valide
        # default_workspace_id traegt.
        if not rows:
            # Profil VOR dem Lock lesen: `_lookup_profile` braucht eine eigene
            # Pool-Connection, und wer unter dem Lock eine zweite anfordert,
            # kann bei vielen wartenden Erstaufrufen den Pool erschoepfen.
            user_email, content_locale = await self._lookup_profile(user_id)
            # Eine Transaktion, pro User serialisiert: die Web-App ruft /v1/me
            # beim Start mehrfach parallel auf. Ohne Lock sahen alle Aufrufe
            # `rows == []`, einer uebernahm die Bootstrap-Org, die anderen
            # seedeten zusaetzlich eine Personal-Org. Unter dem Lock wird die
            # Mitgliedschaft erneut gelesen; nur wer weiterhin keine hat,
            # uebernimmt bzw. seedet. `xact_lock` gibt am Tx-Ende frei.
            async with self._pool.acquire() as conn, conn.transaction():
                await conn.execute(
                    "SELECT pg_advisory_xact_lock(hashtext($1))", f"me_seed:{user_id}"
                )
                if not await conn.fetchval(_HAS_LIVE_MEMBERSHIP_QUERY, user_id):
                    # On-Prem-Bootstrap (services/bootstrap_service.py): der
                    # erste Login des Bootstrap-Admins mit bestaetigter Adresse
                    # uebernimmt die geseedete Org, statt eine eigene
                    # Personal-Org zu bekommen.
                    if not await claim_bootstrap_org(conn, user_id):
                        # Seed aus mehreren Inserts (Org, Member, Workspace,
                        # Default-Templates), atomar in dieser Transaktion.
                        await ensure_personal_workspace(
                            conn, user_id, user_email=user_email, content_locale=content_locale
                        )
            rows = await self._pool.fetch(_MEMBER_QUERY, user_id)

        orgs: dict[UUID, MeOrganization] = {}
        default_workspace_id: UUID | None = None
        for row in rows:
            org_id = row["org_id"]
            if org_id not in orgs:
                orgs[org_id] = MeOrganization(
                    id=org_id,
                    name=row["org_name"],
                    slug=row["org_slug"],
                    kind=row["org_kind"],
                    workspaces=[],
                )
            orgs[org_id].workspaces.append(
                MeWorkspace(
                    id=row["workspace_id"],
                    name=row["workspace_name"],
                    slug=row["workspace_slug"],
                    role=row["workspace_role"],
                )
            )
            if default_workspace_id is None:
                default_workspace_id = row["workspace_id"]
        return MeRead(
            user_id=user_id,
            default_workspace_id=default_workspace_id,
            organizations=list(orgs.values()),
            has_password=await self._has_password(user_id),
        )

    async def _lookup_profile(self, user_id: UUID) -> tuple[str | None, str]:
        """Liest `email` + `preferred_locale` des Users — EINE Query,
        optional, Fehler → Defaults (None, `DEFAULT_LOCALE`).

        Wird beim Lazy-Seed genutzt, um die Personal-Org nach dem Local-Part
        der E-Mail zu benennen UND die Workspace-Content-Sprache aus der
        UI-Sprache (`raw_user_meta_data ->> 'preferred_locale'`) abzuleiten
        (ADR-0045). Gelesen wird ueber `w2b_user_profiles` (Migration 0090):
        die Laufzeitrolle hat keinen Zugriff auf `auth.users`, und ohne
        Workspace-Mandanten liefert die Funktion nur das eigene Profil — dafuer
        setzt `scope_to_self` `app.current_user_id` transaktionslokal. Ist die
        Funktion nicht aufrufbar (reine Test-DB ohne GoTrue), faellt der Seed
        auf ``"Personal"`` + `'de'` zurueck.
        """
        try:
            async with self._pool.acquire() as conn, conn.transaction():
                await scope_to_self(conn, user_id)
                row = await conn.fetchrow(
                    "SELECT email, raw_user_meta_data ->> 'preferred_locale' AS preferred_locale "
                    "FROM w2b_user_profiles(ARRAY[$1::uuid])",
                    user_id,
                )
        except asyncpg.PostgresError:
            return None, DEFAULT_LOCALE
        if row is None:
            return None, DEFAULT_LOCALE
        return row["email"], _content_locale_from_preferred(row["preferred_locale"])

    async def _has_password(self, user_id: UUID) -> bool:
        """Ob der User ein Passwort gesetzt hat — frisch eingeladene
        Magic-Link-User und reine OAuth-User haben keins, bis sie auf
        `/onboarding/set-password` eines setzen. Gelesen ueber
        `w2b_self_account()` (Migration 0093): nur die eigene Zeile, nur der
        Wahrheitswert, nie der Hash. Ist die Funktion nicht aufrufbar (reine
        API-Test-DB ohne GoTrue), gilt `False`."""
        try:
            async with self._pool.acquire() as conn, conn.transaction():
                await scope_to_self(conn, user_id)
                value = await conn.fetchval("SELECT has_password FROM w2b_self_account()")
        except asyncpg.PostgresError:
            return False
        return bool(value)

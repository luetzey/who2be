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

from who2be_api.repositories.workspace_repository import ensure_personal_workspace
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
            user_email, content_locale = await self._lookup_profile(user_id)
            # Transaktion: der Seed besteht aus mehreren Inserts (Org, Member,
            # Workspace, Default-Templates). Atomar, damit zwei parallele
            # Erstaufrufe desselben Users keinen Teilzustand hinterlassen — die
            # ON-CONFLICT-Klauseln in ensure_personal_workspace machen den
            # Re-Lauf idempotent (analog WorkspaceRepository.create).
            async with self._pool.acquire() as conn, conn.transaction():
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
        """Liest `email` + `preferred_locale` aus `auth.users` — EINE Query,
        optional, Fehler → Defaults (None, `DEFAULT_LOCALE`).

        Wird beim Lazy-Seed genutzt, um die Personal-Org nach dem Local-Part
        der E-Mail zu benennen UND die Workspace-Content-Sprache aus der
        UI-Sprache (`raw_user_meta_data ->> 'preferred_locale'`) abzuleiten
        (ADR-0045). Existiert `auth.users` nicht oder fehlt eine Spalte
        (reine Test-DB), faellt der Seed auf ``"Personal"`` + `'de'` zurueck.
        """
        try:
            row = await self._pool.fetchrow(
                "SELECT email, raw_user_meta_data ->> 'preferred_locale' AS preferred_locale "
                "FROM auth.users WHERE id = $1",
                user_id,
            )
        except asyncpg.PostgresError:
            return None, DEFAULT_LOCALE
        if row is None:
            return None, DEFAULT_LOCALE
        return row["email"], _content_locale_from_preferred(row["preferred_locale"])

    async def _has_password(self, user_id: UUID) -> bool:
        """`auth.users.encrypted_password IS NOT NULL` — frisch eingeladene
        Magic-Link-User haben `NULL`, bis sie auf `/onboarding/set-password`
        ein Passwort setzen. Wenn das `auth`-Schema (noch) nicht existiert
        — z. B. in einer reinen API-Test-DB ohne GoTrue — gilt `False`."""
        try:
            value = await self._pool.fetchval(
                "SELECT encrypted_password IS NOT NULL FROM auth.users WHERE id = $1",
                user_id,
            )
        except asyncpg.PostgresError:
            return False
        return bool(value)

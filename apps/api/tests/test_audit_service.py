"""Unit-Tests fuer die Audit-Wiring (WP-B).

Ohne DB: Fake-Audit-Repo zaehlt die `insert(...)`-Aufrufe; Domain-Repos sind
Fakes, die nur die fuer den jeweiligen Pfad noetigen Methoden implementieren.
Belegt: jede sicherheitskritische Mutation erzeugt genau einen Audit-Eintrag
mit dem erwarteten Action-String und Akteur.

Race-Test fuer den Last-Admin-Lock (zwei nebenlaeufige Admin-Removals) braucht
eine echte DB und ist als `@pytest.mark.integration` in `test_invitations.py`-
Manier mit `pytest.skip(...)` bei fehlender DB ausgestattet.
"""

from __future__ import annotations

import asyncio
import secrets
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import asyncpg
import pytest

from who2be_api.core.config import get_settings
from who2be_api.core.migrations import MIGRATIONS_DIR, apply_migrations
from who2be_api.core.security import WorkspaceContext
from who2be_api.repositories.audit_log_repository import (
    Executor,
    PgAuditLogRepository,
)
from who2be_api.repositories.workspace_member_repository import (
    LastAdminError,
    PgWorkspaceMemberRepository,
)
from who2be_api.services.account_lifecycle_service import AccountLifecycleService
from who2be_api.services.audit_service import AuditService
from who2be_api.services.invitation_service import InvitationService
from who2be_api.services.token_service import TokenService
from who2be_models import (
    InvitationCreate,
    InvitationRead,
    TokenCreate,
    TokenRead,
    WorkspaceRole,
)


@dataclass
class _AuditCall:
    action: str
    org_id: UUID | None
    workspace_id: UUID | None
    actor_id: UUID | None
    target: str | None
    detail: dict[str, Any] | None


class FakeAuditLogRepository:
    """In-Memory-Stub von `AuditLogRepository` — speichert die Aufrufe."""

    def __init__(self) -> None:
        self.calls: list[_AuditCall] = []

    async def insert(
        self,
        executor: Executor,
        *,
        action: str,
        org_id: UUID | None = None,
        workspace_id: UUID | None = None,
        actor_id: UUID | None = None,
        target: str | None = None,
        detail: dict[str, Any] | None = None,
    ) -> None:
        self.calls.append(
            _AuditCall(
                action=action,
                org_id=org_id,
                workspace_id=workspace_id,
                actor_id=actor_id,
                target=target,
                detail=detail,
            )
        )


# --- Token-Service ----------------------------------------------------------


@dataclass
class _FakeTokenRepo:
    last_inserted: TokenRead | None = None
    revoked: list[UUID] = field(default_factory=list)

    async def insert(
        self,
        workspace_id: UUID,
        owner_id: UUID,
        name: str,
        token_hash: str,
        role: WorkspaceRole,
        agent_id: UUID | None = None,
        expires_at: datetime | None = None,
    ) -> TokenRead:
        stored = TokenRead(
            id=uuid4(),
            workspace_id=workspace_id,
            name=name,
            role=role,
            created_at=datetime.now(UTC),
            last_used_at=None,
            revoked_at=None,
        )
        self.last_inserted = stored
        return stored

    async def list_by_workspace(
        self,
        workspace_id: UUID,
        limit: int,
        after: tuple[datetime, UUID] | None,
    ) -> list[TokenRead]:
        return []

    async def list_by_agent(
        self,
        workspace_id: UUID,
        agent_id: UUID,
        limit: int,
        after: tuple[datetime, UUID] | None,
    ) -> list[TokenRead]:
        return []

    async def fetch_auth_by_hash(self, token_hash: str) -> None:
        return None

    async def rename(self, workspace_id: UUID, token_id: UUID, name: str) -> TokenRead | None:
        return self.last_inserted

    async def rotate(self, workspace_id: UUID, token_id: UUID, new_hash: str) -> TokenRead | None:
        return self.last_inserted

    async def revoke(self, workspace_id: UUID, token_id: UUID) -> bool:
        self.revoked.append(token_id)
        return True

    async def touch_last_used(self, token_hash: str) -> None:  # pragma: no cover
        return None


class _FakePool:
    """Minimaler Pool-Stub: `_assert_agent_in_workspace` braucht nur `fetchval`."""

    async def fetchval(self, *_args: object) -> int:
        return 1


def _ctx(role: WorkspaceRole = WorkspaceRole.admin) -> WorkspaceContext:
    return WorkspaceContext(workspace_id=uuid4(), user_id=uuid4(), role=role)


def test_token_service_records_issued_and_revoked() -> None:
    audit_repo = FakeAuditLogRepository()
    audit = AuditService(audit_repo)
    repo = _FakeTokenRepo()
    # Pool muss `fetchval` koennen (Agent-Workspace-Check); der Fake-Audit-Repo
    # nutzt den Pool selbst nicht.
    service = TokenService(repo, audit_service=audit, pool=_FakePool())
    ctx = _ctx()

    asyncio.run(
        service.create(ctx, TokenCreate(name="ci", role=WorkspaceRole.editor, agent_id=uuid4()))
    )
    asyncio.run(service.revoke(ctx, uuid4()))

    actions = [call.action for call in audit_repo.calls]
    assert actions == ["token.issued", "token.revoked"]
    assert all(call.actor_id == ctx.user_id for call in audit_repo.calls)
    assert all(call.workspace_id == ctx.workspace_id for call in audit_repo.calls)


# --- Invitation-Service -----------------------------------------------------


@dataclass
class _FakeInvitationRepo:
    last_created: InvitationRead | None = None
    revoked: list[UUID] = field(default_factory=list)

    async def create(
        self,
        workspace_id: UUID,
        email: str,
        role: WorkspaceRole,
        token_hash: str,
        expires_at: datetime,
        created_by: UUID,
    ) -> InvitationRead:
        stored = InvitationRead(
            id=uuid4(),
            email=email,
            role=role,
            expires_at=expires_at,
            created_at=datetime.now(UTC),
        )
        self.last_created = stored
        return stored

    async def list_pending_by_workspace(self, workspace_id: UUID) -> list[InvitationRead]:
        return []

    async def accept(
        self, token_hash: str, user_id: UUID, expected_email: str | None = None
    ) -> Any:  # pragma: no cover
        raise NotImplementedError

    async def revoke(self, workspace_id: UUID, invitation_id: UUID) -> bool:
        self.revoked.append(invitation_id)
        return True


def test_invitation_service_records_issued_and_revoked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # send_invitation_email ist im Test-Setup ohnehin No-op (Settings ohne
    # supabase_url) — wir patchen es zur Sicherheit auf eine reine async No-op.
    from who2be_api.services import invitation_service

    async def _noop_mail(email: str, plaintext: str) -> None:
        return None

    monkeypatch.setattr(invitation_service, "send_invitation_email", _noop_mail)

    audit_repo = FakeAuditLogRepository()
    audit = AuditService(audit_repo)
    repo = _FakeInvitationRepo()
    service = InvitationService(repo, audit_service=audit, pool=object())
    ctx = _ctx()

    asyncio.run(
        service.create(ctx, InvitationCreate(email="x@example.com", role=WorkspaceRole.editor))
    )
    asyncio.run(service.revoke(ctx, uuid4()))

    actions = [call.action for call in audit_repo.calls]
    assert actions == ["invitation.issued", "invitation.revoked"]
    assert all(call.workspace_id == ctx.workspace_id for call in audit_repo.calls)


# --- Account-Lifecycle ------------------------------------------------------


class _FakeLifecycleRepo:
    """Minimaler Stub fuer `AccountLifecycleService` — kein Konflikt-Pfad."""

    async def is_org_owner(self, org_id: UUID, user_id: UUID) -> bool:
        return True

    async def org_kind(self, org_id: UUID) -> str | None:
        return "company"

    async def soft_delete_organization(self, org_id: UUID, purge_after: datetime) -> datetime:
        return purge_after

    async def sole_owner_company_orgs(self, user_id: UUID) -> list[str]:
        return []

    async def request_account_deletion(self, user_id: UUID, purge_after: datetime) -> None:
        return None


def test_account_lifecycle_records_deletion_events() -> None:
    audit_repo = FakeAuditLogRepository()
    audit = AuditService(audit_repo)
    service = AccountLifecycleService(
        _FakeLifecycleRepo(),
        audit_service=audit,
        pool=object(),
    )
    user = uuid4()
    org = uuid4()

    asyncio.run(service.request_account_deletion(user))
    asyncio.run(service.delete_organization(user, org))

    actions = [call.action for call in audit_repo.calls]
    assert actions == ["account.deletion_requested", "org.soft_deleted"]
    assert audit_repo.calls[0].actor_id == user
    assert audit_repo.calls[1].org_id == org


# --- Workspace-Member-Repo: Audit + Last-Admin-Race (Integration) ----------


_APP_PASSWORD = "audit_member_test_secret"  # noqa: S105 — Test-Fixture


def _db_reachable() -> bool:
    async def _check() -> bool:
        try:
            conn = await asyncpg.connect(get_settings().database_url)
        except (asyncpg.PostgresError, OSError):
            return False
        await conn.close()
        return True

    return asyncio.run(_check())


async def _seed_workspace_with_two_admins(
    conn: asyncpg.Connection,
) -> tuple[UUID, UUID, UUID]:
    """Workspace mit zwei Admins; gibt (workspace_id, admin_a, admin_b) zurueck."""
    org_id = await conn.fetchval(
        "INSERT INTO organization (name, slug, kind) VALUES ('o', $1, 'company') RETURNING id",
        f"o-{secrets.token_hex(4)}",
    )
    ws_id = await conn.fetchval(
        "INSERT INTO workspace (org_id, name, slug) VALUES ($1, 'w', 'w') RETURNING id",
        org_id,
    )
    a, b = uuid4(), uuid4()
    for user_id in (a, b):
        await conn.execute(
            "INSERT INTO workspace_member (workspace_id, user_id, role) VALUES ($1, $2, 'admin')",
            ws_id,
            user_id,
        )
    return ws_id, a, b


@pytest.mark.integration
def test_member_role_change_writes_audit_log() -> None:
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")

    settings = get_settings()
    schema = f"audit_mem_{secrets.token_hex(6)}"

    async def _run() -> None:
        owner = await asyncpg.connect(settings.database_url)
        pool: asyncpg.Pool | None = None
        try:
            await owner.execute(f'CREATE SCHEMA "{schema}"')
            await owner.execute(f'SET search_path TO "{schema}"')
            await apply_migrations(owner, MIGRATIONS_DIR)
            ws_id, admin_a, admin_b = await _seed_workspace_with_two_admins(owner)
            await owner.execute(f"ALTER ROLE who2be_app WITH PASSWORD '{_APP_PASSWORD}'")

            pool = await asyncpg.create_pool(
                settings.database_url,
                user="who2be_app",
                password=_APP_PASSWORD,
                min_size=1,
                max_size=2,
                server_settings={"search_path": schema},
            )
            repo: PgWorkspaceMemberRepository = PgWorkspaceMemberRepository(
                pool, audit_repo=PgAuditLogRepository()
            )
            # Downgrade einen der zwei Admins → erlaubt, da noch einer uebrig.
            await repo.update_role(ws_id, admin_b, WorkspaceRole.editor, actor_id=admin_a)
            audit_rows = await owner.fetch(
                "SELECT action, actor_id, target, detail FROM audit_log "
                "WHERE workspace_id = $1 ORDER BY created_at",
                ws_id,
            )
            assert [row["action"] for row in audit_rows] == ["member.role_changed"]
            assert audit_rows[0]["actor_id"] == admin_a
            assert audit_rows[0]["target"] == str(admin_b)

            # Den letzten Admin entfernen → LastAdminError, kein Audit-Eintrag.
            with pytest.raises(LastAdminError):
                await repo.remove(ws_id, admin_a, actor_id=admin_a)
            audit_rows = await owner.fetch(
                "SELECT action FROM audit_log WHERE workspace_id = $1",
                ws_id,
            )
            assert [row["action"] for row in audit_rows] == ["member.role_changed"]
        finally:
            if pool is not None:
                await pool.close()
            await owner.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
            await owner.close()

    asyncio.run(_run())


@pytest.mark.integration
def test_last_admin_race_is_serialised_by_advisory_lock() -> None:
    """Zwei nebenlaeufige Removals verschiedener Admins → genau einer schlaegt
    fehl (LastAdminError), mindestens ein Admin bleibt zurueck.

    Ohne den Advisory-Lock koennten unter READ COMMITTED beide Transaktionen
    `admin_count = 2` lesen und durchschluepfen — die Invariante riese.
    """
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")

    settings = get_settings()
    schema = f"audit_race_{secrets.token_hex(6)}"

    async def _run() -> None:
        owner = await asyncpg.connect(settings.database_url)
        pool: asyncpg.Pool | None = None
        try:
            await owner.execute(f'CREATE SCHEMA "{schema}"')
            await owner.execute(f'SET search_path TO "{schema}"')
            await apply_migrations(owner, MIGRATIONS_DIR)
            ws_id, admin_a, admin_b = await _seed_workspace_with_two_admins(owner)
            await owner.execute(f"ALTER ROLE who2be_app WITH PASSWORD '{_APP_PASSWORD}'")

            pool = await asyncpg.create_pool(
                settings.database_url,
                user="who2be_app",
                password=_APP_PASSWORD,
                min_size=2,
                max_size=4,
                server_settings={"search_path": schema},
            )
            repo: PgWorkspaceMemberRepository = PgWorkspaceMemberRepository(
                pool, audit_repo=PgAuditLogRepository()
            )

            async def _remove(target: UUID, actor: UUID) -> bool:
                try:
                    await repo.remove(ws_id, target, actor_id=actor)
                    return True
                except LastAdminError:
                    return False

            # Nebenlaeufig: beide Admins parallel entfernen.
            results = await asyncio.gather(
                _remove(admin_a, admin_b),
                _remove(admin_b, admin_a),
            )

            # Genau eine der beiden Operationen darf gelungen sein.
            assert sum(results) == 1
            remaining = await owner.fetchval(
                "SELECT count(*) FROM workspace_member WHERE workspace_id = $1 AND role = 'admin'",
                ws_id,
            )
            assert remaining >= 1
        finally:
            if pool is not None:
                await pool.close()
            await owner.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
            await owner.close()

    asyncio.run(_run())


# Suppress unused-import in environments where the integration tests skip.
_ = timedelta

"""DB-freie Unit-Tests fuer die neuen Token-Service-Operationen.

Deckt Rename/Rotate ab (Edit-Umfang: Umbenennen + Rotieren + Widerrufen), das
`_deny_agent_bound`-Gate auf den neuen Mutationen, sowie (#469) das Admin-MFA-
Gate auf `create`/`rotate`: eine effektive `admin`-Rolle verlangt eine aal2-
Session (`require_aal2`, mit den zwei bestehenden Ausnahmen API-Token und
On-Prem-fail-open). Der DB-Zugriff (`_assert_agent_in_workspace`) ist hier
grossteils irrelevant — ohne Pool (`pool=None`) ist er ein No-Op; `rotate`s
Vor-Rotate-Rollen-Check (`_current_role`) braucht dagegen einen Pool-Stub
(`_FakePool`), sonst greift das neue Gate mangels bekannter Rolle nicht.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from structlog.testing import capture_logs

from who2be_api.core.config import Settings
from who2be_api.core.errors import ApiGateError
from who2be_api.core.security import WorkspaceContext
from who2be_api.services.token_service import TokenService
from who2be_models import AgentToolPolicy, TokenCreate, TokenRead, WorkspaceRole


def _token(
    name: str = "t", agent_id: UUID | None = None, role: WorkspaceRole = WorkspaceRole.editor
) -> TokenRead:
    return TokenRead(
        id=uuid4(),
        workspace_id=uuid4(),
        name=name,
        role=role,
        agent_id=agent_id or uuid4(),
        created_at=datetime.now(UTC),
        last_used_at=None,
        revoked_at=None,
    )


class _FakeRepo:
    """Minimaler Token-Repo-Stub; nur die getesteten Methoden sind belegt."""

    def __init__(
        self,
        rename_ret: TokenRead | None = None,
        rotate_ret: TokenRead | None = None,
        insert_ret: TokenRead | None = None,
    ) -> None:
        self._rename_ret = rename_ret
        self._rotate_ret = rotate_ret
        self._insert_ret = insert_ret
        self.rotated_hash: str | None = None

    async def rename(self, _ws: UUID, _id: UUID, name: str) -> TokenRead | None:
        return self._rename_ret

    async def rotate(self, _ws: UUID, _id: UUID, new_hash: str) -> TokenRead | None:
        self.rotated_hash = new_hash
        return self._rotate_ret

    async def insert(
        self,
        _ws: UUID,
        _owner: UUID,
        name: str,
        _token_hash: str,
        role: WorkspaceRole,
        agent_id: UUID | None = None,
        expires_at: datetime | None = None,
    ) -> TokenRead:
        if self._insert_ret is not None:
            return self._insert_ret
        return _token(name=name, agent_id=agent_id, role=role)


class _FakePool:
    """Stub fuer `_current_role`: liefert eine feste Rolle per `fetchval`."""

    def __init__(self, role: WorkspaceRole | None) -> None:
        self._role = role

    async def fetchval(self, *_args: object) -> str | None:
        return self._role.value if self._role is not None else None


def _svc(repo: _FakeRepo, pool: _FakePool | None = None) -> TokenService:
    # pool=None → _assert_agent_in_workspace/_current_role sind No-Ops, kein Audit.
    return TokenService(cast(Any, repo), audit_service=None, pool=cast(Any, pool))


def _human_ctx(
    role: WorkspaceRole = WorkspaceRole.editor, aal: str | None = None
) -> WorkspaceContext:
    return WorkspaceContext(workspace_id=uuid4(), user_id=uuid4(), role=role, aal=aal)


def _agent_ctx() -> WorkspaceContext:
    return WorkspaceContext(
        workspace_id=uuid4(),
        user_id=uuid4(),
        role=WorkspaceRole.editor,
        is_api_token=True,
        agent_id=uuid4(),
        tool_policy=AgentToolPolicy(),
    )


def _api_token_ctx(role: WorkspaceRole) -> WorkspaceContext:
    # Ungebundener API-Token (kein `tool_policy`) — darf laut `_deny_agent_bound`
    # weiterhin Tokens verwalten und ist vom Admin-MFA-Gate ausgenommen (#469 AC4).
    return WorkspaceContext(workspace_id=uuid4(), user_id=uuid4(), role=role, is_api_token=True)


def _run(coro: Any) -> Any:
    return asyncio.run(coro)


def test_rename_returns_renamed_token() -> None:
    stored = _token(name="neu")
    result = _run(_svc(_FakeRepo(stored, None)).rename(_human_ctx(), uuid4(), "neu"))
    assert result.name == "neu"


def test_rename_missing_raises_404() -> None:
    with pytest.raises(HTTPException) as exc:
        _run(_svc(_FakeRepo(None, None)).rename(_human_ctx(), uuid4(), "x"))
    assert exc.value.status_code == 404


def test_rotate_returns_new_plaintext_and_hashes_it() -> None:
    stored = _token()
    repo = _FakeRepo(None, stored)
    result = _run(_svc(repo).rotate(_human_ctx(), uuid4()))
    assert result.token.startswith("w2b_")
    # Der Service hasht das neue Secret, bevor er es ans Repo gibt.
    assert repo.rotated_hash is not None
    assert repo.rotated_hash != result.token


def test_rotate_missing_or_revoked_raises_404() -> None:
    with pytest.raises(HTTPException) as exc:
        _run(_svc(_FakeRepo(None, None)).rotate(_human_ctx(), uuid4()))
    assert exc.value.status_code == 404


def test_agent_bound_token_cannot_rename() -> None:
    with pytest.raises(HTTPException) as exc:
        _run(_svc(_FakeRepo(_token(), None)).rename(_agent_ctx(), uuid4(), "x"))
    assert exc.value.status_code == 403


def test_agent_bound_token_cannot_rotate() -> None:
    with pytest.raises(HTTPException) as exc:
        _run(_svc(_FakeRepo(None, _token())).rotate(_agent_ctx(), uuid4()))
    assert exc.value.status_code == 403


# --- Admin-MFA-Gate (#469): `create`/`rotate` verlangen aal2 fuer `admin` ---


def test_create_admin_role_from_aal1_session_requires_mfa() -> None:
    ctx = _human_ctx(role=WorkspaceRole.admin, aal="aal1")
    with pytest.raises(ApiGateError) as exc:
        _run(_svc(_FakeRepo()).create(ctx, TokenCreate(name="admin-token", agent_id=uuid4())))
    assert exc.value.status == 403
    assert exc.value.reason == "mfa_required"


def test_create_admin_role_from_aal2_session_succeeds() -> None:
    ctx = _human_ctx(role=WorkspaceRole.admin, aal="aal2")
    result = _run(_svc(_FakeRepo()).create(ctx, TokenCreate(name="admin-token", agent_id=uuid4())))
    assert result.role == WorkspaceRole.admin
    assert result.token.startswith("w2b_")


def test_create_editor_role_from_aal1_session_unaffected_by_admin_gate() -> None:
    # AC3: editor-Tokens sind vom Admin-MFA-Gate nicht betroffen.
    ctx = _human_ctx(role=WorkspaceRole.editor, aal="aal1")
    result = _run(
        _svc(_FakeRepo()).create(
            ctx, TokenCreate(name="editor-token", role=WorkspaceRole.editor, agent_id=uuid4())
        )
    )
    assert result.role == WorkspaceRole.editor


def test_create_admin_role_via_api_token_is_exempt_from_mfa_gate() -> None:
    # AC4: ein bestehender (ungebundener) API-Token ist vom Admin-MFA-Gate
    # ausgenommen (Maschinen-Pfad, `require_aal2`s `is_api_token`-Ausnahme).
    ctx = _api_token_ctx(WorkspaceRole.admin)
    result = _run(_svc(_FakeRepo()).create(ctx, TokenCreate(name="admin-token", agent_id=uuid4())))
    assert result.role == WorkspaceRole.admin


def test_create_admin_role_without_aal_claim_allowed_onprem_fail_open(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # AC5: On-Prem ohne aal-Claim + WHO2BE_REQUIRE_MFA_ONPREM=false laeuft
    # durch, emittiert aber das Warn-Event `aal_missing_onprem`.
    monkeypatch.setattr("who2be_api.core.security.is_onprem", lambda: True)
    monkeypatch.setattr(
        "who2be_api.core.security.get_settings",
        lambda: Settings(_env_file=None, require_mfa_onprem=False),  # type: ignore[call-arg]
    )
    ctx = _human_ctx(role=WorkspaceRole.admin, aal=None)
    with capture_logs() as logs:
        result = _run(
            _svc(_FakeRepo()).create(ctx, TokenCreate(name="admin-token", agent_id=uuid4()))
        )
    assert result.role == WorkspaceRole.admin
    events = [entry for entry in logs if entry.get("event") == "aal_missing_onprem"]
    assert len(events) == 1
    assert events[0]["log_level"] == "warning"


def test_create_admin_role_without_aal_claim_blocked_when_onprem_mfa_required(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # AC5: mit WHO2BE_REQUIRE_MFA_ONPREM=true greift das Gate auch On-Prem.
    monkeypatch.setattr("who2be_api.core.security.is_onprem", lambda: True)
    monkeypatch.setattr(
        "who2be_api.core.security.get_settings",
        lambda: Settings(_env_file=None, require_mfa_onprem=True),  # type: ignore[call-arg]
    )
    ctx = _human_ctx(role=WorkspaceRole.admin, aal=None)
    with pytest.raises(ApiGateError) as exc:
        _run(_svc(_FakeRepo()).create(ctx, TokenCreate(name="admin-token", agent_id=uuid4())))
    assert exc.value.reason == "mfa_required"


def test_rotate_admin_token_from_aal1_session_requires_mfa_before_new_secret_exists() -> None:
    ctx = _human_ctx(role=WorkspaceRole.admin, aal="aal1")
    repo = _FakeRepo(rotate_ret=_token(role=WorkspaceRole.admin))
    with pytest.raises(ApiGateError) as exc:
        _run(_svc(repo, _FakePool(WorkspaceRole.admin)).rotate(ctx, uuid4()))
    assert exc.value.status == 403
    assert exc.value.reason == "mfa_required"
    # Belegt die Kern-Anforderung aus #469: das Gate greift VOR dem Rotate —
    # `repo.rotate` wurde nie aufgerufen, es existiert kein neues Secret.
    assert repo.rotated_hash is None


def test_rotate_admin_token_from_aal2_session_succeeds() -> None:
    ctx = _human_ctx(role=WorkspaceRole.admin, aal="aal2")
    repo = _FakeRepo(rotate_ret=_token(role=WorkspaceRole.admin))
    result = _run(_svc(repo, _FakePool(WorkspaceRole.admin)).rotate(ctx, uuid4()))
    assert result.token.startswith("w2b_")
    assert repo.rotated_hash is not None


def test_rotate_editor_token_from_aal1_session_unaffected_by_admin_gate() -> None:
    # AC3: das Rotieren eines editor-Tokens ist vom Admin-MFA-Gate nicht betroffen.
    ctx = _human_ctx(role=WorkspaceRole.editor, aal="aal1")
    repo = _FakeRepo(rotate_ret=_token(role=WorkspaceRole.editor))
    result = _run(_svc(repo, _FakePool(WorkspaceRole.editor)).rotate(ctx, uuid4()))
    assert result.token.startswith("w2b_")


def test_rotate_admin_token_via_api_token_is_exempt_from_mfa_gate() -> None:
    # AC4: ein bestehender (ungebundener) API-Token darf ein admin-Token
    # rotieren, ohne dass das MFA-Gate greift.
    ctx = _api_token_ctx(WorkspaceRole.admin)
    repo = _FakeRepo(rotate_ret=_token(role=WorkspaceRole.admin))
    result = _run(_svc(repo, _FakePool(WorkspaceRole.admin)).rotate(ctx, uuid4()))
    assert result.token.startswith("w2b_")


def test_rotate_missing_token_skips_mfa_gate_and_still_raises_404() -> None:
    # `_current_role` liefert None fuer einen nicht (mehr) existenten Token —
    # das Gate greift dann nicht, der bestehende 404-Pfad bleibt unveraendert.
    ctx = _human_ctx(role=WorkspaceRole.admin, aal="aal1")
    with pytest.raises(HTTPException) as exc:
        _run(_svc(_FakeRepo(), _FakePool(None)).rotate(ctx, uuid4()))
    assert exc.value.status_code == 404

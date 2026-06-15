"""DB-freie Unit-Tests fuer die neuen Token-Service-Operationen.

Deckt Rename/Rotate ab (Edit-Umfang: Umbenennen + Rotieren + Widerrufen) sowie
das `_deny_agent_bound`-Gate auf den neuen Mutationen. Der DB-Zugriff
(`_assert_agent_in_workspace`) ist hier irrelevant — ohne Pool (`pool=None`)
ist er ein No-Op, und die geprueften Pfade brauchen ihn nicht.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException

from who2be_api.core.security import WorkspaceContext
from who2be_api.services.token_service import TokenService
from who2be_models import AgentToolPolicy, TokenRead, WorkspaceRole


def _token(name: str = "t", agent_id: UUID | None = None) -> TokenRead:
    return TokenRead(
        id=uuid4(),
        workspace_id=uuid4(),
        name=name,
        role=WorkspaceRole.editor,
        agent_id=agent_id or uuid4(),
        created_at=datetime.now(UTC),
        last_used_at=None,
        revoked_at=None,
    )


class _FakeRepo:
    """Minimaler Token-Repo-Stub; nur die getesteten Methoden sind belegt."""

    def __init__(self, rename_ret: TokenRead | None, rotate_ret: TokenRead | None) -> None:
        self._rename_ret = rename_ret
        self._rotate_ret = rotate_ret
        self.rotated_hash: str | None = None

    async def rename(self, _ws: UUID, _id: UUID, name: str) -> TokenRead | None:
        return self._rename_ret

    async def rotate(self, _ws: UUID, _id: UUID, new_hash: str) -> TokenRead | None:
        self.rotated_hash = new_hash
        return self._rotate_ret


def _svc(repo: _FakeRepo) -> TokenService:
    # pool=None → _assert_agent_in_workspace No-Op, kein Audit.
    return TokenService(cast(Any, repo), audit_service=None, pool=None)


def _human_ctx() -> WorkspaceContext:
    return WorkspaceContext(workspace_id=uuid4(), user_id=uuid4(), role=WorkspaceRole.editor)


def _agent_ctx() -> WorkspaceContext:
    return WorkspaceContext(
        workspace_id=uuid4(),
        user_id=uuid4(),
        role=WorkspaceRole.editor,
        is_api_token=True,
        agent_id=uuid4(),
        tool_policy=AgentToolPolicy(),
    )


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

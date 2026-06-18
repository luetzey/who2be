from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from who2be_models import TokenCreate, TokenCreated, TokenRead, WorkspaceRole


def test_create_requires_non_empty_name() -> None:
    with pytest.raises(ValidationError):
        TokenCreate(name="", agent_id=uuid4())


def test_create_requires_agent_id() -> None:
    # Pflicht-Bindung: ohne agent_id ist ein Token nicht erstellbar (secure by default).
    with pytest.raises(ValidationError):
        TokenCreate(name="agent")  # type: ignore[call-arg]


def test_read_has_no_secret_fields() -> None:
    fields = set(TokenRead.model_fields)
    assert "token" not in fields
    assert "token_hash" not in fields


def test_read_allows_null_usage_timestamps() -> None:
    token = TokenRead(
        id=uuid4(),
        workspace_id=uuid4(),
        name="agent",
        role=WorkspaceRole.admin,
        created_at=datetime.now(UTC),
        last_used_at=None,
        revoked_at=None,
    )
    assert token.last_used_at is None


def test_create_role_defaults_to_none() -> None:
    # role=None signalisiert dem Service "Snapshot der Ersteller-Rolle".
    assert TokenCreate(name="agent", agent_id=uuid4()).role is None


def test_created_exposes_plaintext_token_once() -> None:
    created = TokenCreated(
        id=uuid4(),
        workspace_id=uuid4(),
        name="agent",
        role=WorkspaceRole.admin,
        created_at=datetime.now(UTC),
        last_used_at=None,
        revoked_at=None,
        token="w2b_secret_plaintext",
    )
    assert created.token == "w2b_secret_plaintext"
    assert "token" in TokenCreated.model_fields

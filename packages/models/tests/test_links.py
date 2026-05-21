from uuid import uuid4

import pytest
from pydantic import ValidationError

from who2be_models import PersonaPlaybookLinkSet


def test_link_set_defaults_to_empty() -> None:
    assert PersonaPlaybookLinkSet().playbook_ids == []


def test_link_set_accepts_playbook_ids() -> None:
    ids = [uuid4(), uuid4()]
    assert PersonaPlaybookLinkSet(playbook_ids=ids).playbook_ids == ids


def test_link_set_rejects_non_uuid_entries() -> None:
    with pytest.raises(ValidationError):
        PersonaPlaybookLinkSet(playbook_ids=["not-a-uuid"])  # type: ignore[list-item]

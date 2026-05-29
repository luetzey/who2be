"""Round-Trip-Tests fuer die Phase-3-0 Resource-Helper-Shapes."""

from uuid import uuid4

import pytest
from pydantic import ValidationError

from who2be_models import LinkedBlockSection, ResourceBlock, ResourceUsage


def test_linked_block_section_round_trip() -> None:
    section = LinkedBlockSection(
        resource_id=uuid4(),
        resource_name="Style Guide",
        block_id="heading-1",
        position=0,
        available=True,
        preview="Section preview",
        section_blocks=[
            ResourceBlock(id="heading-1", type="heading"),
            ResourceBlock(id="p-1", type="paragraph"),
        ],
    )
    restored = LinkedBlockSection.model_validate(section.model_dump())
    assert restored == section
    assert len(restored.section_blocks) == 2


def test_linked_block_section_defaults_empty_section() -> None:
    section = LinkedBlockSection(
        resource_id=uuid4(),
        resource_name="Style Guide",
        block_id="heading-1",
        position=0,
        available=False,
    )
    assert section.section_blocks == []
    assert section.preview is None


def test_resource_usage_round_trip() -> None:
    usage = ResourceUsage(playbook_id=uuid4(), playbook_name="Onboarding", block_count=3)
    assert ResourceUsage.model_validate(usage.model_dump()) == usage


def test_resource_usage_rejects_negative_block_count() -> None:
    with pytest.raises(ValidationError):
        ResourceUsage(playbook_id=uuid4(), playbook_name="X", block_count=-1)

"""Gezielte Unit-Tests fuer reine Logik-Branches (ADR-0032, Phase 1).

Schliesst die im Coverage-Report sichtbaren Luecken in `version_diff` und
`promote_validation` — bewusst DB-frei, jede Assertion deckt einen konkreten
Zweig der Pflichtfeld-/Diff-Logik.
"""

from typing import Any

import pytest

from who2be_api.services.promote_validation import (
    PromoteValidationError,
    validate_promote_playbook,
    validate_promote_resource,
)
from who2be_api.services.version_diff import compute_version_diff
from who2be_models import VersionStatus


def _block(block_id: str, text: str) -> dict[str, Any]:
    return {"id": block_id, "type": "paragraph", "content": [{"type": "text", "text": text}]}


def test_version_diff_unchanged_block_is_not_reported() -> None:
    """Ein unveraenderter Block in einer Block-Liste erscheint NICHT als Change.

    Deckt den `before_block == after_block`-Zweig in `_diff_block_list`: nur der
    geaenderte Block `b` taucht auf, der unveraenderte `a` wird uebersprungen.
    """
    before = {"blocks": [_block("a", "stabil"), _block("b", "alt")]}
    after = {"blocks": [_block("a", "stabil"), _block("b", "neu")]}

    diff = compute_version_diff(
        version=2, against="active", against_version=1, before=before, after=after
    )

    assert diff.identical is False
    paths = [c.path for c in diff.changes]
    assert paths == ["blocks[b]"]
    assert diff.changes[0].op == "changed"


def test_version_diff_identical_content_has_no_changes() -> None:
    before = {"blocks": [_block("a", "x")], "title": "t"}
    diff = compute_version_diff(
        version=2, against="active", against_version=1, before=before, after=dict(before)
    )
    assert diff.identical is True
    assert diff.changes == []


@pytest.mark.parametrize("to_status", [VersionStatus.draft, VersionStatus.inactive])
def test_promote_validators_skip_non_promote_directions(to_status: VersionStatus) -> None:
    """Nur draft->review/active validieren; andere Richtungen sind No-ops.

    Deckt die fruehen `return`-Zweige in `validate_promote_playbook`/`_resource`:
    selbst mit komplett leerem Content wird NICHT geworfen.
    """
    validate_promote_playbook("", {}, to_status)
    validate_promote_resource("", {}, to_status)


def test_promote_resource_missing_name_and_body() -> None:
    """Leerer Name + leere Bloecke → beide Felder in `missing`."""
    with pytest.raises(PromoteValidationError) as exc:
        validate_promote_resource("  ", {"description": "da", "blocks": []}, VersionStatus.review)
    assert "name" in exc.value.missing
    assert "body" in exc.value.missing


def test_promote_resource_non_dict_block_counts_as_filled_body() -> None:
    """Ein Nicht-dict-Block gilt konservativ als befuellt → kein 'body' fehlt."""
    validate_promote_resource(
        "R", {"description": "d", "blocks": ["irgendwas"]}, VersionStatus.active
    )


def test_promote_resource_non_text_block_counts_as_filled_body() -> None:
    """Block ohne 'content' (z. B. Image/Divider) gilt als befuellter Body."""
    validate_promote_resource(
        "R",
        {"description": "d", "blocks": [{"id": "i1", "type": "image"}]},
        VersionStatus.active,
    )


def test_promote_playbook_missing_type_only() -> None:
    """Vollstaendig bis auf `type` → genau 'type' fehlt."""
    with pytest.raises(PromoteValidationError) as exc:
        validate_promote_playbook(
            "PB", {"description": "d", "body": "1.", "type": ""}, VersionStatus.active
        )
    assert exc.value.missing == ["type"]

"""Unit-Tests fuer den generischen Versions-Diff (`compute_version_diff`).

Kein DB-Zugriff: prueft die reine Diff-Mechanik (Skalar-/Block-Diff, ID-
Matching, leerer Vergleichsstand).
"""

from who2be_api.services.version_diff import compute_version_diff


def _block(block_id: str, text: str) -> dict[str, object]:
    return {
        "id": block_id,
        "type": "paragraph",
        "content": [{"type": "text", "text": text, "styles": {}}],
    }


def test_identical_content_has_no_changes() -> None:
    content = {"description": "a", "blocks": [_block("b1", "x")]}
    diff = compute_version_diff(
        version=2, against="active", against_version=1, before=content, after=dict(content)
    )
    assert diff.identical is True
    assert diff.changes == []
    assert diff.against_version == 1


def test_scalar_field_change_is_reported() -> None:
    diff = compute_version_diff(
        version=2,
        against="active",
        against_version=1,
        before={"description": "old", "type": "workflow"},
        after={"description": "new", "type": "workflow"},
    )
    assert diff.identical is False
    assert len(diff.changes) == 1
    change = diff.changes[0]
    assert change.path == "description"
    assert change.op == "changed"
    assert change.before == "old"
    assert change.after == "new"


def test_added_and_removed_scalar_fields() -> None:
    diff = compute_version_diff(
        version=2,
        against="active",
        against_version=1,
        before={"keep": 1, "gone": 2},
        after={"keep": 1, "added": 3},
    )
    by_path = {c.path: c for c in diff.changes}
    assert by_path["gone"].op == "removed"
    assert by_path["gone"].before == 2
    assert by_path["added"].op == "added"
    assert by_path["added"].after == 3


def test_block_list_diff_matches_by_id() -> None:
    before = {"blocks": [_block("b1", "one"), _block("b2", "two")]}
    after = {"blocks": [_block("b1", "ONE"), _block("b3", "three")]}
    diff = compute_version_diff(
        version=2, against="active", against_version=1, before=before, after=after
    )
    by_path = {c.path: c.op for c in diff.changes}
    assert by_path["blocks[b1]"] == "changed"
    assert by_path["blocks[b2]"] == "removed"
    assert by_path["blocks[b3]"] == "added"


def test_no_active_base_renders_everything_as_added() -> None:
    after = {"description": "fresh", "blocks": [_block("b1", "x")]}
    diff = compute_version_diff(
        version=1, against="active", against_version=None, before={}, after=after
    )
    assert diff.against_version is None
    ops = {c.path: c.op for c in diff.changes}
    assert ops["description"] == "added"
    assert ops["blocks[b1]"] == "added"


def test_nested_dict_recurses_into_block_lists() -> None:
    # Persona-Form: content.content.blocks liegt verschachtelt.
    before = {"content": {"blocks": [_block("b1", "x")]}}
    after = {"content": {"blocks": [_block("b1", "y")]}}
    diff = compute_version_diff(
        version=2, against="active", against_version=1, before=before, after=after
    )
    assert [c.path for c in diff.changes] == ["content.blocks[b1]"]
    assert diff.changes[0].op == "changed"

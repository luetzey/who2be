"""Unit-Tests fuer `extract_pills` (B3 — Save-Sync „Body treibt").

Deckt ab: Playbook- und Resource-Pills, Block-Anker-Scope, Dedup der Playbook-
IDs, kaputtes/leeres JSON (→ leere Listen), gemischte Dokumentreihenfolge sowie
die Rekursion in `children`.
"""

import json
from uuid import uuid4

from who2be_api.services.playbook_body_pills import extract_pills


def _playbook_pill(target_id: str) -> dict[str, object]:
    return {
        "type": "placeholder",
        "props": {"kind": "playbook", "target_id": target_id, "label": "Sub"},
    }


def _resource_pill(target_id: str) -> dict[str, object]:
    return {
        "type": "placeholder",
        "props": {"kind": "resource", "target_id": target_id, "label": "Res"},
    }


def _text(value: str) -> dict[str, object]:
    return {"type": "text", "text": value, "styles": {}}


def _block(
    content: list[dict[str, object]],
    children: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    return {"type": "paragraph", "content": content, "children": children or []}


def test_extracts_playbook_and_resource_pills() -> None:
    child = uuid4()
    resource = uuid4()
    body = json.dumps([_block([_playbook_pill(str(child)), _resource_pill(str(resource))])])
    child_ids, links = extract_pills(body)
    assert child_ids == [child]
    assert len(links) == 1
    assert links[0].resource_id == resource
    assert links[0].link_scope == "resource"
    assert links[0].block_id is None
    assert links[0].position == 0


def test_resource_pill_with_block_anchor() -> None:
    resource = uuid4()
    body = json.dumps([_block([_resource_pill(f"{resource}#heading-1")])])
    _, links = extract_pills(body)
    assert links[0].link_scope == "block"
    assert links[0].block_id == "heading-1"
    assert links[0].resource_id == resource


def test_playbook_ids_deduplicated_order_preserved() -> None:
    a = uuid4()
    b = uuid4()
    body = json.dumps(
        [
            _block([_playbook_pill(str(a)), _playbook_pill(str(b))]),
            _block([_playbook_pill(str(a))]),  # Duplikat von a
        ]
    )
    child_ids, _ = extract_pills(body)
    assert child_ids == [a, b]


def test_content_wrapper_shape_supported() -> None:
    child = uuid4()
    body = json.dumps({"content": [_block([_playbook_pill(str(child))])]})
    child_ids, _ = extract_pills(body)
    assert child_ids == [child]


def test_broken_json_returns_empty() -> None:
    child_ids, links = extract_pills("{ this is not json")
    assert child_ids == []
    assert links == []


def test_non_string_returns_empty() -> None:
    child_ids, links = extract_pills(None)  # type: ignore[arg-type]
    assert child_ids == []
    assert links == []


def test_mixed_order_positions_increment() -> None:
    r1 = uuid4()
    r2 = uuid4()
    child = uuid4()
    body = json.dumps(
        [
            _block([_text("Intro "), _resource_pill(str(r1))]),
            _block([_playbook_pill(str(child)), _resource_pill(f"{r2}#h2")]),
        ]
    )
    child_ids, links = extract_pills(body)
    assert child_ids == [child]
    assert [link.resource_id for link in links] == [r1, r2]
    assert [link.position for link in links] == [0, 1]


def test_children_recursion() -> None:
    child = uuid4()
    resource = uuid4()
    body = json.dumps(
        [
            _block(
                [_text("Parent")],
                children=[_block([_playbook_pill(str(child)), _resource_pill(str(resource))])],
            )
        ]
    )
    child_ids, links = extract_pills(body)
    assert child_ids == [child]
    assert links[0].resource_id == resource

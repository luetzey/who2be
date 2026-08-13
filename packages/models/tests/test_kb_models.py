"""Unit-Tests fuer die Knowledge-Base-Models (WP1, ADR-0047).

DB-frei: Roundtrips + die Modell-Validatoren (co_occurs_with-Pflichtfelder,
Evidence-Minimum, Teilupdate-Pflicht). Die Service-Regeln (Belegpflicht in
einer Transaktion, Tier-Upgrade-Regeln, n>=20) leben in den API-WPs.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from who2be_models import (
    EdgeType,
    KbConflictKind,
    KbConflictRead,
    KbEdgeCreate,
    KbEdgeRead,
    KbNeighbor,
    KbNodeCreate,
    KbNodeRead,
    KbNodeUpdate,
    KbSearchHit,
    NodeStatus,
    NodeTier,
    OccurredPrecision,
    Sensitivity,
    SourceRefKind,
)

_NOW = datetime(2026, 8, 13, 12, 0, tzinfo=UTC)


def _node_read_payload() -> dict[str, object]:
    return {
        "id": uuid4(),
        "workspace_id": uuid4(),
        "tier": "hypothesis",
        "content": "Kunde X bestellt immer montags.",
        "source_ref": f"artifact:{uuid4()}#a1b2c3d4",
        "source_ref_kind": "artifact",
        "status": "live",
        "derivation_depth": 0,
        "sensitivity": "general",
        "occurred_at": _NOW,
        "occurred_precision": "day",
        "created_by": "agent:00000000-0000-0000-0000-000000000001",
        "created_at": _NOW,
        "updated_at": _NOW,
    }


class TestKbNode:
    def test_create_defaults(self) -> None:
        node = KbNodeCreate(
            content="Aussage",
            tier=NodeTier.hypothesis,
            source_ref="url:https://example.org",
            occurred_at=_NOW,
        )
        # Wissens-Aussagen sind selten minutengenau: Default `day`.
        assert node.occurred_precision == OccurredPrecision.day
        assert node.sensitivity == Sensitivity.general
        assert node.content_ref is None

    def test_create_requires_source_ref(self) -> None:
        # Belegpflicht: kein Node ohne source_ref (ADR-0047).
        with pytest.raises(ValidationError):
            KbNodeCreate.model_validate(
                {"content": "Aussage", "tier": "hypothesis", "occurred_at": _NOW}
            )

    def test_create_forbids_extra_fields(self) -> None:
        with pytest.raises(ValidationError):
            KbNodeCreate.model_validate(
                {
                    "content": "x",
                    "tier": "derived",
                    "source_ref": "url:https://example.org",
                    "occurred_at": _NOW,
                    "status": "stale",
                }
            )

    def test_read_roundtrip(self) -> None:
        read = KbNodeRead.model_validate(_node_read_payload())
        assert read.tier == NodeTier.hypothesis
        assert read.status == NodeStatus.live
        assert read.source_ref_kind == SourceRefKind.artifact
        assert read.ttl_expires_at is None

    def test_update_requires_at_least_one_field(self) -> None:
        with pytest.raises(ValidationError, match="Mindestens ein Feld"):
            KbNodeUpdate()

    def test_update_single_field_ok(self) -> None:
        assert KbNodeUpdate(content="Neu").tier is None
        assert KbNodeUpdate(tier=NodeTier.derived).content is None
        update = KbNodeUpdate(additional_source_ref="sha256:" + "ab" * 32)
        assert update.additional_source_ref is not None


def _edge_kwargs() -> dict[str, object]:
    return {
        "from_anchor": f"{uuid4()}",
        "to_anchor": f"{uuid4()}#a1b2c3d4",
        "evidence_from": [f"{uuid4()}#b1b2c3d4"],
        "evidence_to": [f"{uuid4()}#c1c2c3c4"],
    }


class TestKbEdgeCreate:
    def test_supports_edge_roundtrip(self) -> None:
        edge = KbEdgeCreate.model_validate({**_edge_kwargs(), "type": "supports"})
        assert edge.type == EdgeType.supports
        assert edge.co_query is None
        assert KbEdgeCreate.model_validate(edge.model_dump()) == edge

    def test_evidence_required_on_both_sides(self) -> None:
        # Belegpflicht pro Seite: leere Evidence-Liste ist schon im Modell
        # abgelehnt (das Service-422 `evidence_missing` prueft die Aufloesung).
        for side in ("evidence_from", "evidence_to"):
            payload = {**_edge_kwargs(), "type": "supports", side: []}
            with pytest.raises(ValidationError):
                KbEdgeCreate.model_validate(payload)

    def test_co_occurs_requires_all_co_fields(self) -> None:
        base = {**_edge_kwargs(), "type": "co_occurs_with"}
        with pytest.raises(ValidationError, match="co_occurs_with"):
            KbEdgeCreate.model_validate(base)
        # Ein fehlendes co_-Feld reicht fuer die Ablehnung.
        partial = {
            **base,
            "co_query": "SELECT …",
            "co_n": 25,
            "co_from": _NOW,
        }
        with pytest.raises(ValidationError, match="co_occurs_with"):
            KbEdgeCreate.model_validate(partial)

    def test_co_occurs_with_all_fields_ok(self) -> None:
        edge = KbEdgeCreate.model_validate(
            {
                **_edge_kwargs(),
                "type": "co_occurs_with",
                "co_query": "SELECT …",
                "co_n": 25,
                "co_from": _NOW,
                "co_to": _NOW,
            }
        )
        assert edge.co_n == 25

    def test_co_fields_forbidden_for_other_types(self) -> None:
        with pytest.raises(ValidationError, match="co_-Felder"):
            KbEdgeCreate.model_validate({**_edge_kwargs(), "type": "supports", "co_n": 25})

    def test_co_n_lower_bound_is_model_side_one(self) -> None:
        # Die 20er-Grenze prueft der SERVICE (422 `correlation_underpowered`
        # mit tatsaechlichem n) — das Modell verlangt nur >= 1.
        edge = KbEdgeCreate.model_validate(
            {
                **_edge_kwargs(),
                "type": "co_occurs_with",
                "co_query": "SELECT …",
                "co_n": 5,
                "co_from": _NOW,
                "co_to": _NOW,
            }
        )
        assert edge.co_n == 5
        with pytest.raises(ValidationError):
            KbEdgeCreate.model_validate(
                {
                    **_edge_kwargs(),
                    "type": "co_occurs_with",
                    "co_query": "SELECT …",
                    "co_n": 0,
                    "co_from": _NOW,
                    "co_to": _NOW,
                }
            )


class TestKbReadModels:
    def test_edge_read_roundtrip(self) -> None:
        read = KbEdgeRead.model_validate(
            {
                "id": uuid4(),
                "workspace_id": uuid4(),
                "type": "derived_from",
                "from_anchor": f"{uuid4()}",
                "to_anchor": f"{uuid4()}",
                "from_node_id": uuid4(),
                "to_node_id": None,
                "evidence_from": ["a"],
                "evidence_to": ["b"],
                "created_by": "user:00000000-0000-0000-0000-000000000002",
                "created_at": _NOW,
            }
        )
        assert read.type == EdgeType.derived_from
        assert read.to_node_id is None

    def test_neighbor_carries_direction_and_co_n(self) -> None:
        neighbor = KbNeighbor.model_validate(
            {
                "node": _node_read_payload(),
                "edge_type": "co_occurs_with",
                "direction": "out",
                "co_n": 42,
            }
        )
        assert neighbor.direction == "out"
        assert neighbor.co_n == 42
        with pytest.raises(ValidationError):
            KbNeighbor.model_validate(
                {"node": _node_read_payload(), "edge_type": "supports", "direction": "sideways"}
            )

    def test_search_hit_roundtrip(self) -> None:
        node_id = uuid4()
        hit = KbSearchHit.model_validate(
            {
                "node_id": node_id,
                "anchor": str(node_id),
                "snippet": "…Aussage…",
                "tier": "verified",
                "status": "stale",
                "score": 1.5,
            }
        )
        assert hit.tier == NodeTier.verified
        assert hit.status == NodeStatus.stale

    def test_conflict_roundtrip(self) -> None:
        conflict = KbConflictRead.model_validate(
            {
                "id": uuid4(),
                "kind": "rule",
                "a_id": uuid4(),
                "b_id": uuid4(),
                "reason": "Zwei aktive Regeln, verschiedene Kategorien.",
                "opened_at": _NOW,
                "resolved_at": None,
                "resolution": None,
            }
        )
        assert conflict.kind == KbConflictKind.rule
        assert conflict.resolved_at is None

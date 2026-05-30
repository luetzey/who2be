from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from who2be_models import (
    DashboardActivity,
    DashboardActor,
    DashboardKpis,
    DashboardResponse,
    DashboardStatusDistribution,
    EntityStatusDistribution,
)


def _distribution() -> DashboardStatusDistribution:
    return DashboardStatusDistribution(
        persona=EntityStatusDistribution(draft=2, review=1, active=12, inactive=8),
        playbook=EntityStatusDistribution(draft=0, review=0, active=34, inactive=5),
        resource=EntityStatusDistribution(draft=1, review=0, active=7, inactive=2),
    )


def _kpis() -> DashboardKpis:
    return DashboardKpis(active_personas=12, active_playbooks=34, pending_reviews=3)


def test_activity_defaults_to_empty_list() -> None:
    response = DashboardResponse(kpis=_kpis(), status_distribution=_distribution())
    assert response.activity == []


def test_round_trip_preserves_activity() -> None:
    entry = DashboardActivity(
        ts=datetime.now(UTC),
        actor=DashboardActor(user_id=uuid4(), display_name="Alice"),
        entity_type="playbook",
        entity_id=uuid4(),
        entity_name="Onboard",
        event="promoted_to_active",
        from_version=3,
        to_version=4,
    )
    response = DashboardResponse(
        kpis=_kpis(),
        activity=[entry],
        status_distribution=_distribution(),
    )
    restored = DashboardResponse.model_validate(response.model_dump())
    assert restored == response


def test_rejects_negative_kpi() -> None:
    with pytest.raises(ValidationError):
        DashboardKpis(active_personas=-1, active_playbooks=0, pending_reviews=0)


def test_rejects_negative_distribution_value() -> None:
    with pytest.raises(ValidationError):
        EntityStatusDistribution(draft=-1, review=0, active=0, inactive=0)

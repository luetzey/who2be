"""Dashboard-Antwort fuer `GET /v1/workspaces/{ws_id}/dashboard`.

Schema folgt Plan §2.1.E (siehe
`.claude/plan/2026-05-27-1921_phase-2-vollwertige-app.md`): drei KPI-Werte,
eine `activity`-Liste aus `status_history` und eine Verteilung pro
Entity-Typ.

Phase 3 — Fix Track 1: Die Frontend-`ActivityRow` erwartet ein flaches
DTO mit `actor`, `entity_name` und einem abgeleiteten `event`-String, statt
der rohen `StatusHistoryEntry`. Backend liefert das jetzt direkt; das alte
`StatusHistoryEntry` bleibt fuer den schreibenden Audit-Trail bestehen.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from who2be_models.status_history import EntityType


class DashboardKpis(BaseModel):
    """Top-Line-KPIs des Workspaces."""

    model_config = ConfigDict(from_attributes=True)

    active_personas: int = Field(ge=0)
    active_playbooks: int = Field(ge=0)
    active_resources: int = Field(ge=0, default=0)
    pending_reviews: int = Field(ge=0)


class EntityStatusDistribution(BaseModel):
    """Anzahl Versionen je Status fuer einen Entity-Typ."""

    model_config = ConfigDict(from_attributes=True)

    draft: int = Field(ge=0)
    review: int = Field(ge=0)
    active: int = Field(ge=0)
    inactive: int = Field(ge=0)


class DashboardStatusDistribution(BaseModel):
    """Status-Verteilung pro Entity-Typ."""

    model_config = ConfigDict(from_attributes=True)

    persona: EntityStatusDistribution
    playbook: EntityStatusDistribution
    resource: EntityStatusDistribution


class DashboardActor(BaseModel):
    """Wer hat den Status-Wechsel ausgeloest — fuers UI aufbereitet."""

    model_config = ConfigDict(from_attributes=True)

    user_id: UUID
    # Service garantiert per Fallback-Kette einen nicht-leeren String
    # (`raw_user_meta_data->>'name'` → Email-Local-Part → User-ID-String).
    display_name: str


class DashboardActivity(BaseModel):
    """Ein Eintrag des Activity-Feeds, fertig fuers Frontend."""

    model_config = ConfigDict(from_attributes=True)

    ts: datetime
    actor: DashboardActor
    entity_type: EntityType
    entity_id: UUID
    entity_name: str | None = None
    event: str
    from_version: int | None = None
    to_version: int | None = None


class DashboardResponse(BaseModel):
    """Antwort von `GET /v1/workspaces/{ws_id}/dashboard`."""

    model_config = ConfigDict(from_attributes=True)

    kpis: DashboardKpis
    activity: list[DashboardActivity] = Field(default_factory=list)
    status_distribution: DashboardStatusDistribution
